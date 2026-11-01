"""
News endpoints.

GET  /api/news/search?q=...   raw NewsAPI search (or offline fallback),
                               NOT persisted — just for browsing.
POST /api/news/track          body: {"query": "..."}. Fetches recent
                               articles for the topic, runs each one
                               through NLP, links them into the shared
                               claim graph, and returns the resulting
                               evolution graph + timeline for that
                               topic. This is the "topic -> live news
                               -> NLP -> evolution graph" flow.
"""
from flask import Blueprint, request, jsonify, current_app
import json
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import SearchHistory
from services import news_service, analysis_service

news_bp = Blueprint("news", __name__, url_prefix="/api/news")

MAX_ARTICLES_TO_INGEST = 8


def _error(message, status=400):
    return jsonify({"error": message}), status


@news_bp.get("/search")
@jwt_required()
def search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _error("Provide a search query, e.g. /api/news/search?q=election")

    api_key = current_app.config["NEWSAPI_KEY"]
    articles, is_live, warning = news_service.search_news(query, api_key)

    return jsonify({
        "query": query,
        "is_live": is_live,
        "warning": warning,
        "articles": articles,
    }), 200


@news_bp.post("/track")
@jwt_required()
def track_topic():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return _error("Provide a topic or query to track.")

    api_key = current_app.config["NEWSAPI_KEY"]
    articles, is_live, warning = news_service.search_news(query, api_key, page_size=MAX_ARTICLES_TO_INGEST)

    if not articles:
        return jsonify({
            "query": query, "is_live": is_live, "warning": warning,
            "articles": [], "graph": {"nodes": [], "edges": []}, "timeline": [],
        }), 200

    ingested_claim_ids = []
    for article in articles[:MAX_ARTICLES_TO_INGEST]:
        title = article.get("title") or ""
        description = article.get("description") or ""
        text = f"{title}. {description}".strip(". ").strip()
        if not text:
            continue
        published_at = None
        raw_date = article.get("published_at")
        if raw_date:
            from datetime import datetime
            try:
                published_at = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
                from datetime import timezone as tz
                published_at = published_at.replace(tzinfo=tz.utc)
            except ValueError:
                published_at = None

        claim, _best = analysis_service.analyze_new_text(
            text, origin="news", user_id=None,
            source_name=article.get("source_name") or "Unknown source",
            source_url=article.get("url"),
            published_at=published_at,
        )
        # Return the NLP metadata alongside each fetched article so the
        # frontend can group the actual NewsAPI results by narrative and
        # summarize their existing sentiment signal.
        article["claim_id"] = claim.id
        article["cluster_id"] = claim.cluster_id
        article["narrative_label"] = claim.narrative_label
        article["sentiment"] = json.loads(claim.sentiment_json) if claim.sentiment_json else None
        ingested_claim_ids.append(claim.id)

    db.session.add(SearchHistory(
        user_id=user_id, query_text=query, query_type="news",
        result_claim_id=ingested_claim_ids[0] if ingested_claim_ids else None,
    ))
    db.session.commit()

    # Merge the neighbor graphs of every ingested article into one
    # combined topic graph/timeline.
    nodes_by_id, edges_by_id = {}, {}
    for cid in ingested_claim_ids:
        g = analysis_service.build_graph_for_claim(cid, depth=1, max_nodes=40)
        if not g:
            continue
        for n in g["nodes"]:
            nodes_by_id[n["id"]] = n
        for e in g["edges"]:
            edges_by_id[e["id"]] = e

    nodes_sorted = sorted(nodes_by_id.values(), key=lambda n: n["published_at"] or n["created_at"] or "")

    return jsonify({
        "query": query,
        "is_live": is_live,
        "warning": warning,
        "articles": articles,
        "graph": {"nodes": nodes_sorted, "edges": list(edges_by_id.values())},
        "timeline": nodes_sorted,
    }), 200
