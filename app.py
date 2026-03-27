from flask import Flask, render_template
from flask_caching import Cache

from config import config

# Simple in-memory cache — no Redis / extra infra needed.
# Exported so routes can use @cache.memoize(timeout=86400).
cache = Cache()

def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # SimpleCache — in-process dict cache, 24h default TTL.
    # Upgrade path: swap CACHE_TYPE to 'RedisCache' with CACHE_REDIS_URL for production.
    app.config.setdefault("CACHE_TYPE", "SimpleCache")
    app.config.setdefault("CACHE_DEFAULT_TIMEOUT", 86400)  # 24h — IPEDS ships annually
    cache.init_app(app)

    # SQLAlchemy init
    from models import db
    db.init_app(app)

    # Register blueprints
    from routes import root_bp
    from routes.admin import admin_bp

    app.register_blueprint(root_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(debug=True)
