from app.models import User
from tests.conftest import create_user, login


def test_register_success_and_password_is_hashed(client, app):
    response = client.post(
        "/auth/register",
        data={"username": "alice", "password": "GoodPass1!"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    user = User.query.filter_by(username="alice").first()
    assert user is not None
    assert user.password_hash != "GoodPass1!"
    assert user.check_password("GoodPass1!")
    assert user.wallet.balance == 0


def test_duplicate_username_rejected(client, app):
    create_user("alice")
    response = client.post(
        "/auth/register",
        data={"username": "alice", "password": "GoodPass1!"},
    )
    assert response.status_code == 200
    assert User.query.filter_by(username="alice").count() == 1


def test_login_success_and_failure_message_is_generic(client, app):
    create_user("alice")
    success = login(client, "alice")
    assert success.status_code == 302
    client.post("/auth/logout")

    failed = client.post(
        "/auth/login",
        data={"username": "missing", "password": "WrongPass1!"},
    )
    assert failed.status_code == 200
    assert "사용자명 또는 비밀번호가 올바르지 않습니다.".encode() in failed.data


def test_protected_page_requires_login(client, app):
    response = client.get("/me")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_profile_update_and_wrong_current_password_rejected(client, app):
    create_user("alice")
    login(client, "alice")
    response = client.post("/me/edit", data={"bio": "안전 거래", "region": "서울 마포구"})
    assert response.status_code == 302
    assert User.query.filter_by(username="alice").first().bio == "안전 거래"

    response = client.post(
        "/me/password",
        data={"current_password": "WrongPass1!", "new_password": "BetterPass1!"},
    )
    assert response.status_code == 400
    assert User.query.filter_by(username="alice").first().check_password("GoodPass1!")


def test_password_change_logs_out_current_session(client, app):
    create_user("alice")
    login(client, "alice")
    response = client.post(
        "/me/password",
        data={"current_password": "GoodPass1!", "new_password": "BetterPass1!"},
    )
    assert response.status_code == 302
    assert client.get("/me").status_code == 302
    assert User.query.filter_by(username="alice").first().check_password("BetterPass1!")


def test_logout_uses_post(client, app):
    create_user("alice")
    login(client, "alice")
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 302
