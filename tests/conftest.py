import io

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Product, User, Wallet

_png_buffer = io.BytesIO()
Image.new("RGB", (1, 1), color=(255, 255, 255)).save(_png_buffer, format="PNG")
PNG_BYTES = _png_buffer.getvalue()


@pytest.fixture()
def app(tmp_path):
    test_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "MAX_CONTENT_LENGTH": 4096,
        }
    )
    with test_app.app_context():
        db.create_all()
        from app.chat.routes import SOCKET_RATE_BUCKETS

        SOCKET_RATE_BUCKETS.clear()
        yield test_app
        SOCKET_RATE_BUCKETS.clear()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(username, password="GoodPass1!", role="USER", status="ACTIVE", balance=0, region="서울"):
    user = User(username=username, role=role, status=status, region=region)
    user.set_password(password)
    user.wallet = Wallet(balance=balance)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username, password="GoodPass1!"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def create_product(seller, title="아이패드", price=10000, status="SELLING"):
    product = Product(
        seller_id=seller.id,
        title=title,
        description="깨끗하게 사용한 테스트 상품입니다.",
        price=price,
        category="디지털",
        condition="좋음",
        region=seller.region or "서울",
        status=status,
    )
    db.session.add(product)
    db.session.commit()
    return product


def product_form_data(**overrides):
    data = {
        "title": "테스트 상품",
        "description": "테스트용 설명입니다.",
        "price": "12000",
        "category": "디지털",
        "condition": "좋음",
        "region": "서울 성동구",
    }
    data.update(overrides)
    return data


def image_tuple(data=PNG_BYTES, filename="tiny.png"):
    return (io.BytesIO(data), filename)
