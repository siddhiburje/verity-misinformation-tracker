"""
SQLAlchemy models for Verity.

Tables
------
User            - registered accounts (bcrypt-hashed passwords only)
Claim           - every piece of text ever analyzed: reference/seed
                  narratives, user-submitted text, OCR-extracted text,
                  and articles pulled from NewsAPI all live here so the
                  similarity graph can be built across all of them.
Relationship    - a scored edge between two Claims, computed by the NLP
                  engine (never hand-authored / decorative).
SearchHistory   - a log of what a user searched/analyzed, for the
                  "recent searches" UI feature.
"""
from datetime import datetime, timezone
from extensions import db


def now_utc():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc)

    claims = db.relationship("Claim", backref="submitted_by", lazy="dynamic")
    searches = db.relationship("SearchHistory", backref="user", lazy="dynamic")

    def to_public_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class Claim(db.Model):
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # Where this claim/text came from.
    # one of: "reference", "user_text", "user_image", "news"
    origin = db.Column(db.String(20), nullable=False, default="user_text")

    source_name = db.Column(db.String(200))       # e.g. "Reuters", "Reference Dataset"
    source_url = db.Column(db.String(600))
    published_at = db.Column(db.DateTime)          # used for timeline ordering

    narrative_label = db.Column(db.String(160))    # human readable cluster name (seed data)
    cluster_id = db.Column(db.String(40))          # stable id, e.g. "cluster-02"

    # NLP outputs, stored as JSON text (SQLite has no native JSON type
    # in this SQLAlchemy version's simplest form, so we keep it as text
    # and (de)serialize in the NLP layer / routes).
    keywords_json = db.Column(db.Text)
    entities_json = db.Column(db.Text)
    sentiment_json = db.Column(db.Text)

    # Claim verification (separate from narrative/similarity matching
    # above): the outcome of looking this claim up against an
    # independent fact-check service. NULL until a single text/image
    # analysis has actually run verification on this claim (never set
    # for batch-imported or reference claims). See
    # services/verification_service.py for how these are populated —
    # this model only stores whatever that service actually returned.
    verification_status = db.Column(db.String(20))          # Supported | Contradicted | Mixed | Unverified
    verification_explanation = db.Column(db.Text)
    verification_sources_json = db.Column(db.Text)
    verification_checked_at = db.Column(db.DateTime)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "text": self.text,
            "origin": self.origin,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "narrative_label": self.narrative_label,
            "cluster_id": self.cluster_id,
            "keywords": json.loads(self.keywords_json) if self.keywords_json else [],
            "entities": json.loads(self.entities_json) if self.entities_json else [],
            "sentiment": json.loads(self.sentiment_json) if self.sentiment_json else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verification": {
                "status": self.verification_status,
                "explanation": self.verification_explanation,
                "sources": json.loads(self.verification_sources_json) if self.verification_sources_json else [],
                "checked_at": self.verification_checked_at.isoformat() if self.verification_checked_at else None,
            } if self.verification_status else None,
        }


class Relationship(db.Model):
    """A scored, computed edge between two claims in the evolution graph."""
    __tablename__ = "relationships"

    id = db.Column(db.Integer, primary_key=True)
    claim_a_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    claim_b_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False)
    similarity = db.Column(db.Float, nullable=False)
    relation_type = db.Column(db.String(40), default="related")  # related | same_narrative | variant
    created_at = db.Column(db.DateTime, default=now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.claim_a_id,
            "target": self.claim_b_id,
            "similarity": round(self.similarity, 4),
            "relation_type": self.relation_type,
        }


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    query_text = db.Column(db.String(600), nullable=False)
    query_type = db.Column(db.String(20), default="text")  # text | image | news
    result_claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query_text,
            "query_type": self.query_type,
            "result_claim_id": self.result_claim_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
