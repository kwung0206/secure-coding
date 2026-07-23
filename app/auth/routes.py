from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm, RegisterForm
from app.extensions import db, limiter
from app.models import User, Wallet

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("users.me"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            form.username.errors.append("이미 사용할 수 없는 사용자명입니다.")
        else:
            user = User(username=username)
            user.set_password(form.password.data)
            user.wallet = Wallet(balance=0)
            db.session.add(user)
            db.session.commit()
            flash("회원가입이 완료되었습니다. 로그인해 주세요.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("users.me"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data) and user.status != "SUSPENDED":
            if user.wallet is None:
                user.wallet = Wallet(balance=0)
                db.session.commit()
            session.clear()
            login_user(user)
            flash("로그인되었습니다.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("users.me"))
        flash("사용자명 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("products.home"))

