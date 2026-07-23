from time import monotonic

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_socketio import emit, join_room
from sqlalchemy import or_

from app.decorators import writable_account_required
from app.extensions import db, limiter, socketio
from app.models import Block, ChatMessage, ChatRoom, PlazaMessage, Product, utcnow

bp = Blueprint("chat", __name__, url_prefix="/chat")

MAX_MESSAGE_LENGTH = 500
SOCKET_MESSAGE_LIMIT = 5
SOCKET_RATE_WINDOW_SECONDS = 2
SOCKET_RATE_BUCKETS = {}


@bp.route("/products/<int:product_id>/start", methods=["POST"])
@writable_account_required
@limiter.limit("20 per minute")
def start_product_chat(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.status == "HIDDEN":
        abort(404)
    if product.seller_id == current_user.id:
        abort(400)
    if is_blocked_between(current_user.id, product.seller_id):
        abort(403)
    room = ChatRoom.query.filter_by(
        product_id=product.id,
        seller_id=product.seller_id,
        buyer_id=current_user.id,
    ).first()
    if room is None:
        room = ChatRoom(product_id=product.id, seller_id=product.seller_id, buyer_id=current_user.id)
        db.session.add(room)
        db.session.commit()
    return redirect(url_for("chat.product_room", room_id=room.id))


@bp.route("/rooms/<int:room_id>")
@login_required
def product_room(room_id):
    room = db.session.get(ChatRoom, room_id) or abort(404)
    if not room.includes_user(current_user.id) and current_user.role != "ADMIN":
        abort(403)
    messages = (
        ChatMessage.query.filter_by(room_id=room.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return render_template("chat/room.html", room=room, messages=messages)


@bp.route("/rooms/<int:room_id>/messages", methods=["POST"])
@writable_account_required
@limiter.limit("30 per minute")
def post_product_message(room_id):
    room = db.session.get(ChatRoom, room_id) or abort(404)
    if not room.includes_user(current_user.id):
        abort(403)
    other_user_id = room.buyer_id if current_user.id == room.seller_id else room.seller_id
    if is_blocked_between(current_user.id, other_user_id):
        abort(403)
    content = (request.form.get("content") or "").strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        abort(400)
    message = ChatMessage(room_id=room.id, sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    return redirect(url_for("chat.product_room", room_id=room.id))


@bp.route("/plaza")
@login_required
def plaza():
    messages = PlazaMessage.query.order_by(PlazaMessage.created_at.desc()).limit(80).all()
    messages.reverse()
    return render_template("chat/plaza.html", messages=messages)


@bp.route("/plaza/messages", methods=["POST"])
@writable_account_required
@limiter.limit("30 per minute")
def post_plaza_message():
    content = (request.form.get("content") or "").strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        abort(400)
    message = PlazaMessage(sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    return redirect(url_for("chat.plaza"))


def is_blocked_between(user_id, other_user_id):
    return (
        Block.query.filter(
            or_(
                (Block.blocker_id == user_id) & (Block.blocked_id == other_user_id),
                (Block.blocker_id == other_user_id) & (Block.blocked_id == user_id),
            )
        ).first()
        is not None
    )


@socketio.on("join_product_room")
def socket_join_product_room(data):
    if not current_user.is_authenticated:
        _emit_chat_error("authentication required")
        return
    room = _get_socket_room(data)
    if room is None or not room.includes_user(current_user.id):
        _emit_chat_error("forbidden")
        return
    join_room(f"product-{room.id}")
    emit("joined", {"room_id": room.id})


@socketio.on("send_product_message")
def socket_send_product_message(data):
    if not current_user.is_authenticated or current_user.status != "ACTIVE":
        _emit_chat_error("forbidden")
        return
    room = _get_socket_room(data)
    if room is None or not room.includes_user(current_user.id):
        _emit_chat_error("forbidden")
        return
    other_user_id = room.buyer_id if current_user.id == room.seller_id else room.seller_id
    if is_blocked_between(current_user.id, other_user_id):
        _emit_chat_error("blocked")
        return
    if _socket_rate_limited(f"product:{room.id}"):
        _emit_chat_error("rate limited")
        return
    content = (data.get("content") or "").strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        _emit_chat_error("invalid message")
        return
    message = ChatMessage(room_id=room.id, sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    emit(
        "product_message",
        {
            "id": message.id,
            "room_id": room.id,
            "sender": current_user.username,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
        room=f"product-{room.id}",
    )


@socketio.on("join_plaza")
def socket_join_plaza():
    if not current_user.is_authenticated:
        _emit_chat_error("authentication required")
        return
    join_room("plaza")
    emit("joined", {"room": "plaza"})


@socketio.on("send_plaza_message")
def socket_send_plaza_message(data):
    if not current_user.is_authenticated or current_user.status != "ACTIVE":
        _emit_chat_error("forbidden")
        return
    if _socket_rate_limited("plaza"):
        _emit_chat_error("rate limited")
        return
    content = (data.get("content") or "").strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        _emit_chat_error("invalid message")
        return
    message = PlazaMessage(sender_id=current_user.id, content=content, created_at=utcnow())
    db.session.add(message)
    db.session.commit()
    emit(
        "plaza_message",
        {
            "id": message.id,
            "sender": current_user.username,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
        room="plaza",
    )


def _get_socket_room(data):
    try:
        room_id = int(data.get("room_id", 0) or 0)
    except (TypeError, ValueError):
        return None
    return db.session.get(ChatRoom, room_id)


def _socket_rate_limited(scope):
    now = monotonic()
    key = (current_user.get_id(), scope)
    recent_hits = [
        timestamp
        for timestamp in SOCKET_RATE_BUCKETS.get(key, [])
        if now - timestamp < SOCKET_RATE_WINDOW_SECONDS
    ]
    if len(recent_hits) >= SOCKET_MESSAGE_LIMIT:
        SOCKET_RATE_BUCKETS[key] = recent_hits
        return True
    recent_hits.append(now)
    SOCKET_RATE_BUCKETS[key] = recent_hits
    return False


def _emit_chat_error(message):
    emit("chat_error", {"message": message})
