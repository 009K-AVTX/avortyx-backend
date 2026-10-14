"""Shared extension objects, created here and bound to the app in create_app()."""
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cors = CORS()
