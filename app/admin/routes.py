from uuid import uuid4

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.admin.forms import (
    ReasonForm,
    ReportResolveForm,
    UserStatusForm,
    WalletGrantForm,
)
from app.decorators import admin_required
from app.extensions import db, limiter
from app.models import (
    AdminAuditLog,
    ChatMessage,
    PlazaMessage,
    Product,
    Report,
    User,
    Wallet,
    WalletTransaction,
    utcnow,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def index():
    pending_reports = Report.query.filter_by(status="PENDING").count()
    restricted_users = User.query.filter(User.status != "ACTIVE").count()
    hidden_products = Product.query.filter_by(status="HIDDEN").count()
    return render_template(
        "admin/index.html",
        pending_reports=pending_reports,
        restricted_users=restricted_users,
        hidden_products=hidden_products,
    )


@bp.route("/users")
@admin_required
def users():
    search = (request.args.get("q") or "").strip()
    query = User.query
    if search:
        query = query.filter(User.username.ilike(f"%{search}%"))
    users_list = query.order_by(User.created_at.desc()).limit(100).all()
    status_form = UserStatusForm()
    grant_form = WalletGrantForm(idempotency_key=uuid4().hex)
    return render_template(
        "admin/users.html",
        users=users_list,
        status_form=status_form,
        grant_form=grant_form,
    )


@bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_required
@limiter.limit("30 per minute")
def set_user_status(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = UserStatusForm()
    if not form.validate_on_submit():
        abort(400)
    if user.id == current_user.id and form.status.data != "ACTIVE":
        abort(400)
    if user.role == "ADMIN" and form.status.data != "ACTIVE" and _active_admin_count() <= 1:
        abort(400)
    user.status = form.status.data
    _audit("USER_STATUS", "USER", user.id, form.reason.data)
    db.session.commit()
    flash("사용자 상태를 변경했습니다.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/wallet-grant", methods=["POST"])
@admin_required
@limiter.limit("20 per minute")
def grant_wallet(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = WalletGrantForm()
    if not form.validate_on_submit():
        abort(400)
    if WalletTransaction.query.filter_by(idempotency_key=form.idempotency_key.data).first():
        abort(400)
    if user.wallet is None:
        user.wallet = Wallet(balance=0)
    if current_user.wallet is None:
        current_user.wallet = Wallet(balance=0)
    user.wallet.balance += form.amount.data
    db.session.add(
        WalletTransaction(
            sender_id=current_user.id,
            receiver_id=user.id,
            amount=form.amount.data,
            transaction_type="ADMIN_GRANT",
            status="SUCCESS",
            idempotency_key=form.idempotency_key.data,
            sender_balance_after=current_user.wallet.balance,
            receiver_balance_after=user.wallet.balance,
        )
    )
    _audit("WALLET_GRANT", "USER", user.id, form.reason.data)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400)
    flash("테스트 머니를 지급했습니다.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/products")
@admin_required
def products():
    search = (request.args.get("q") or "").strip()
    query = Product.query
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    products_list = query.order_by(Product.created_at.desc()).limit(100).all()
    reason_form = ReasonForm()
    return render_template("admin/products.html", products=products_list, reason_form=reason_form)


@bp.route("/products/<int:product_id>/hide", methods=["POST"])
@admin_required
def hide_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    reason = _required_reason()
    product.status = "HIDDEN"
    _audit("PRODUCT_HIDE", "PRODUCT", product.id, reason)
    db.session.commit()
    flash("상품을 숨겼습니다.", "success")
    return redirect(url_for("admin.products"))


@bp.route("/products/<int:product_id>/restore", methods=["POST"])
@admin_required
def restore_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    reason = _required_reason()
    product.status = "SELLING"
    _audit("PRODUCT_RESTORE", "PRODUCT", product.id, reason)
    db.session.commit()
    flash("상품을 복구했습니다.", "success")
    return redirect(url_for("admin.products"))


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_delete_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    reason = _required_reason()
    _audit("PRODUCT_DELETE", "PRODUCT", product.id, reason)
    db.session.delete(product)
    db.session.commit()
    flash("상품을 삭제했습니다.", "success")
    return redirect(url_for("admin.products"))


@bp.route("/reports")
@admin_required
def reports():
    reports_list = Report.query.order_by(Report.created_at.desc()).limit(100).all()
    form = ReportResolveForm()
    return render_template("admin/reports.html", reports=reports_list, form=form)


@bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
@admin_required
def resolve_report(report_id):
    report = db.session.get(Report, report_id) or abort(404)
    form = ReportResolveForm()
    if not form.validate_on_submit():
        abort(400)
    is_reapplying_resolved = report.status == "RESOLVED" and form.status.data == "RESOLVED"
    if report.status != "PENDING" and not is_reapplying_resolved:
        abort(400)
    if form.status.data == "RESOLVED":
        _apply_approved_report(report, form.reason.data)
        report.status = "RESOLVED"
        flash("신고를 승인하고 대상에 조치했습니다.", "success")
    else:
        report.status = "REJECTED"
        _audit("REPORT_REJECT", report.target_type, report.target_id, form.reason.data)
        flash("신고를 기각했습니다.", "success")
    _audit("REPORT_RESOLVE", "REPORT", report.id, form.reason.data)
    db.session.commit()
    return redirect(url_for("admin.reports"))


@bp.route("/messages/<string:message_kind>/<int:message_id>/hide", methods=["POST"])
@admin_required
def hide_message(message_kind, message_id):
    reason = _required_reason()
    if message_kind == "product":
        message = db.session.get(ChatMessage, message_id) or abort(404)
    elif message_kind == "plaza":
        message = db.session.get(PlazaMessage, message_id) or abort(404)
    else:
        abort(404)
    message.deleted_at = utcnow()
    _audit("MESSAGE_HIDE", message_kind.upper(), message_id, reason)
    db.session.commit()
    flash("메시지를 숨겼습니다.", "success")
    return redirect(url_for("admin.index"))


def _required_reason():
    reason = (request.form.get("reason") or "").strip()
    if len(reason) < 2:
        abort(400)
    return reason


def _audit(action, target_type, target_id, reason):
    db.session.add(
        AdminAuditLog(
            admin_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason.strip(),
        )
    )


def _apply_approved_report(report, reason):
    if report.target_type == "PRODUCT":
        product = db.session.get(Product, report.target_id) or abort(404)
        product.status = "HIDDEN"
    elif report.target_type == "USER":
        user = db.session.get(User, report.target_id) or abort(404)
        if user.id == current_user.id:
            abort(400)
        if user.role == "ADMIN" and user.status == "ACTIVE" and _active_admin_count() <= 1:
            abort(400)
        user.status = "SUSPENDED"
        for product in Product.query.filter_by(seller_id=user.id).all():
            product.status = "HIDDEN"
    elif report.target_type == "MESSAGE":
        message = db.session.get(ChatMessage, report.target_id) or abort(404)
        message.deleted_at = utcnow()
    else:
        abort(400)
    _audit("REPORT_APPROVE", report.target_type, report.target_id, reason)


def _active_admin_count():
    return User.query.filter_by(role="ADMIN", status="ACTIVE").count()
