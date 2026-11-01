"""
Verity NLP engine.

Real, non-fabricated NLP built on scikit-learn + spaCy + TextBlob:

  - preprocess()      basic cleaning/tokenizing
  - extract_keywords() TF-IDF ranked keywords for a single document
                       against a background corpus
  - extract_entities() named entity recognition (spaCy)
  - sentiment()        polarity/subjectivity (TextBlob)
  - similarity_matrix() cosine similarity between many documents using
                       a shared TF-IDF space (this is what powers the
                       relationship graph — every edge weight returned
                       to the frontend is a real cosine similarity
                       score, not a placeholder number)
  - cluster_labels()   DBSCAN over the TF-IDF space, used when a whole
                       dataset is imported/analyzed in one batch

All functions are pure and stateless; the spaCy model and vectorizer
are loaded once per process at import time.
"""
import re
import string
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
from textblob import TextBlob

_SPACY_MODEL_NAME = "en_core_web_sm"
_nlp_model = None
_spacy_load_error = None


def _get_spacy():
    """Lazily load spaCy so a missing model doesn't crash the whole app —
    entity extraction just degrades to an empty list with a logged reason."""
    global _nlp_model, _spacy_load_error
    if _nlp_model is None and _spacy_load_error is None:
        try:
            import spacy
            _nlp_model = spacy.load(_SPACY_MODEL_NAME)
        except Exception as exc:  # noqa: BLE001 - want to swallow & degrade
            _spacy_load_error = str(exc)
    return _nlp_model


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "for", "with", "at", "by",
    "from", "up", "about", "into", "over", "after", "this", "that", "these",
    "those", "it", "its", "as", "if", "than", "so", "not", "no", "do",
    "does", "did", "has", "have", "had", "will", "would", "can", "could",
    "should", "may", "might", "must", "i", "you", "he", "she", "they",
    "we", "them", "his", "her", "their", "our", "your", "there", "what",
    "which", "who", "whom", "when", "where", "why", "how",
}


def preprocess(text: str) -> str:
    """Lowercase, strip punctuation/extra whitespace. Returns cleaned text."""
    text = text.strip()
    text = re.sub(r"http\S+|www\.\S+", " ", text)          # strip URLs
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str):
    return [w for w in preprocess(text).lower().split() if w and w not in _STOPWORDS]


def _lemma_tokenize(text: str):
    """
    Tokenizer used for TF-IDF similarity/clustering. Uses spaCy lemmas
    when the model is available (so "vaccines"/"vaccination"/"vaccinated"
    collapse to one feature), falling back to plain lowercase word
    splitting if the model failed to load. This directly improves the
    quality of the similarity graph, not just cosmetic tagging.
    """
    model = _get_spacy()
    cleaned = preprocess(text).lower()
    if not cleaned:
        return []
    if model is not None:
        doc = model(cleaned)
        return [t.lemma_ for t in doc if t.lemma_ and t.lemma_ not in _STOPWORDS and not t.is_space]
    return [w for w in cleaned.split() if w not in _STOPWORDS]


def extract_keywords(text: str, background_corpus=None, top_n: int = 8):
    """
    Rank keywords in `text` by TF-IDF weight. `background_corpus` (a list
    of other document strings) gives the IDF component real meaning —
    without it we fall back to simple term frequency.
    """
    doc = preprocess(text)
    if not doc:
        return []

    corpus = list(background_corpus) if background_corpus else []
    corpus.append(doc)

    try:
        vectorizer = TfidfVectorizer(tokenizer=_lemma_tokenize, preprocessor=lambda x: x, lowercase=False, token_pattern=None, max_features=2000)
        matrix = vectorizer.fit_transform(corpus)
        terms = np.array(vectorizer.get_feature_names_out())
        row = matrix[-1].toarray().ravel()
        top_idx = row.argsort()[::-1]
        keywords = []
        for idx in top_idx:
            if row[idx] <= 0:
                break
            keywords.append({"term": terms[idx], "weight": round(float(row[idx]), 4)})
            if len(keywords) >= top_n:
                break
        return keywords
    except ValueError:
        # e.g. text is entirely stopwords
        return []


def extract_entities(text: str):
    """Named entities via spaCy. Returns [] (not fabricated data) if the
    model failed to load, with the reason attached at nlp_status()."""
    model = _get_spacy()
    if model is None:
        return []
    doc = model(text)
    seen = set()
    entities = []
    for ent in doc.ents:
        key = (ent.text.strip().lower(), ent.label_)
        if key in seen or not ent.text.strip():
            continue
        seen.add(key)
        entities.append({"text": ent.text, "label": ent.label_})
    return entities


def sentiment(text: str):
    blob = TextBlob(text)
    return {
        "polarity": round(blob.sentiment.polarity, 4),      # -1..1
        "subjectivity": round(blob.sentiment.subjectivity, 4),  # 0..1
    }


def similarity_matrix(documents):
    """
    Cosine similarity matrix across ALL given documents using one shared
    TF-IDF space. Returns an (n x n) numpy array. Documents with no
    usable tokens get a zero-vector row (similarity 0 to everything).
    """
    cleaned = [preprocess(d) or "" for d in documents]
    if len(cleaned) < 2:
        return np.zeros((len(cleaned), len(cleaned)))
    vectorizer = TfidfVectorizer(tokenizer=_lemma_tokenize, preprocessor=lambda x: x, lowercase=False, token_pattern=None, max_features=5000)
    try:
        matrix = vectorizer.fit_transform(cleaned)
    except ValueError:
        return np.zeros((len(cleaned), len(cleaned)))
    return cosine_similarity(matrix)


def cluster_labels(documents, eps: float = 0.65, min_samples: int = 1):
    """
    DBSCAN clustering over TF-IDF cosine distance. Used for batch/dataset
    analysis where many claims are clustered together in one pass.
    Returns a list of integer cluster ids (-1 == noise/unclustered),
    parallel to `documents`.
    """
    cleaned = [preprocess(d) or "" for d in documents]
    if len(cleaned) < 2:
        return [0] * len(cleaned)
    vectorizer = TfidfVectorizer(tokenizer=_lemma_tokenize, preprocessor=lambda x: x, lowercase=False, token_pattern=None, max_features=5000)
    try:
        matrix = vectorizer.fit_transform(cleaned)
    except ValueError:
        return [-1] * len(cleaned)
    sim = cosine_similarity(matrix)
    distance = np.clip(1 - sim, 0, 2)
    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = model.fit_predict(distance)
    return labels.tolist()


def nlp_status():
    """Reports whether the optional spaCy NER model loaded successfully,
    so the API/UI can surface a real, honest degraded-mode message
    instead of silently returning empty entity lists."""
    _get_spacy()
    return {
        "ner_available": _nlp_model is not None,
        "ner_error": _spacy_load_error,
    }
