"""
Shared Flask extension instances.

Kept in their own module (instead of inside app.py) so that model files
and route files can `from extensions import db` without circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
