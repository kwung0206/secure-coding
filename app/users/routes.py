from flask import Blueprint, abort, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, logout_user

from app.extensions import db
from app.models import Block, Product, Review, User, WalletTransaction
from app.security import ImageValidationError, save_validated_image
from app.users.forms import PasswordChangeForm, ProfileForm

bp = Blueprint("users", __name__)


@bp.route("/me")
@login_required
def me():
    selling_products = (
        Product.query.filter_by(seller_id=current_user.id)
        .order_by(Product.created_at.desc())
        .limit(20)
        .all()
    )
    favorite_products = [favorite.product for favorite in current_user.favorites]
    reviews = (
        Review.query.filter_by(reviewee_id=current_user.id)
        .order_by(Review.created_at.desc())
        .limit(20)
        .all()
    )
    transactions = (
        WalletTransaction.query.filter(
            (WalletTransaction.sender_id == current_user.id)
            | (WalletTransaction.receiver_id == current_user.id)
        )
        .order_by(WalletTransaction.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "users/me.html",
        selling_products=selling_products,
        favorite_products=favorite_products,
        reviews=reviews,
        transactions=transactions,
    )


@bp.route("/me/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.bio = (form.bio.data or "").strip()
        current_user.region = (form.region.data or "").strip()
        if form.profile_image.data and form.profile_image.data.filename:
            try:
                current_user.profile_image = save_validated_image(
                    form.profile_image.data,
                    current_app.config["UPLOAD_FOLDER"],
                    current_app.config["MAX_CONTENT_LENGTH"],
                )
            except ImageValidationError as exc:
                form.profile_image.errors.append(str(exc))
                return render_template("users/edit.html", form=form), 400
        db.session.commit()
        flash("프로필을 저장했습니다.", "success")
        return redirect(url_for("users.me"))
    return render_template("users/edit.html", form=form)


@bp.route("/me/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("현재 비밀번호가 올바르지 않습니다.")
            return render_template("users/password.html", form=form), 400
        current_user.set_password(form.new_password.data)
        db.session.commit()
        logout_user()
        session.clear()
        flash("비밀번호를 변경했습니다. 다시 로그인해 주세요.", "success")
        return redirect(url_for("auth.login"))
    return render_template("users/password.html", form=form)


@bp.route("/users/<username>")
def public_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    products = (
        Product.query.filter(
            Product.seller_id == user.id,
            Product.status != "HIDDEN",
        )
        .order_by(Product.created_at.desc())
        .limit(20)
        .all()
    )
    reviews = (
        Review.query.filter_by(reviewee_id=user.id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("users/public.html", profile_user=user, products=products, reviews=reviews)


@bp.route("/users/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    if user_id == current_user.id:
        abort(400)
    target = db.session.get(User, user_id) or abort(404)
    existing = Block.query.filter_by(blocker_id=current_user.id, blocked_id=target.id).first()
    if existing is None:
        db.session.add(Block(blocker_id=current_user.id, blocked_id=target.id))
        db.session.commit()
    flash("사용자를 차단했습니다.", "success")
    return redirect(url_for("users.public_profile", username=target.username))


@bp.route("/users/<int:user_id>/unblock", methods=["POST"])
@login_required
def unblock_user(user_id):
    target = db.session.get(User, user_id) or abort(404)
    existing = Block.query.filter_by(blocker_id=current_user.id, blocked_id=target.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    flash("차단을 해제했습니다.", "success")
    return redirect(url_for("users.public_profile", username=target.username))
