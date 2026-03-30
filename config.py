import os

basedir = os.path.abspath(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Required environment variables (set these on the server, never in code)
# ---------------------------------------------------------------------------
# SECRET_KEY   — random secret for session signing
# DATABASE_URL — SQLAlchemy connection string, e.g.:
#                  sqlite:////home/jlane/the_haystack/db/haystack.db
#                  postgresql://user:pass@host/dbname
# FLASK_ENV    — "development" | "production"  (consumed by run.py / WSGI)
# ---------------------------------------------------------------------------


class Config:
    """Shared defaults for all environments."""
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(
        basedir, "db", "haystack.db"
    )


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(
        basedir, "db", "haystack.db"
    )

    @staticmethod
    def init_app(app):
        # Guard runs at app-startup, not at import time, so dev machines
        # can import config without SECRET_KEY being set.
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY environment variable is not set. "
                "Set it on PythonAnywhere via the 'Web' tab → 'Environment variables', "
                "or load a .env file before startup."
            )


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
