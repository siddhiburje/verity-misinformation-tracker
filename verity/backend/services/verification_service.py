"""
Claim verification via Google's Fact Check Tools API.

This is deliberately a SEPARATE concept from narrative/similarity
matching elsewhere in the app:

  - analysis_service.py answers "what similar claims/narratives exist
    in our own tracked data?" — that is TF-IDF text similarity, never
    evidence of truth or falsity.
  - This module answers "has an independent fact-checking publisher
    actually reviewed this claim, and what did they conclude?" — that
    is real third-party evidence, or an honest admission that none was
    found.

Hard rules enforced throughout this file:
  - Never fabricate a source, URL, publisher, rating, or explanation.
    Every field in a returned source dict comes directly from the
    Fact Check Tools API response.
  - Never treat the app's own narrative cluster, TF-IDF similarity
    score, or the offline NewsAPI sample data as evidence — this
    module never reads any of that; it only ever talks to the Fact
    Check Tools API.
  - Never invent a verdict. If the evidence is missing, ambiguous, or
    unavailable for any reason, the status is "Unverified" — never
    "Supported" or "Contradicted" by default/guesswork.
  - "No matching fact-check found" (we asked, nothing came back) and
    "fact-check service unavailable" (we couldn't ask at all) are
    always distinguishable in the returned explanation text.
"""
import requests
from datetime import datetime, timezone

FACTCHECK_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
REQUEST_TIMEOUT = 8  # seconds
MAX_CLAIMS_TO_INSPECT = 10

# Statuses a single publisher's textualRating can be classified into.
# Anything not matched by these keyword lists stays "unclear" rather
# than being force-fit into a bucket — see classify_rating().
_MIXED_TERMS = [
    "mixture", "mixed", "half true", "half false", "half-true", "half-false",
    "partly true", "partially true", "partly false", "partially false",
    "unproven", "misattributed", "outdated", "needs context", "missing context",
    "exaggerated", "overstated",
]
_CONTRADICTS_TERMS = [
    "false", "fake", "pants on fire", "hoax", "debunked", "incorrect",
    "not true", "manipulated", "altered", "fabricated", "misleading", "scam",
]
_SUPPORTS_TERMS = [
    "true", "correct", "accurate", "confirmed", "verified", "legit",
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _unverified(explanation: str) -> dict:
    """Every 'we could not establish a verdict' exit point funnels
    through here so the shape is always consistent and sources is
    always an empty list (never fabricated placeholders)."""
    return {
        "status": "Unverified",
        "explanation": explanation,
        "sources": [],
        "checked_at": _now_iso(),
    }


def classify_rating(textual_rating: str) -> str:
    """
    Maps one publisher's free-text rating (e.g. "False", "Mostly True",
    "Pants on Fire!") to 'supports' | 'contradicts' | 'mixed' | 'unclear'.
    Checked in this priority order because e.g. "Half True" contains
    the substring "true" and must not be misread as a plain "supports".
    Anything not recognized is 'unclear' — never guessed.
    """
    if not textual_rating:
        return "unclear"
    text = textual_rating.strip().lower()

    if any(term in text for term in _MIXED_TERMS):
        return "mixed"
    if any(term in text for term in _CONTRADICTS_TERMS):
        return "contradicts"
    if any(term in text for term in _SUPPORTS_TERMS):
        return "supports"
    return "unclear"


def verify_claim(claim_text: str, api_key: str) -> dict:
    """
    Looks up `claim_text` against Google's Fact Check Tools API and
    returns a structured verification result. Never raises for any
    expected failure mode (missing key, network error, empty/garbled
    response) — each one is reported as a distinct, honest
    "Unverified" explanation instead.
    """
    if not claim_text or not claim_text.strip():
        return _unverified("No claim text was available to verify.")

    if not api_key:
        return _unverified(
            "Fact-check API key is not configured. No fact-check lookup "
            "was performed, so this claim has not been checked against "
            "any evidence — this is not the same as evidence supporting it."
        )

    try:
        response = requests.get(
            FACTCHECK_ENDPOINT,
            params={
                "query": claim_text[:400],
                "key": api_key,
                "languageCode": "en",
                "pageSize": MAX_CLAIMS_TO_INSPECT,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        return _unverified(
            f"The fact-check service could not be reached ({exc.__class__.__name__}). "
            "This claim has not been checked — the service was unavailable, "
            "not that no evidence exists."
        )

    if response.status_code == 401 or response.status_code == 403:
        return _unverified(
            "The fact-check service rejected the configured API key. "
            "This claim has not been checked."
        )
    if response.status_code == 429:
        return _unverified(
            "The fact-check service's rate limit was reached. "
            "This claim has not been checked."
        )
    if response.status_code != 200:
        return _unverified(
            f"The fact-check service returned an unexpected error "
            f"(HTTP {response.status_code}). This claim has not been checked."
        )

    try:
        payload = response.json()
    except ValueError:
        return _unverified(
            "The fact-check service returned a response that could not be "
            "understood. This claim has not been checked."
        )

    raw_claims = payload.get("claims") or []
    if not raw_claims:
        return _unverified(
            "No matching fact-check was found for this claim by the "
            "fact-check service. This does not mean the claim is true — "
            "it means no independent review of it was found."
        )

    # Flatten every claimReview across every matched claim into real,
    # directly-sourced entries. A "claim" with no claimReview entries
    # contributes nothing (there's no actual review to point to).
    sources = []
    classifications = []
    for raw_claim in raw_claims[:MAX_CLAIMS_TO_INSPECT]:
        for review in raw_claim.get("claimReview") or []:
            publisher = (review.get("publisher") or {}).get("name")
            url = review.get("url")
            rating = review.get("textualRating")
            if not publisher or not url:
                continue  # don't surface a "source" we can't actually attribute/link
            sources.append({
                "publisher": publisher,
                "title": review.get("title") or raw_claim.get("text") or "(untitled)",
                "rating": rating,
                "url": url,
                "review_date": review.get("reviewDate"),
            })
            classifications.append(classify_rating(rating))

    if not sources:
        return _unverified(
            "The fact-check service returned results, but none included a "
            "usable, attributable publisher review. This claim has not "
            "been confidently checked."
        )

    supports = classifications.count("supports")
    contradicts = classifications.count("contradicts")
    mixed = classifications.count("mixed")

    if mixed > 0 or (supports > 0 and contradicts > 0):
        status = "Mixed"
        explanation = (
            f"Fact-checkers who reviewed this claim disagreed or found it "
            f"partially accurate: {supports} rating(s) leaning true, "
            f"{contradicts} leaning false, {mixed} explicitly mixed/partial, "
            f"out of {len(sources)} review(s) found."
        )
    elif contradicts > 0:
        status = "Contradicted"
        explanation = (
            f"{contradicts} of {len(sources)} fact-check review(s) found for "
            f"this claim rated it false or misleading."
        )
    elif supports > 0:
        status = "Supported"
        explanation = (
            f"{supports} of {len(sources)} fact-check review(s) found for "
            f"this claim rated it true or accurate."
        )
    else:
        # Reviews exist, but none had a rating we could confidently
        # classify — show the real sources, but do not guess a verdict.
        status = "Unverified"
        explanation = (
            f"{len(sources)} fact-check review(s) were found for this claim, "
            f"but their ratings could not be confidently classified as "
            f"supporting or contradicting it. See the original ratings below."
        )

    return {
        "status": status,
        "explanation": explanation,
        "sources": sources,
        "checked_at": _now_iso(),
    }
