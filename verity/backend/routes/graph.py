"""
Graph / evolution / sources endpoints.

GET /api/graph/<id>       raw {nodes, edges} centered on a claim
GET /api/evolution/<id>   graph + chronologically sorted timeline
GET /api/sources/<id>     source metadata for a single claim
GET /api/nlp/status       whether the optional NER model loaded (used
                           by the frontend to show an honest banner if
                           entity extraction is running in degraded mode)
"""
from flask import Blueprint, jsonify
from datetime import datetime, timezone, timedelta
from collections import Counter
from flask_jwt_extended import jwt_required

from models import Claim
from services import analysis_service
from nlp import engine

graph_bp = Blueprint("graph", __name__, url_prefix="/api")


def _error(message, status=400):
    return jsonify({"error": message}), status


@graph_bp.get("/graph/<int:claim_id>")
@jwt_required()
def get_graph(claim_id):
    graph = analysis_service.build_graph_for_claim(claim_id)
    if graph is None:
        return _error("Claim not found.", 404)
    return jsonify(graph), 200


@graph_bp.get("/evolution/<int:claim_id>")
@jwt_required()
def get_evolution(claim_id):
    graph = analysis_service.build_graph_for_claim(claim_id, depth=2, max_nodes=60)
    if graph is None:
        return _error("Claim not found.", 404)
    timeline = sorted(graph["nodes"], key=lambda n: n["published_at"] or n["created_at"] or "")
    return jsonify({"graph": graph, "timeline": timeline}), 200


@graph_bp.get("/sources/<int:claim_id>")
@jwt_required()
def get_sources(claim_id):
    claim = Claim.query.get(claim_id)
    if not claim:
        return _error("Claim not found.", 404)
    graph = analysis_service.build_graph_for_claim(claim_id)
    sources = [
        {
            "claim_id": n["id"],
            "headline": n["text"][:140],
            "source_name": n["source_name"],
            "source_url": n["source_url"],
            "published_at": n["published_at"],
            "narrative_label": n["narrative_label"],
        }
        for n in graph["nodes"]
    ]
    return jsonify({"claim_id": claim_id, "sources": sources}), 200


@graph_bp.get("/nlp/status")
@jwt_required()
def nlp_status():
    return jsonify(engine.nlp_status()), 200


@graph_bp.get("/stats")
@jwt_required()
def stats():
    total_claims = Claim.query.count()
    clusters = (
        Claim.query.with_entities(Claim.cluster_id)
        .filter(Claim.cluster_id.isnot(None))
        .distinct()
        .count()
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = Claim.query.filter(Claim.created_at >= cutoff, Claim.cluster_id.isnot(None)).all()
    counts = Counter(c.cluster_id for c in recent)
    active = None
    if counts:
        cluster_id, count = counts.most_common(1)[0]
        sample = next((c for c in recent if c.cluster_id == cluster_id), None)
        active = {
            "cluster_id": cluster_id,
            "label": sample.narrative_label if sample else "Unclustered narrative",
            "count": count,
        }
    return jsonify({"total_claims": total_claims, "total_clusters": clusters, "most_active_cluster": active}), 200
