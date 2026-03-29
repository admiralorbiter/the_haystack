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
    from routes.api import api_v1_bp

    app.register_blueprint(root_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    @app.before_request
    def log_page_view():
        from flask import request, session
        import uuid
        from models import db, PageView

        if request.path.startswith("/static") or request.path.startswith("/admin") or request.path.startswith("/api"):
            return

        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())
            
        try:
            pv = PageView(
                path=request.path,
                query_params=request.query_string.decode('utf-8')[:1000] if request.query_string else None,
                session_id=session.get("session_id")
            )
            db.session.add(pv)
            db.session.commit()
        except Exception:
            db.session.rollback()

    @app.template_filter('timeago')
    def timeago_filter(value):
        from datetime import datetime
        if not value: return ""
        if isinstance(value, str):
            try: value = datetime.strptime(value, "%Y-%m-%d")
            except: return value
        diff = datetime.now() - value
        days = diff.days
        if days <= 0: return "today"
        if days == 1: return "yesterday"
        if days < 7: return f"{days} days ago"
        if days < 14: return "1 week ago"
        if days < 30: return f"{days // 7} weeks ago"
        if days < 60: return "1 month ago"
        if days < 365: return f"{days // 30} months ago"
        return f"{days // 365} years ago"

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
