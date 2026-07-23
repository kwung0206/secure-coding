from app.extensions import db
from app.models import Product, ProductImage

from tests.conftest import create_product, create_user, image_tuple, login, product_form_data


def test_product_create_read_update_delete(client, app):
    create_user("seller")
    login(client, "seller")

    create_response = client.post("/products/new", data=product_form_data(), follow_redirects=False)
    assert create_response.status_code == 302
    product = Product.query.filter_by(title="테스트 상품").first()
    assert product is not None

    detail = client.get(f"/products/{product.id}")
    assert detail.status_code == 200
    assert "테스트 상품".encode() in detail.data

    edit_response = client.post(
        f"/products/{product.id}/edit",
        data=product_form_data(title="수정 상품"),
        follow_redirects=False,
    )
    assert edit_response.status_code == 302
    assert db.session.get(Product, product.id).title == "수정 상품"

    delete_response = client.post(f"/products/{product.id}/delete", follow_redirects=False)
    assert delete_response.status_code == 302
    assert db.session.get(Product, product.id) is None


def test_other_user_cannot_edit_or_delete_product(client, app):
    seller = create_user("seller")
    create_user("intruder")
    product = create_product(seller)
    login(client, "intruder")

    assert client.post(f"/products/{product.id}/edit", data=product_form_data()).status_code == 403
    assert client.post(f"/products/{product.id}/delete").status_code == 403


def test_product_search_filter_and_sort(client, app):
    seller = create_user("seller")
    create_product(seller, title="나무 의자", price=5000)
    create_product(seller, title="노트북", price=500000)

    response = client.get("/?q=의자&max_price=10000&sort=price_asc")
    assert response.status_code == 200
    assert "나무 의자".encode() in response.data
    assert "노트북".encode() not in response.data


def test_invalid_and_oversized_images_are_rejected(client, app):
    create_user("seller")
    login(client, "seller")

    bad = product_form_data(images=image_tuple(b"not-image", "bad.png"))
    response = client.post("/products/new", data=bad, content_type="multipart/form-data")
    assert response.status_code == 400

    too_large = product_form_data(images=image_tuple(b"\x89PNG\r\n\x1a\n" + b"0" * 8192, "big.png"))
    response = client.post("/products/new", data=too_large, content_type="multipart/form-data")
    assert response.status_code in {400, 413}


def test_valid_image_is_stored_with_uuid_name(client, app):
    create_user("seller")
    login(client, "seller")
    data = product_form_data(images=image_tuple())
    response = client.post("/products/new", data=data, content_type="multipart/form-data")
    assert response.status_code == 302
    image = ProductImage.query.first()
    assert image is not None
    assert image.stored_filename.endswith(".png")
    assert "tiny" not in image.stored_filename


def test_xss_payload_is_escaped(client, app):
    seller = create_user("seller")
    create_product(seller, title="<script>alert(1)</script>")
    response = client.get("/")
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data
