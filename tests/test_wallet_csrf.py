import pytest

from app import create_app
from app.extensions import db
from app.models import Wallet, WalletTransaction
from app.wallet.routes import transfer_money
from tests.conftest import create_user, login


def test_successful_transfer(client, app):
    sender = create_user("sender", balance=1000)
    receiver = create_user("receiver", balance=100)
    login(client, "sender")
    response = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "300", "idempotency_key": "tx-1"},
    )
    assert response.status_code == 302
    assert db.session.get(Wallet, sender.id).balance == 700
    assert db.session.get(Wallet, receiver.id).balance == 400
    assert WalletTransaction.query.filter_by(idempotency_key="tx-1").first() is not None


def test_transfer_rejects_insufficient_self_nonpositive_and_duplicate(client, app):
    create_user("sender", balance=100)
    create_user("receiver", balance=0)
    login(client, "sender")

    insufficient = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "200", "idempotency_key": "tx-low"},
    )
    assert insufficient.status_code == 400

    self_transfer = client.post(
        "/wallet/transfer",
        data={"receiver_username": "sender", "amount": "1", "idempotency_key": "tx-self"},
    )
    assert self_transfer.status_code == 400

    nonpositive = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "0", "idempotency_key": "tx-zero"},
    )
    assert nonpositive.status_code == 200

    ok = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "50", "idempotency_key": "tx-dupe"},
    )
    assert ok.status_code == 302
    duplicate = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "50", "idempotency_key": "tx-dupe"},
    )
    assert duplicate.status_code == 400


def test_transfer_rolls_back_on_commit_failure(app, monkeypatch):
    sender = create_user("sender", balance=1000)
    receiver = create_user("receiver", balance=0)

    def fail_commit():
        raise RuntimeError("forced failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        transfer_money(sender, receiver, 400, "tx-rollback")

    assert db.session.get(Wallet, sender.id).balance == 1000
    assert db.session.get(Wallet, receiver.id).balance == 0
    assert WalletTransaction.query.filter_by(idempotency_key="tx-rollback").first() is None


def test_missing_csrf_rejected(tmp_path):
    csrf_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "csrf-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.sqlite'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": True,
            "RATELIMIT_ENABLED": False,
        }
    )
    with csrf_app.app_context():
        db.create_all()
        response = csrf_app.test_client().post(
            "/auth/register",
            data={"username": "alice", "password": "GoodPass1!"},
        )
        assert response.status_code == 400
        db.session.remove()
        db.drop_all()
