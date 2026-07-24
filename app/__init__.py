from pathlib import Path
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from app.cli import register_commands
from app.config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate, socketio
from app.models import User, utcnow


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config_object:
        if isinstance(config_object, dict):
            app.config.update(config_object)
        else:
            app.config.from_object(config_object)

    validate_secret_key(app)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "로그인이 필요합니다."

    @login_manager.user_loader
    def load_user(user_id):
        if not str(user_id).isdigit():
            return None
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for("auth.login", next=request.full_path))

    register_blueprints(app)
    socketio.init_app(app)
    register_error_handlers(app)
    register_commands(app)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self' ws: wss:; frame-ancestors 'none'",
        )
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.context_processor
    def inject_globals():
        return {"format_datetime": format_datetime, "now": utcnow()}

    return app


def format_datetime(value):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")


def validate_secret_key(app):
    secret_key = app.config.get("SECRET_KEY")
    placeholder_values = {
        "",
        "change-me",
        "replace-with-a-long-random-secret",
        "secret",
        "secret" + "!",
    }
    if not secret_key or str(secret_key).strip().lower() in placeholder_values:
        raise RuntimeError(
            "SECRET_KEY is required. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )


def register_blueprints(app):
    from app.admin.routes import bp as admin_bp
    from app.auth.routes import bp as auth_bp
    from app.chat.routes import bp as chat_bp
    from app.products.routes import bp as products_bp
    from app.reports.routes import bp as reports_bp
    from app.users.routes import bp as users_bp
    from app.wallet.routes import bp as wallet_bp

    app.register_blueprint(products_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(admin_bp)


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", status_code=400, message="요청을 처리할 수 없습니다."), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", status_code=403, message="접근 권한이 없습니다."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", status_code=404, message="페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template("error.html", status_code=413, message="업로드 파일이 너무 큽니다."), 413

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template("error.html", status_code=429, message="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."), 429

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("error.html", status_code=500, message="서버 오류가 발생했습니다."), 500

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("error.html", status_code=400, message="CSRF 검증에 실패했습니다."), 400
