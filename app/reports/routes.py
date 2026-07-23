from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app.decorators import writable_account_required
from app.extensions import db, limiter
from app.models import ChatMessage, Product, Report, User
from app.reports.forms import ReportForm

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/new", methods=["GET", "POST"])
@writable_account_required
@limiter.limit("10 per hour")
def create_report():
    form = ReportForm()
    if request.method == "GET":
        form.target_type.data = (request.args.get("target_type") or "").upper()
        form.target_id.data = request.args.get("target_id") or ""

    if form.validate_on_submit():
        target_type = form.target_type.data.upper()
        try:
            target_id = int(form.target_id.data)
        except (TypeError, ValueError):
            abort(400)
        if target_id <= 0:
            abort(400)
        _assert_target_exists(target_type, target_id)
        if _is_self_report(target_type, target_id):
            abort(400)
        if Report.query.filter_by(
            reporter_id=current_user.id,
            target_type=target_type,
            target_id=target_id,
        ).first():
            flash("이미 같은 대상을 신고했습니다.", "warning")
            return redirect(_target_redirect(target_type, target_id))
        report = Report(
            reporter_id=current_user.id,
            target_type=target_type,
            target_id=target_id,
            reason_category=form.reason_category.data,
            reason_detail=form.reason_detail.data.strip(),
        )
        db.session.add(report)
        db.session.flush()
        _apply_report_threshold(target_type, target_id)
        db.session.commit()
        flash("신고가 접수되었습니다.", "success")
        return redirect(_target_redirect(target_type, target_id))

    return render_template("reports/form.html", form=form)


def _assert_target_exists(target_type, target_id):
    if target_type == "USER":
        db.session.get(User, target_id) or abort(404)
    elif target_type == "PRODUCT":
        db.session.get(Product, target_id) or abort(404)
    elif target_type == "MESSAGE":
        db.session.get(ChatMessage, target_id) or abort(404)
    else:
        abort(400)


def _is_self_report(target_type, target_id):
    if target_type == "USER":
        return target_id == current_user.id
    if target_type == "PRODUCT":
        product = db.session.get(Product, target_id)
        return product and product.seller_id == current_user.id
    if target_type == "MESSAGE":
        message = db.session.get(ChatMessage, target_id)
        return message and message.sender_id == current_user.id
    return False


def _apply_report_threshold(target_type, target_id):
    reporter_count = (
        db.session.query(func.count(func.distinct(Report.reporter_id)))
        .filter(
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status != "REJECTED",
        )
        .scalar()
    )
    if target_type == "PRODUCT" and reporter_count >= 3:
        product = db.session.get(Product, target_id)
        if product and product.status != "HIDDEN":
            product.status = "HIDDEN"
    if target_type == "USER" and reporter_count >= 5:
        user = db.session.get(User, target_id)
        if user and user.status == "ACTIVE":
            user.status = "RESTRICTED"


def _target_redirect(target_type, target_id):
    if target_type == "PRODUCT":
        return url_for("products.detail", product_id=target_id)
    if target_type == "USER":
        user = db.session.get(User, target_id)
        return url_for("users.public_profile", username=user.username)
    if target_type == "MESSAGE":
        message = db.session.get(ChatMessage, target_id)
        return url_for("chat.product_room", room_id=message.room_id)
    return url_for("products.home")
