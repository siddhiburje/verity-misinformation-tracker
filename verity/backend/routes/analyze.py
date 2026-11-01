"""
Analysis endpoints — the core "track a claim" functionality.

POST /api/analyze/text     body: { "text": "..." }
POST /api/analyze/image    multipart form, field name "image"
POST /api/analyze/batch    body: { "items": [ {"claim","source","date"}, ... ] }
GET  /api/claims/<id>      single claim + its direct-neighbor graph
GET  /api/history          the current user's recent searches

/analyze/text and /analyze/image also run claim VERIFICATION (a
separate concept from the narrative/similarity matching in
analysis_service.py — see services/verification_service.py for the
full explanation). /analyze/batch deliberately does NOT run
verification, to avoid looping an external API call over up to
MAX_BATCH_ITEMS rows.
"""
import json
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Claim, SearchHistory
from services import analysis_service, verification_service, news_service
from ocr.engine import extract_text_from_bytes, OCRError

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api")

MAX_TEXT_LENGTH = 8000
MAX_BATCH_ITEMS = 200
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}


def _error(message, status=400):
    return jsonify({"error": message}), status


def _verify_and_attach(claim):
    """
    Runs claim verification (Google Fact Check Tools API) for a single
    claim and stores the result directly on it. Never raises — the
    verification service itself already turns every failure mode into
    an honest "Unverified" result, so this never blocks or breaks the
    surrounding analyze request.
    """
    api_key = current_app.config["FACTCHECK_API_KEY"]
    result = verification_service.verify_claim(claim.text, api_key)
    claim.verification_status = result["status"]
    claim.verification_explanation = result["explanation"]
    claim.verification_sources_json = json.dumps(result["sources"])
    claim.verification_checked_at = datetime.fromisoformat(result["checked_at"])


def _live_news_evidence(claim):
    """Return recent live NewsAPI coverage as CONTEXT, never as a truth verdict."""
    try:
        api_key = current_app.config.get("NEWSAPI_KEY")
        if not api_key:
            return []
        articles, is_live, _warning = news_service.search_news(
            claim.text[:240], api_key, page_size=5
        )
        if not is_live:
            return []
        return [a for a in articles if a.get("url")][:5]
    except Exception:
        return []


def _claim_payload(claim, best_match, news_evidence=None):
    graph = analysis_service.build_graph_for_claim(claim.id)
    timeline = sorted(graph["nodes"], key=lambda n: n["published_at"] or n["created_at"] or "")
    return {
        "claim": claim.to_dict(),
        "best_match": {
            "claim_id": best_match[0].id,
            "similarity": round(best_match[1] * 100, 1),
            "narrative_label": best_match[0].narrative_label,
        } if best_match else None,
        "graph": graph,
        "timeline": timeline,
        "related_count": max(len(graph["nodes"]) - 1, 0),
        "news_evidence": news_evidence or [],
    }


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@analyze_bp.post("/analyze/text")
@jwt_required()
def analyze_text():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return _error("Please enter some text, a claim, or a headline to analyze.")
    if len(text) > MAX_TEXT_LENGTH:
        return _error(f"Text is too long (max {MAX_TEXT_LENGTH} characters).")

    try:
        claim, best_match = analysis_service.analyze_new_text(
            text, origin="user_text", user_id=user_id, source_name="You",
        )
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _error(f"Analysis failed: {exc}", 500)

    _verify_and_attach(claim)
    news_evidence = _live_news_evidence(claim)

    db.session.add(SearchHistory(
        user_id=user_id, query_text=text[:600], query_type="text", result_claim_id=claim.id,
    ))
    db.session.commit()

    return jsonify(_claim_payload(claim, best_match, news_evidence)), 201


@analyze_bp.post("/analyze/image")
@jwt_required()
def analyze_image():
    user_id = int(get_jwt_identity())

    if "image" not in request.files:
        return _error("No image file was uploaded (expected form field 'image').")
    file = request.files["image"]
    if not file or file.filename == "":
        return _error("No image file was selected.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return _error(f"Unsupported image format '.{ext}'. Use PNG, JPG/JPEG, or WEBP.")

    file_bytes = file.read()
    if not file_bytes:
        return _error("The uploaded image appears to be empty.")

    try:
        ocr_result = extract_text_from_bytes(file_bytes)
    except OCRError as exc:
        return _error(str(exc), 422)

    extracted_text = ocr_result["text"]
    if len(extracted_text) > MAX_TEXT_LENGTH:
        extracted_text = extracted_text[:MAX_TEXT_LENGTH]

    try:
        claim, best_match = analysis_service.analyze_new_text(
            extracted_text, origin="user_image", user_id=user_id, source_name="Image upload",
        )
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _error(f"Analysis failed: {exc}", 500)

    _verify_and_attach(claim)
    news_evidence = _live_news_evidence(claim)

    db.session.add(SearchHistory(
        user_id=user_id, query_text=extracted_text[:600], query_type="image", result_claim_id=claim.id,
    ))
    db.session.commit()

    payload = _claim_payload(claim, best_match, news_evidence)
    payload["ocr"] = {"extracted_text": extracted_text, "confidence": ocr_result["confidence"]}
    return jsonify(payload), 201


@analyze_bp.post("/analyze/batch")
@jwt_required()
def analyze_batch():
    """Batch/dataset import — mirrors the original prototype's CSV/TXT
    upload feature, but now runs each row through the real NLP engine
    and persists it into the shared graph instead of a hand-rolled
    keyword matcher."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []

    if not isinstance(items, list) or not items:
        return _error("No claims were provided to analyze.")
    if len(items) > MAX_BATCH_ITEMS:
        return _error(f"Too many rows (max {MAX_BATCH_ITEMS} per batch).")

    results = []
    for item in items:
        claim_text = (item.get("claim") or "").strip()
        if not claim_text:
            continue
        source = (item.get("source") or "Dataset import").strip() or "Dataset import"
        published_at = _parse_date(item.get("date"))

        try:
            claim, best_match = analysis_service.analyze_new_text(
                claim_text[:MAX_TEXT_LENGTH], origin="user_text", user_id=user_id,
                source_name=source, published_at=published_at,
            )
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            continue

        results.append({
            "claim": claim.to_dict(),
            "best_match": {
                "claim_id": best_match[0].id,
                "similarity": round(best_match[1] * 100, 1),
                "narrative_label": best_match[0].narrative_label,
            } if best_match else None,
        })

    if not results:
        return _error("None of the rows contained usable claim text.")

    db.session.add(SearchHistory(
        user_id=user_id, query_text=f"Dataset import ({len(results)} claims)", query_type="dataset",
    ))
    db.session.commit()

    related = sum(1 for r in results if r["best_match"] and r["best_match"]["similarity"] >= 30)
    clusters = len({r["claim"]["cluster_id"] for r in results if r["claim"]["cluster_id"]})

    return jsonify({
        "results": results,
        "summary": {"claims_analyzed": len(results), "related_count": related, "clusters_found": clusters},
    }), 201


@analyze_bp.get("/claims/<int:claim_id>")
@jwt_required()
def get_claim(claim_id):
    claim = Claim.query.get(claim_id)
    if not claim:
        return _error("Claim not found.", 404)
    graph = analysis_service.build_graph_for_claim(claim_id)
    return jsonify({"claim": claim.to_dict(), "graph": graph}), 200


@analyze_bp.get("/history")
@jwt_required()
def history():
    user_id = int(get_jwt_identity())
    rows = (SearchHistory.query
            .filter_by(user_id=user_id)
            .order_by(SearchHistory.created_at.desc())
            .limit(25).all())

    claim_ids = [r.result_claim_id for r in rows if r.result_claim_id]
    claims = Claim.query.filter(Claim.id.in_(claim_ids)).all() if claim_ids else []
    claim_map = {c.id: c for c in claims}
    history_payload = []
    for row in rows:
        item = row.to_dict()
        claim = claim_map.get(row.result_claim_id)
        if claim:
            item["claim"] = {
                "id": claim.id,
                "text": claim.text,
                "cluster_id": claim.cluster_id,
                "narrative_label": claim.narrative_label,
                "verification": claim.to_dict().get("verification"),
            }
        else:
            item["claim"] = None
        history_payload.append(item)
    return jsonify({"history": history_payload}), 200
