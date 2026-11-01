"""
Verity — application factory.

Serves both the JSON API (under /api/...) and the frontend (landing,
auth, dashboard pages) from a single Flask app/origin, so there is no
CORS complexity in the default setup.
"""
import os
from flask import Flask, render_template, jsonify

from config import Config
from extensions import db, jwt, cors


def create_app(config_class=Config):
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

    app = Flask(
        __name__,
        template_folder=os.path.join(frontend_dir, "templates"),
        static_folder=os.path.join(frontend_dir, "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # --- Blueprints (API) ---
    from routes.auth import auth_bp
    from routes.analyze import analyze_bp
    from routes.news import news_bp
    from routes.graph import graph_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(graph_bp)

    # --- Frontend pages ---
    @app.get("/")
    def landing():
        return render_template("landing.html")

    @app.get("/auth")
    def auth_page():
        return render_template("auth.html")

    @app.get("/app")
    def dashboard():
        return render_template("dashboard.html")

    # --- Health check (useful for verifying the server + DB are alive) ---
    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "newsapi_configured": bool(app.config["NEWSAPI_KEY"]),
        }), 200

    # --- Error handlers: never let the app return a blank page/crash trace ---
    @jwt.unauthorized_loader
    def handle_missing_auth(reason):
        return jsonify({"error": "Authentication required. Please log in again."}), 401

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        return jsonify({"error": "Your session is invalid. Please log in again."}), 401

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        return jsonify({"error": "Your session has expired. Please log in again."}), 401

    @app.errorhandler(413)
    def handle_too_large(exc):
        return jsonify({"error": "Uploaded file is too large (max 8 MB)."}), 413

    @app.errorhandler(404)
    def handle_not_found(exc):
        if _wants_json():
            return jsonify({"error": "Not found."}), 404
        return render_template("landing.html"), 404

    @app.errorhandler(500)
    def handle_server_error(exc):
        db.session.rollback()
        return jsonify({"error": "Something went wrong on the server. Please try again."}), 500

    def _wants_json():
        from flask import request
        return request.path.startswith("/api/")

    # --- DB init + reference-data seeding ---
    with app.app_context():
        db.create_all()
        from services.analysis_service import seed_reference_data_if_empty
        seed_reference_data_if_empty()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=(Config.FLASK_ENV == "development"), use_reloader=False)
