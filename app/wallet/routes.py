from uuid import uuid4

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.decorators import writable_account_required
from app.extensions import db, limiter
from app.models import User, Wallet, WalletTransaction
from app.wallet.forms import TransferForm

bp = Blueprint("wallet", __name__, url_prefix="/wallet")


@bp.route("/")
@login_required
def dashboard():
    _ensure_wallet(current_user)
    transactions = (
        WalletTransaction.query.filter(
            (WalletTransaction.sender_id == current_user.id)
            | (WalletTransaction.receiver_id == current_user.id)
        )
        .order_by(WalletTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    form = TransferForm(idempotency_key=uuid4().hex)
    return render_template("wallet/dashboard.html", form=form, transactions=transactions)


@bp.route("/transfer", methods=["GET", "POST"])
@writable_account_required
@limiter.limit("10 per minute")
def transfer():
    _ensure_wallet(current_user)
    form = TransferForm()
    if form.validate_on_submit():
        receiver = User.query.filter_by(username=form.receiver_username.data.strip()).first()
        if receiver is None:
            form.receiver_username.errors.append("받는 사용자를 확인할 수 없습니다.")
            return render_template("wallet/transfer.html", form=form), 400
        try:
            transfer_money(
                sender=current_user,
                receiver=receiver,
                amount=form.amount.data,
                idempotency_key=form.idempotency_key.data,
            )
        except ValueError as exc:
            form.amount.errors.append(str(exc))
            return render_template("wallet/transfer.html", form=form), 400
        flash("테스트 머니를 보냈습니다.", "success")
        return redirect(url_for("wallet.dashboard"))
    if not form.idempotency_key.data:
        form.idempotency_key.data = uuid4().hex
    return render_template("wallet/transfer.html", form=form)


def transfer_money(sender, receiver, amount, idempotency_key):
    if sender.id == receiver.id:
        raise ValueError("자기 자신에게는 송금할 수 없습니다.")
    if amount is None or amount <= 0:
        raise ValueError("송금 금액은 1 이상이어야 합니다.")
    if not idempotency_key:
        raise ValueError("요청 키가 필요합니다.")
    sender_id = sender.id
    receiver_id = receiver.id
    if WalletTransaction.query.filter_by(idempotency_key=idempotency_key).first():
        raise ValueError("이미 처리된 송금 요청입니다.")

    try:
        _ensure_wallet_record(sender_id)
        _ensure_wallet_record(receiver_id)
        debit_result = db.session.execute(
            db.update(Wallet)
            .where(Wallet.user_id == sender_id, Wallet.balance >= amount)
            .values(balance=Wallet.balance - amount)
        )
        if debit_result.rowcount != 1:
            raise ValueError("잔액이 부족합니다.")
        credit_result = db.session.execute(
            db.update(Wallet)
            .where(Wallet.user_id == receiver_id)
            .values(balance=Wallet.balance + amount)
        )
        if credit_result.rowcount != 1:
            raise ValueError("받는 사용자의 지갑을 확인할 수 없습니다.")
        tx = WalletTransaction(
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            transaction_type="TRANSFER",
            status="SUCCESS",
            idempotency_key=idempotency_key,
        )
        db.session.add(tx)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("이미 처리된 송금 요청입니다.") from exc
    except ValueError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise
    return tx


def _ensure_wallet(user):
    if user.wallet is None:
        user.wallet = Wallet(balance=0)
        db.session.add(user.wallet)
        db.session.flush()


def _ensure_wallet_record(user_id):
    if db.session.get(Wallet, user_id) is None:
        db.session.add(Wallet(user_id=user_id, balance=0))
        db.session.flush()
