from flask import Flask, render_template

from config import config


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

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
