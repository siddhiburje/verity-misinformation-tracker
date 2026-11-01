"""
Auth endpoints.

POST /api/auth/signup   -> create account, returns JWT
POST /api/auth/login    -> verify credentials, returns JWT
POST /api/auth/logout   -> stateless JWT, so this just tells the client
                            to discard its token (documented behavior)
GET  /api/auth/me       -> return the current user (requires JWT)

Passwords are hashed with bcrypt before storage. Plain-text passwords
are never persisted or logged.
"""
import re
import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _error(message, status=400):
    return jsonify({"error": message}), status


@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("confirmPassword") or ""

    if not name or len(name) < 2:
        return _error("Please enter your full name.")
    if not EMAIL_RE.match(email):
        return _error("Please enter a valid email address.")
    if len(password) < 8:
        return _error("Password must be at least 8 characters long.")
    if password != confirm:
        return _error("Passwords do not match.")

    if User.query.filter_by(email=email).first():
        return _error("An account with this email already exists.", 409)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(name=name, email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_public_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return _error("Email and password are required.")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        return _error("Invalid email or password.", 401)

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_public_dict()}), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    # JWTs are stateless in this project (no server-side session/blocklist),
    # so logout is enforced client-side by discarding the token. Documented
    # here rather than silently pretended to invalidate server-side.
    return jsonify({"message": "Logged out. Discard the token on the client."}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return _error("User not found.", 404)
    return jsonify({"user": user.to_public_dict()}), 200
