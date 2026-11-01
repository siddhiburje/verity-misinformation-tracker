"""
Analysis service — the glue between the database and the NLP engine.

This is where a submitted claim actually gets:
  1. stored,
  2. run through NLP (keywords / entities / sentiment),
  3. compared against every other claim already in the database
     (reference dataset + news articles + previously submitted claims)
     to build real similarity edges,
  4. assigned to an existing narrative cluster or flagged as a new/
     emerging one,
  5. turned into a graph + timeline payload for the frontend.

Every number returned here (similarity %, cluster membership, related
claim count) comes directly from nlp/engine.py — nothing is hand-typed
or decorative.
"""
import json
from datetime import datetime, timezone, timedelta

from extensions import db
from models import Claim, Relationship
from nlp import engine

RELATION_THRESHOLD = 0.12     # minimum cosine similarity to draw an edge at all
SAME_NARRATIVE_THRESHOLD = 0.30  # similarity above which we call it "same narrative"
MAX_GRAPH_NEIGHBORS = 8       # cap edges per new claim so the graph stays readable


def seed_reference_data_if_empty():
    """Populate the claims table with the curated reference dataset on
    first run, so the graph/cluster features have real data to compare
    against immediately. Safe to call on every startup — it's a no-op
    once seed data exists."""
    from nlp.seed_data import SEED_CLAIMS

    already_seeded = Claim.query.filter_by(origin="reference").first()
    if already_seeded:
        return

    for item in SEED_CLAIMS:
        claim = Claim(
            text=item["text"],
            origin="reference",
            source_name=item["source_name"],
            published_at=item["published_at"],
            narrative_label=item["narrative_label"],
            cluster_id=item["cluster_id"],
        )
        db.session.add(claim)
    db.session.commit()

    # Run NLP once over the seed set too, and build their relationship
    # edges, so the graph is fully connected from the very first search.
    all_claims = Claim.query.all()
    _annotate_nlp(all_claims)
    _build_relationships_for_all(all_claims)
    db.session.commit()


def _annotate_nlp(claims):
    """Fill in keywords/entities/sentiment for any claim missing them."""
    texts = [c.text for c in claims]
    for claim in claims:
        if claim.keywords_json:
            continue
        keywords = engine.extract_keywords(claim.text, background_corpus=texts)
        entities = engine.extract_entities(claim.text)
        senti = engine.sentiment(claim.text)
        claim.keywords_json = json.dumps(keywords)
        claim.entities_json = json.dumps(entities)
        claim.sentiment_json = json.dumps(senti)


def _build_relationships_for_all(claims):
    """Recompute the full pairwise similarity graph for a small seed
    set. Only used at initial seeding time (dataset is tiny)."""
    Relationship.query.delete()
    texts = [c.text for c in claims]
    sim = engine.similarity_matrix(texts)
    n = len(claims)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim[i][j])
            if score >= RELATION_THRESHOLD:
                rel_type = "same_narrative" if score >= SAME_NARRATIVE_THRESHOLD else "related"
                db.session.add(Relationship(
                    claim_a_id=claims[i].id, claim_b_id=claims[j].id,
                    similarity=score, relation_type=rel_type,
                ))


def analyze_new_text(text: str, origin: str, user_id: int = None,
                      source_name: str = None, source_url: str = None,
                      published_at: datetime = None):
    """
    The main entry point: takes a raw piece of text (typed, OCR'd, or
    pulled from a news article), stores it as a Claim, runs NLP on it,
    computes similarity against the rest of the corpus, links it into
    the narrative graph, and returns everything the frontend needs.
    """
    existing_claims = Claim.query.all()
    background_texts = [c.text for c in existing_claims]

    # Reuse a very recent near-duplicate submitted by the same user instead
    # of creating another visually identical claim node. This is deliberately
    # restricted to user-owned claims and a recent window; reference/news
    # material is never silently merged into a user's claim.
    if user_id is not None and origin in ("user_text", "user_image"):
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_user_claims = (
            Claim.query
            .filter(Claim.user_id == user_id, Claim.origin.in_(["user_text", "user_image"]))
            .filter(Claim.created_at >= cutoff)
            .order_by(Claim.created_at.desc())
            .limit(40)
            .all()
        )
        if recent_user_claims:
            scores = engine.similarity_matrix([c.text for c in recent_user_claims] + [text])
            if len(scores):
                best_index = max(range(len(recent_user_claims)), key=lambda i: float(scores[i][-1]))
                duplicate_score = float(scores[best_index][-1])
                if duplicate_score >= 0.95:
                    existing = recent_user_claims[best_index]
                    return existing, (existing, duplicate_score)

    keywords = engine.extract_keywords(text, background_corpus=background_texts)
    entities = engine.extract_entities(text)
    senti = engine.sentiment(text)

    claim = Claim(
        text=text,
        origin=origin,
        user_id=user_id,
        source_name=source_name or ("You" if origin in ("user_text", "user_image") else "Unknown"),
        source_url=source_url,
        published_at=published_at or datetime.now(timezone.utc),
        keywords_json=json.dumps(keywords),
        entities_json=json.dumps(entities),
        sentiment_json=json.dumps(senti),
    )
    db.session.add(claim)
    db.session.flush()  # get claim.id without a full commit yet

    best_match = None
    if existing_claims:
        all_texts = background_texts + [text]
        sim_matrix = engine.similarity_matrix(all_texts)
        new_row = sim_matrix[-1][:-1]  # similarity of new claim vs each existing claim

        scored = sorted(
            zip(existing_claims, new_row.tolist()),
            key=lambda pair: pair[1],
            reverse=True,
        )

        for other_claim, score in scored[:MAX_GRAPH_NEIGHBORS]:
            if score < RELATION_THRESHOLD:
                continue
            rel_type = "same_narrative" if score >= SAME_NARRATIVE_THRESHOLD else "related"
            db.session.add(Relationship(
                claim_a_id=claim.id, claim_b_id=other_claim.id,
                similarity=score, relation_type=rel_type,
            ))
            if best_match is None or score > best_match[1]:
                best_match = (other_claim, score)

    if best_match and best_match[1] >= SAME_NARRATIVE_THRESHOLD and best_match[0].cluster_id:
        claim.cluster_id = best_match[0].cluster_id
        claim.narrative_label = best_match[0].narrative_label
    elif best_match:
        claim.cluster_id = best_match[0].cluster_id or f"cluster-claim-{best_match[0].id}"
        claim.narrative_label = best_match[0].narrative_label or "Related narrative (weak match)"
    else:
        claim.cluster_id = f"cluster-claim-{claim.id}"
        claim.narrative_label = "New / unclustered narrative"

    db.session.commit()
    return claim, best_match


def build_graph_for_claim(claim_id: int, depth: int = 1, max_nodes: int = 40):
    """
    Builds a node/edge graph payload centered on `claim_id`, following
    Relationship edges outward up to `depth` hops (default: direct
    neighbors only, which is what the "Analyze" result view needs).
    """
    center = Claim.query.get(claim_id)
    if center is None:
        return None

    visited_ids = {claim_id}
    frontier = {claim_id}
    edges = []

    for _ in range(max(depth, 1)):
        if not frontier or len(visited_ids) >= max_nodes:
            break
        rels = Relationship.query.filter(
            db.or_(
                Relationship.claim_a_id.in_(frontier),
                Relationship.claim_b_id.in_(frontier),
            )
        ).all()
        next_frontier = set()
        for rel in rels:
            edges.append(rel)
            for cid in (rel.claim_a_id, rel.claim_b_id):
                if cid not in visited_ids and len(visited_ids) < max_nodes:
                    visited_ids.add(cid)
                    next_frontier.add(cid)
        frontier = next_frontier

    # Include the rest of the center claim's narrative cluster when available.
    # This makes the evolution view show the actual narrative family even when
    # TF-IDF did not create a direct edge for every member. These are visual
    # cluster members, not invented similarity relationships.
    if center.cluster_id and len(visited_ids) < max_nodes:
        cluster_members = (
            Claim.query
            .filter(Claim.cluster_id == center.cluster_id, Claim.id.notin_(visited_ids))
            .order_by(Claim.published_at.asc(), Claim.created_at.asc())
            .limit(max_nodes - len(visited_ids))
            .all()
        )
        visited_ids.update(c.id for c in cluster_members)

    nodes = Claim.query.filter(Claim.id.in_(visited_ids)).all()
    # De-duplicate edges (a relationship might get pulled in from both endpoints' queries)
    seen_edge_ids = set()
    unique_edges = []
    for e in edges:
        if e.id not in seen_edge_ids:
            seen_edge_ids.add(e.id)
            unique_edges.append(e)

    nodes_sorted = sorted(nodes, key=lambda c: c.published_at or c.created_at)
    return {
        "center_id": claim_id,
        "nodes": [n.to_dict() for n in nodes_sorted],
        "edges": [e.to_dict() for e in unique_edges],
    }
