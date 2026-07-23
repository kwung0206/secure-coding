import os
from uuid import uuid4

import click
from flask import current_app

from app.extensions import db
from app.models import (
    AdminAuditLog,
    ChatMessage,
    ChatRoom,
    Product,
    Report,
    User,
    Wallet,
    WalletTransaction,
)
from app.security import validate_password_strength


def _password_from_option(option_value, env_name, prompt_label):
    password = option_value or os.environ.get(env_name)
    if not password:
        password = click.prompt(prompt_label, hide_input=True, confirmation_prompt=True)
    errors = validate_password_strength(password)
    if errors:
        raise click.ClickException(" ".join(errors))
    return password


def _ensure_wallet(user, balance=0):
    if user.wallet is None:
        user.wallet = Wallet(balance=balance)
    elif balance and user.wallet.balance < balance:
        user.wallet.balance = balance


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables for local development."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-admin")
    @click.option("--username", default=lambda: os.environ.get("ADMIN_USERNAME", "admin"), show_default="env ADMIN_USERNAME or admin")
    @click.option("--password", default=None, help="Admin password. Prefer ADMIN_PASSWORD env in shell history-sensitive environments.")
    def create_admin(username, password):
        """Create or update an administrator without hardcoding a password."""
        password = _password_from_option(password, "ADMIN_PASSWORD", "Admin password")
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, role="ADMIN", status="ACTIVE", region="운영")
            db.session.add(user)
        user.set_password(password)
        user.role = "ADMIN"
        user.status = "ACTIVE"
        _ensure_wallet(user)
        db.session.commit()
        click.echo(f"Admin user ready: {username}")

    @app.cli.command("seed")
    @click.option("--admin-password", default=None, help="Admin password. Prefer ADMIN_PASSWORD env.")
    @click.option("--user-password", default=None, help="Shared demo user password. Prefer SEED_USER_PASSWORD env.")
    def seed(admin_password, user_password):
        """Create development seed data without storing plaintext passwords."""
        admin_password = _password_from_option(admin_password, "ADMIN_PASSWORD", "Admin password")
        user_password = _password_from_option(user_password, "SEED_USER_PASSWORD", "Demo user password")

        if User.query.count():
            raise click.ClickException("Seed refused because users already exist.")

        admin = User(username="admin", role="ADMIN", region="Tiny 운영센터")
        admin.set_password(admin_password)
        db.session.add(admin)

        users = []
        for username, region, bio in [
            ("minji", "서울 성동구", "작고 좋은 물건을 오래 쓰는 편입니다."),
            ("junho", "서울 마포구", "전자기기와 책을 주로 나눕니다."),
            ("seoyeon", "경기 수원시", "동네에서 안전한 거래를 좋아합니다."),
        ]:
            user = User(username=username, region=region, bio=bio)
            user.set_password(user_password)
            _ensure_wallet(user, 50000)
            users.append(user)
            db.session.add(user)

        db.session.flush()
        _ensure_wallet(admin, 0)

        categories = ["디지털", "생활", "가구", "의류", "도서"]
        statuses = ["SELLING", "RESERVED", "SOLD"]
        for index in range(15):
            seller = users[index % len(users)]
            product = Product(
                seller=seller,
                title=f"Tiny 상품 {index + 1}",
                description="실습용 시드 상품입니다. 실제 결제 없이 테스트 머니만 사용합니다.",
                price=(index + 1) * 3000,
                category=categories[index % len(categories)],
                condition=["새상품", "좋음", "사용감 있음"][index % 3],
                region=seller.region,
                status=statuses[index % len(statuses)],
            )
            db.session.add(product)

        db.session.flush()
        first_product = Product.query.first()
        room = ChatRoom(product=first_product, seller=first_product.seller, buyer=users[1])
        db.session.add(room)
        db.session.flush()
        db.session.add(ChatMessage(room=room, sender=users[1], content="아직 거래 가능할까요?"))
        db.session.add(
            Report(
                reporter=users[2],
                target_type="PRODUCT",
                target_id=first_product.id,
                reason_category="부정확한 정보",
                reason_detail="시드 데이터 확인용 신고입니다.",
            )
        )
        db.session.add(
            WalletTransaction(
                sender=admin,
                receiver=users[0],
                amount=50000,
                transaction_type="ADMIN_GRANT",
                status="SUCCESS",
                idempotency_key=f"seed-{uuid4().hex}",
            )
        )
        db.session.add(
            AdminAuditLog(
                admin=admin,
                action="SEED_DATA_CREATED",
                target_type="SYSTEM",
                target_id=0,
                reason="개발용 시드 데이터 생성",
            )
        )
        db.session.commit()
        current_app.logger.info("Development seed data created without logging passwords.")
        click.echo("Seed data created.")

