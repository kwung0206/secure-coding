import pytest

from app import create_app
from app.extensions import db


def test_secret_key_required_outside_testing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(
            {
                "TESTING": False,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "UPLOAD_FOLDER": "/tmp/tiny-market-test-uploads",
            }
        )


def test_security_headers_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_enabled_when_secure_cookie_configured(tmp_path):
    secure_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SESSION_COOKIE_SECURE": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'secure.sqlite'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    with secure_app.app_context():
        db.create_all()
        response = secure_app.test_client().get("/")
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_internal_error_page_does_not_leak_exception_details(tmp_path):
    error_app = create_app(
        {
            "TESTING": False,
            "PROPAGATE_EXCEPTIONS": False,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'error.sqlite'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )

    @error_app.route("/boom")
    def boom():
        raise RuntimeError("sensitive-token-marker")

    with error_app.app_context():
        db.create_all()
        response = error_app.test_client().get("/boom")
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

    assert response.status_code == 500
    assert b"sensitive-token-marker" not in response.data
    assert b"500" in response.data
