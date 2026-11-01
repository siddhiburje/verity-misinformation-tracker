import os
from datetime import timedelta
from dotenv import load_dotenv

# Load backend/.env if present. Never raises if the file is missing —
# that just means the person hasn't configured anything yet (fine for
# a first run; secrets fall back to insecure development defaults with
# a printed warning — see app.py).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-insecure-secret-key")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # --- Database ---
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    _default_db_uri = "sqlite:///" + os.path.join(INSTANCE_DIR, "verity.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _default_db_uri)
    # Allow "sqlite:///verity.db" style relative URLs from .env to resolve
    # into the instance/ folder rather than the process CWD.
    if SQLALCHEMY_DATABASE_URI == "sqlite:///verity.db":
        SQLALCHEMY_DATABASE_URI = _default_db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT auth ---
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-insecure-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    JWT_TOKEN_LOCATION = ["headers"]

    # --- External APIs ---
    NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "").strip()
    FACTCHECK_API_KEY = os.environ.get("FACTCHECK_API_KEY", "").strip()

    # --- CORS ---
    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000"
    ).split(",")

    # --- Uploads ---
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB upload cap for OCR images
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
