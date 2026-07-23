from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.decorators import writable_account_required
from app.extensions import db
from app.models import Favorite, Product, ProductImage
from app.products.forms import ProductForm, ProductStatusForm
from app.security import ImageValidationError, remove_uploaded_file, save_validated_image

bp = Blueprint("products", __name__)

VISIBLE_PRODUCT_STATUSES = {"SELLING", "RESERVED", "SOLD"}
SELLER_PRODUCT_STATUSES = {"SELLING", "RESERVED", "SOLD"}


@bp.route("/")
def home():
    query = Product.query.filter(Product.status != "HIDDEN")

    search = (request.args.get("q") or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Product.title.ilike(pattern), Product.description.ilike(pattern)))

    category = (request.args.get("category") or "").strip()
    if category:
        query = query.filter(Product.category == category)

    region = (request.args.get("region") or "").strip()
    if region:
        query = query.filter(Product.region.ilike(f"%{region}%"))

    status = (request.args.get("status") or "").strip()
    if status in VISIBLE_PRODUCT_STATUSES:
        query = query.filter(Product.status == status)

    min_price = request.args.get("min_price", type=int)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    max_price = request.args.get("max_price", type=int)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    sort = request.args.get("sort", "latest")
    if sort == "price_asc":
        query = query.order_by(Product.price.asc(), Product.created_at.desc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc(), Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    page = max(request.args.get("page", 1, type=int) or 1, 1)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    query_args = request.args.to_dict()
    query_args.pop("page", None)
    return render_template(
        "products/home.html",
        pagination=pagination,
        products=pagination.items,
        query_args=query_args,
    )


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if "/" in filename or "\\" in filename or ".." in filename:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/products/new", methods=["GET", "POST"])
@writable_account_required
def create_product():
    form = ProductForm()
    if form.validate_on_submit():
        saved_filenames = []
        try:
            saved_filenames = _save_images_from_form(form)
        except ImageValidationError as exc:
            form.images.errors.append(str(exc))
            return render_template("products/form.html", form=form, product=None), 400

        product = Product(
            seller_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            price=form.price.data,
            category=form.category.data,
            condition=form.condition.data,
            region=form.region.data.strip(),
            status="SELLING",
        )
        for order, stored_filename in enumerate(saved_filenames):
            product.images.append(ProductImage(stored_filename=stored_filename, display_order=order))
        db.session.add(product)
        db.session.commit()
        flash("상품을 등록했습니다.", "success")
        return redirect(url_for("products.detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=None)


@bp.route("/products/<int:product_id>")
def detail(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.status == "HIDDEN" and not _can_admin_or_seller(product):
        abort(404)
    product.view_count += 1
    db.session.commit()
    status_form = ProductStatusForm(status=product.status if product.status in SELLER_PRODUCT_STATUSES else "SELLING")
    is_favorite = False
    if current_user.is_authenticated:
        is_favorite = Favorite.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    return render_template(
        "products/detail.html",
        product=product,
        status_form=status_form,
        is_favorite=is_favorite,
    )


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.seller_id != current_user.id:
        abort(403)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        try:
            saved_filenames = _save_images_from_form(form)
        except ImageValidationError as exc:
            form.images.errors.append(str(exc))
            return render_template("products/form.html", form=form, product=product), 400

        product.title = form.title.data.strip()
        product.description = form.description.data.strip()
        product.price = form.price.data
        product.category = form.category.data
        product.condition = form.condition.data
        product.region = form.region.data.strip()
        next_order = len(product.images)
        for offset, stored_filename in enumerate(saved_filenames):
            product.images.append(
                ProductImage(stored_filename=stored_filename, display_order=next_order + offset)
            )
        db.session.commit()
        flash("상품 정보를 수정했습니다.", "success")
        return redirect(url_for("products.detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=product)


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.seller_id != current_user.id and current_user.role != "ADMIN":
        abort(403)
    filenames = [image.stored_filename for image in product.images]
    db.session.delete(product)
    db.session.commit()
    for filename in filenames:
        remove_uploaded_file(current_app.config["UPLOAD_FOLDER"], filename)
    flash("상품을 삭제했습니다.", "success")
    return redirect(url_for("products.home"))


@bp.route("/products/<int:product_id>/status", methods=["POST"])
@login_required
def change_status(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.seller_id != current_user.id:
        abort(403)
    status = request.form.get("status")
    if status not in SELLER_PRODUCT_STATUSES:
        abort(400)
    product.status = status
    db.session.commit()
    flash("거래 상태를 변경했습니다.", "success")
    return redirect(url_for("products.detail", product_id=product.id))


@bp.route("/products/<int:product_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.status == "HIDDEN":
        abort(404)
    favorite = Favorite.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if favorite:
        db.session.delete(favorite)
        flash("관심 상품에서 제거했습니다.", "success")
    else:
        db.session.add(Favorite(user_id=current_user.id, product_id=product.id))
        flash("관심 상품에 추가했습니다.", "success")
    db.session.commit()
    return redirect(url_for("products.detail", product_id=product.id))


def _save_images_from_form(form):
    saved_filenames = []
    for file_storage in form.images.data or []:
        if not file_storage or not file_storage.filename:
            continue
        try:
            saved_filenames.append(
                save_validated_image(
                    file_storage,
                    current_app.config["UPLOAD_FOLDER"],
                    current_app.config["MAX_CONTENT_LENGTH"],
                )
            )
        except ImageValidationError:
            for filename in saved_filenames:
                remove_uploaded_file(current_app.config["UPLOAD_FOLDER"], filename)
            raise
    return saved_filenames


def _can_admin_or_seller(product):
    return current_user.is_authenticated and (
        current_user.role == "ADMIN" or current_user.id == product.seller_id
    )
