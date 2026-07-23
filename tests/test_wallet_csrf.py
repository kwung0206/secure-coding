from threading import Barrier, Thread

import pytest

from app import create_app, format_datetime
from app.extensions import db
from app.models import User, Wallet, WalletTransaction
from app.wallet.forms import MAX_TEST_MONEY_AMOUNT
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
    tx = WalletTransaction.query.filter_by(idempotency_key="tx-1").first()
    assert tx is not None
    assert tx.sender_balance_after == 700
    assert tx.receiver_balance_after == 400


def test_wallet_history_shows_direction_counterparty_time_and_balance_after(client, app):
    sender = create_user("sender", balance=1000)
    receiver = create_user("receiver", balance=100)
    transfer_money(sender, receiver, 300, "tx-history")
    tx = WalletTransaction.query.filter_by(idempotency_key="tx-history").first()
    rendered_time = format_datetime(tx.created_at)

    login(client, sender.username)
    sender_response = client.get("/wallet/")
    assert sender_response.status_code == 200
    assert "출금".encode() in sender_response.data
    assert "받는 사람".encode() in sender_response.data
    assert b"receiver" in sender_response.data
    assert "-300 TM".encode() in sender_response.data
    assert "거래 후 잔액".encode() in sender_response.data
    assert "700 TM".encode() in sender_response.data
    assert rendered_time.encode() in sender_response.data
    client.post("/auth/logout")

    login(client, receiver.username)
    receiver_response = client.get("/wallet/")
    assert receiver_response.status_code == 200
    assert "입금".encode() in receiver_response.data
    assert "보낸 사람".encode() in receiver_response.data
    assert b"sender" in receiver_response.data
    assert "+300 TM".encode() in receiver_response.data
    assert "400 TM".encode() in receiver_response.data
    assert rendered_time.encode() in receiver_response.data


def test_admin_grant_history_shows_sender_and_receiver_balance_after(client, app):
    admin = create_user("admin", role="ADMIN", balance=0)
    user = create_user("receiver", balance=50)

    login(client, admin.username)
    response = client.post(
        f"/admin/users/{user.id}/wallet-grant",
        data={"amount": "200", "idempotency_key": "grant-history", "reason": "표시 확인"},
    )
    assert response.status_code == 302
    client.post("/auth/logout")

    tx = WalletTransaction.query.filter_by(idempotency_key="grant-history").first()
    assert tx.sender_balance_after == 0
    assert tx.receiver_balance_after == 250

    login(client, user.username)
    history_response = client.get("/wallet/")
    assert history_response.status_code == 200
    assert "입금".encode() in history_response.data
    assert "보낸 사람".encode() in history_response.data
    assert b"admin" in history_response.data
    assert "+200 TM".encode() in history_response.data
    assert "250 TM".encode() in history_response.data


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


def test_transfer_rejects_excessive_amount(app):
    sender = create_user("sender", balance=MAX_TEST_MONEY_AMOUNT)
    receiver = create_user("receiver", balance=0)

    with pytest.raises(ValueError, match="너무 큽니다"):
        transfer_money(sender, receiver, MAX_TEST_MONEY_AMOUNT + 1, "tx-too-large")

    assert db.session.get(Wallet, sender.id).balance == MAX_TEST_MONEY_AMOUNT
    assert db.session.get(Wallet, receiver.id).balance == 0
    assert WalletTransaction.query.filter_by(idempotency_key="tx-too-large").first() is None


def test_concurrent_transfers_cannot_double_spend(app):
    sender = create_user("sender", balance=100)
    receiver = create_user("receiver", balance=0)
    barrier = Barrier(2)
    results = []

    def attempt_transfer(key):
        with app.app_context():
            local_sender = User.query.filter_by(username="sender").first()
            local_receiver = User.query.filter_by(username="receiver").first()
            barrier.wait()
            try:
                transfer_money(local_sender, local_receiver, 80, key)
                results.append("success")
            except ValueError:
                results.append("rejected")
            finally:
                db.session.remove()

    threads = [
        Thread(target=attempt_transfer, args=("race-1",)),
        Thread(target=attempt_transfer, args=("race-2",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("success") == 1
    assert results.count("rejected") == 1
    assert db.session.get(Wallet, sender.id).balance == 20
    assert db.session.get(Wallet, receiver.id).balance == 80
    assert WalletTransaction.query.filter_by(transaction_type="TRANSFER").count() == 1


def test_wallet_total_balance_matches_admin_grants_after_transfer(client, app):
    create_user("admin", role="ADMIN", balance=0)
    sender = create_user("sender", balance=0)
    create_user("receiver", balance=0)

    login(client, "admin")
    grant_response = client.post(
        f"/admin/users/{sender.id}/wallet-grant",
        data={"amount": "1000", "idempotency_key": "grant-total-1", "reason": "총량 검증"},
    )
    assert grant_response.status_code == 302
    client.post("/auth/logout")

    login(client, "sender")
    transfer_response = client.post(
        "/wallet/transfer",
        data={"receiver_username": "receiver", "amount": "300", "idempotency_key": "tx-total-1"},
    )
    assert transfer_response.status_code == 302

    total_balance = db.session.query(db.func.sum(Wallet.balance)).scalar()
    issued_total = (
        db.session.query(db.func.sum(WalletTransaction.amount))
        .filter_by(transaction_type="ADMIN_GRANT", status="SUCCESS")
        .scalar()
    )
    assert total_balance == issued_total == 1000


def test_admin_wallet_grant_duplicate_key_rejected(client, app):
    admin = create_user("admin", role="ADMIN")
    user = create_user("user")
    login(client, admin.username)
    first = client.post(
        f"/admin/users/{user.id}/wallet-grant",
        data={"amount": "100", "idempotency_key": "grant-dupe", "reason": "첫 지급"},
    )
    second = client.post(
        f"/admin/users/{user.id}/wallet-grant",
        data={"amount": "200", "idempotency_key": "grant-dupe", "reason": "중복 지급"},
    )
    assert first.status_code == 302
    assert second.status_code == 400
    assert db.session.get(Wallet, user.id).balance == 100


def test_transfer_idempotency_key_is_global_across_users(client, app):
    sender = create_user("sender", balance=100)
    other_sender = create_user("other_sender", balance=100)
    receiver = create_user("receiver", balance=0)

    login(client, sender.username)
    first = client.post(
        "/wallet/transfer",
        data={"receiver_username": receiver.username, "amount": "40", "idempotency_key": "global-key"},
    )
    assert first.status_code == 302
    client.post("/auth/logout")

    login(client, other_sender.username)
    second = client.post(
        "/wallet/transfer",
        data={"receiver_username": receiver.username, "amount": "10", "idempotency_key": "global-key"},
    )
    assert second.status_code == 400
    assert db.session.get(Wallet, sender.id).balance == 60
    assert db.session.get(Wallet, other_sender.id).balance == 100
    assert db.session.get(Wallet, receiver.id).balance == 40


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
        db.engine.dispose()
