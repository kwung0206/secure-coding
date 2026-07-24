from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(500), default="", nullable=False)
    profile_image = db.Column(db.String(255))
    region = db.Column(db.String(80), default="", nullable=False)
    region_verified_at = db.Column(db.DateTime(timezone=True))
    role = db.Column(db.String(20), default="USER", nullable=False)
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)
    manner_score = db.Column(db.Integer, default=36, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    products = db.relationship("Product", back_populates="seller", cascade="all, delete-orphan")
    favorites = db.relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    wallet = db.relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sent_messages = db.relationship("ChatMessage", back_populates="sender", foreign_keys="ChatMessage.sender_id")

    __table_args__ = (
        db.CheckConstraint("role in ('USER', 'ADMIN')", name="ck_users_role"),
        db.CheckConstraint(
            "status in ('ACTIVE', 'RESTRICTED', 'SUSPENDED')",
            name="ck_users_status",
        ),
        db.CheckConstraint("manner_score >= 0", name="ck_users_manner_score"),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.status != "SUSPENDED"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(2000), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    condition = db.Column(db.String(50), nullable=False)
    region = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default="SELLING", nullable=False, index=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    seller = db.relationship("User", back_populates="products")
    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.display_order",
    )
    favorites = db.relationship("Favorite", back_populates="product", cascade="all, delete-orphan")
    chat_rooms = db.relationship("ChatRoom", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        db.CheckConstraint("view_count >= 0", name="ck_products_view_count"),
        db.CheckConstraint(
            "status in ('SELLING', 'RESERVED', 'SOLD', 'HIDDEN')",
            name="ck_products_status",
        ),
    )

    @property
    def cover_image(self):
        return self.images[0] if self.images else None


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    stored_filename = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    product = db.relationship("Product", back_populates="images")


class Favorite(db.Model):
    __tablename__ = "favorites"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="favorites")
    product = db.relationship("Product", back_populates="favorites")

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_favorites_user_product"),
    )


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    product = db.relationship("Product", back_populates="chat_rooms")
    seller = db.relationship("User", foreign_keys=[seller_id])
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    messages = db.relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint(
            "product_id",
            "seller_id",
            "buyer_id",
            name="uq_chat_rooms_product_seller_buyer",
        ),
    )

    def includes_user(self, user_id):
        return self.seller_id == user_id or self.buyer_id == user_id


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True))

    room = db.relationship("ChatRoom", back_populates="messages")
    sender = db.relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])


class PlazaMessage(db.Model):
    __tablename__ = "plaza_messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True))

    sender = db.relationship("User")


class Block(db.Model):
    __tablename__ = "blocks"

    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    blocker = db.relationship("User", foreign_keys=[blocker_id])
    blocked = db.relationship("User", foreign_keys=[blocked_id])

    __table_args__ = (
        db.UniqueConstraint("blocker_id", "blocked_id", name="uq_blocks_pair"),
        db.CheckConstraint("blocker_id != blocked_id", name="ck_blocks_not_self"),
    )


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason_category = db.Column(db.String(80), nullable=False)
    reason_detail = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.String(20), default="PENDING", nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    reporter = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name="uq_reports_reporter_target",
        ),
        db.CheckConstraint(
            "target_type in ('USER', 'PRODUCT', 'MESSAGE')",
            name="ck_reports_target_type",
        ),
        db.CheckConstraint(
            "status in ('PENDING', 'RESOLVED', 'REJECTED')",
            name="ck_reports_status",
        ),
    )


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    transaction_product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    product = db.relationship("Product")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    reviewee = db.relationship("User", foreign_keys=[reviewee_id])

    __table_args__ = (
        db.CheckConstraint("rating between 1 and 5", name="ck_reviews_rating"),
        db.CheckConstraint("reviewer_id != reviewee_id", name="ck_reviews_not_self"),
    )


class Wallet(db.Model):
    __tablename__ = "wallets"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    balance = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship("User", back_populates="wallet")

    __table_args__ = (
        db.CheckConstraint("balance >= 0", name="ck_wallets_non_negative"),
    )


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    idempotency_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    sender_balance_after = db.Column(db.Integer)
    receiver_balance_after = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_wallet_transactions_amount"),
        db.CheckConstraint(
            "transaction_type in ('TRANSFER', 'ADMIN_GRANT')",
            name="ck_wallet_transactions_type",
        ),
        db.CheckConstraint(
            "status in ('SUCCESS', 'FAILED')",
            name="ck_wallet_transactions_status",
        ),
    )

    def direction_for(self, user_id):
        if self.transaction_type == "ADMIN_GRANT":
            if self.receiver_id == user_id:
                return "입금"
            if self.sender_id == user_id:
                return "지급"
        if self.sender_id == user_id:
            return "출금"
        if self.receiver_id == user_id:
            return "입금"
        return "관련 없음"

    def counterparty_for(self, user_id):
        direction = self.direction_for(user_id)
        if direction in {"출금", "지급"}:
            return self.receiver
        if direction == "입금":
            return self.sender
        return None

    def counterparty_label_for(self, user_id):
        direction = self.direction_for(user_id)
        if direction in {"출금", "지급"}:
            return "받는 사람"
        if direction == "입금":
            return "보낸 사람"
        return "상대"

    def balance_after_for(self, user_id):
        if self.receiver_id == user_id:
            return self.receiver_balance_after
        if self.sender_id == user_id:
            return self.sender_balance_after
        return None


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(40), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    admin = db.relationship("User")
