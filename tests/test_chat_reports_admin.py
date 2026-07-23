from app.extensions import db
from app.models import (
    AdminAuditLog,
    Block,
    ChatMessage,
    ChatRoom,
    Product,
    Report,
    User,
)
from tests.conftest import create_product, create_user, login


def test_product_chat_room_permissions_and_sender_spoofing(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    create_user("outsider")
    product = create_product(seller)

    login(client, "buyer")
    response = client.post(f"/chat/products/{product.id}/start")
    assert response.status_code == 302
    room = ChatRoom.query.filter_by(product_id=product.id, buyer_id=buyer.id).first()
    assert room is not None

    client.post(
        f"/chat/rooms/{room.id}/messages",
        data={"content": "제가 보낸 메시지입니다.", "username": "seller", "sender_id": seller.id},
    )
    message = ChatMessage.query.first()
    assert message.sender_id == buyer.id

    client.post("/auth/logout")
    login(client, "outsider")
    assert client.get(f"/chat/rooms/{room.id}").status_code == 403


def test_chat_room_list_is_visible_to_seller_and_buyer(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    outsider = create_user("outsider")
    product = create_product(seller, title="채팅 테스트 상품")
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.flush()
    db.session.add(ChatMessage(room_id=room.id, sender_id=buyer.id, content="구매 가능할까요?"))
    db.session.commit()

    login(client, seller.username)
    seller_response = client.get("/chat/rooms")
    assert seller_response.status_code == 200
    assert "채팅 테스트 상품".encode() in seller_response.data
    assert b"buyer" in seller_response.data
    client.post("/auth/logout")

    login(client, buyer.username)
    buyer_response = client.get("/chat/rooms")
    assert buyer_response.status_code == 200
    assert "채팅 테스트 상품".encode() in buyer_response.data
    assert b"seller" in buyer_response.data
    client.post("/auth/logout")

    login(client, outsider.username)
    outsider_response = client.get("/chat/rooms")
    assert outsider_response.status_code == 200
    assert "채팅 테스트 상품".encode() not in outsider_response.data


def test_product_chat_room_loads_realtime_client(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, buyer.username)
    response = client.get(f"/chat/rooms/{room.id}")

    assert response.status_code == 200
    assert b"data-realtime-chat" in response.data
    assert b'data-chat-kind="product"' in response.data
    assert b"/static/js/realtime-chat.js" in response.data


def test_plaza_loads_realtime_client(client, app):
    create_user("buyer")

    login(client, "buyer")
    response = client.get("/chat/plaza")

    assert response.status_code == 200
    assert b"data-realtime-chat" in response.data
    assert b'data-chat-kind="plaza"' in response.data
    assert b"/static/js/realtime-chat.js" in response.data


def test_seller_cannot_chat_with_self(client, app):
    seller = create_user("seller")
    product = create_product(seller)
    login(client, "seller")
    assert client.post(f"/chat/products/{product.id}/start").status_code == 400


def test_blocked_users_cannot_chat(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.add(Block(blocker_id=seller.id, blocked_id=buyer.id))
    db.session.commit()

    login(client, "buyer")
    response = client.post(f"/chat/rooms/{room.id}/messages", data={"content": "안녕하세요"})
    assert response.status_code == 403


def test_restricted_user_cannot_block_or_unblock_users(client, app):
    restricted = create_user("restricted", status="RESTRICTED")
    target = create_user("target")
    db.session.add(Block(blocker_id=restricted.id, blocked_id=target.id))
    db.session.commit()

    login(client, restricted.username)
    assert client.post(f"/users/{target.id}/block").status_code == 403
    assert client.post(f"/users/{target.id}/unblock").status_code == 403
    assert Block.query.filter_by(blocker_id=restricted.id, blocked_id=target.id).first() is not None


def test_chat_does_not_show_report_link_for_own_message(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.flush()
    own_message = ChatMessage(room_id=room.id, sender_id=buyer.id, content="제가 쓴 메시지")
    other_message = ChatMessage(room_id=room.id, sender_id=seller.id, content="상대가 쓴 메시지")
    db.session.add_all([own_message, other_message])
    db.session.commit()

    login(client, buyer.username)
    response = client.get(f"/chat/rooms/{room.id}")
    assert response.status_code == 200
    assert f"target_id={own_message.id}".encode() not in response.data
    assert f"target_id={other_message.id}".encode() in response.data


def test_socket_room_join_requires_membership(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    outsider = create_user("outsider")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, outsider.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit("join_product_room", {"room_id": room.id})
    received = socket_client.get_received()
    assert any(
        event["name"] == "chat_error" and event["args"][0]["message"] == "forbidden"
        for event in received
    ), received
    socket_client.disconnect()


def test_socket_rejects_disallowed_origin(client, app):
    create_user("buyer")
    login(client, "buyer")
    socket_client = app.extensions["socketio"].test_client(
        app,
        flask_test_client=client,
        headers={"Origin": "https://evil.example"},
    )
    assert not socket_client.is_connected()


def test_socket_product_messages_are_rate_limited(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, buyer.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit("join_product_room", {"room_id": room.id})
    socket_client.get_received()
    for index in range(7):
        socket_client.emit("send_product_message", {"room_id": room.id, "content": f"메시지 {index}"})
    received = socket_client.get_received()
    assert any(
        event["name"] == "chat_error" and event["args"][0]["message"] == "rate limited"
        for event in received
    ), received
    socket_client.disconnect()


def test_socket_product_message_uses_session_sender_and_ignores_spoofing(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, buyer.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit(
        "send_product_message",
        {"room_id": room.id, "content": "세션 발신자", "sender_id": seller.id, "username": "seller"},
    )
    message = ChatMessage.query.filter_by(content="세션 발신자").first()
    assert message.sender_id == buyer.id
    received = socket_client.get_received()
    assert any(
        event["name"] == "product_message"
        and event["args"][0]["sender_id"] == buyer.id
        and event["args"][0]["content"] == "세션 발신자"
        for event in received
    ), received
    socket_client.disconnect()


def test_http_product_message_broadcasts_to_socket_room(client, app, monkeypatch):
    from app.chat import routes as chat_routes

    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()
    emitted = []

    def capture_emit(event, payload, room=None):
        emitted.append((event, payload, room))

    monkeypatch.setattr(chat_routes.socketio, "emit", capture_emit)
    login(client, buyer.username)
    response = client.post(
        f"/chat/rooms/{room.id}/messages",
        data={"content": "폼 전송도 실시간"},
    )

    assert response.status_code == 302
    assert any(
        event == "product_message"
        and payload["sender_id"] == buyer.id
        and payload["content"] == "폼 전송도 실시간"
        and target_room == f"product-{room.id}"
        for event, payload, target_room in emitted
    ), emitted


def test_socket_rejects_invalid_room_and_invalid_content(client, app):
    create_user("buyer")
    login(client, "buyer")
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)

    socket_client.emit("join_product_room", {"room_id": 999})
    socket_client.emit("send_product_message", {"room_id": 999, "content": "없는 방"})
    socket_client.emit("send_product_message", {"room_id": [], "content": "배열 방"})
    received = socket_client.get_received()
    assert sum(event["name"] == "chat_error" for event in received) == 3
    socket_client.disconnect()


def test_socket_rejects_blank_long_nonstring_and_restricted_sender(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer", status="RESTRICTED")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, buyer.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit("send_product_message", {"room_id": room.id, "content": "제한 사용자"})
    restricted_events = socket_client.get_received()
    assert any(event["args"][0]["message"] == "forbidden" for event in restricted_events)
    socket_client.disconnect()

    buyer.status = "ACTIVE"
    db.session.commit()
    client.post("/auth/logout")
    login(client, buyer.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit("send_product_message", {"room_id": room.id, "content": "   "})
    socket_client.emit("send_product_message", {"room_id": room.id, "content": "x" * 501})
    socket_client.emit("send_product_message", {"room_id": room.id, "content": {"html": "<script>alert(1)</script>"}})
    received = socket_client.get_received()
    assert sum(event["name"] == "chat_error" for event in received) == 3
    socket_client.disconnect()


def test_socket_block_after_join_is_checked_at_send_time(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product = create_product(seller)
    room = ChatRoom(product_id=product.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add(room)
    db.session.commit()

    login(client, buyer.username)
    socket_client = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_client.emit("join_product_room", {"room_id": room.id})
    socket_client.get_received()
    db.session.add(Block(blocker_id=seller.id, blocked_id=buyer.id))
    db.session.commit()
    socket_client.emit("send_product_message", {"room_id": room.id, "content": "차단 후 메시지"})
    received = socket_client.get_received()
    assert any(event["name"] == "chat_error" and event["args"][0]["message"] == "blocked" for event in received)
    socket_client.disconnect()


def test_socket_rate_limit_shared_across_product_rooms_and_sockets(client, app):
    seller = create_user("seller")
    buyer = create_user("buyer")
    product_one = create_product(seller, title="상품 1")
    product_two = create_product(seller, title="상품 2")
    room_one = ChatRoom(product_id=product_one.id, seller_id=seller.id, buyer_id=buyer.id)
    room_two = ChatRoom(product_id=product_two.id, seller_id=seller.id, buyer_id=buyer.id)
    db.session.add_all([room_one, room_two])
    db.session.commit()

    login(client, buyer.username)
    socket_one = app.extensions["socketio"].test_client(app, flask_test_client=client)
    socket_two = app.extensions["socketio"].test_client(app, flask_test_client=client)
    for index in range(3):
        socket_one.emit("send_product_message", {"room_id": room_one.id, "content": f"방1-{index}"})
        socket_two.emit("send_product_message", {"room_id": room_two.id, "content": f"방2-{index}"})
    received = socket_one.get_received() + socket_two.get_received()
    assert any(event["name"] == "chat_error" and event["args"][0]["message"] == "rate limited" for event in received)
    socket_one.disconnect()
    socket_two.disconnect()


def test_duplicate_report_and_product_threshold(client, app):
    seller = create_user("seller")
    product = create_product(seller)
    reporters = [create_user(f"reporter{i}") for i in range(3)]

    login(client, "reporter0")
    data = {
        "target_type": "PRODUCT",
        "target_id": str(product.id),
        "reason_category": "부정확한 정보",
        "reason_detail": "설명이 실제와 다릅니다.",
    }
    assert client.post("/reports/new", data=data).status_code == 302
    assert client.post("/reports/new", data=data).status_code == 302
    assert Report.query.filter_by(target_type="PRODUCT", target_id=product.id).count() == 1

    client.post("/auth/logout")
    for reporter in reporters[1:]:
        login(client, reporter.username)
        client.post("/reports/new", data=data)
        client.post("/auth/logout")

    assert db.session.get(Product, product.id).status == "HIDDEN"


def test_report_invalid_target_id_returns_400(client, app):
    create_user("reporter")
    login(client, "reporter")
    response = client.post(
        "/reports/new",
        data={
            "target_type": "PRODUCT",
            "target_id": "null",
            "reason_category": "부정확한 정보",
            "reason_detail": "조작된 대상 ID입니다.",
        },
    )
    assert response.status_code == 400


def test_user_report_threshold_restricts_user(client, app):
    target = create_user("target")
    reporters = [create_user(f"reporter{i}") for i in range(5)]
    for reporter in reporters:
        login(client, reporter.username)
        response = client.post(
            "/reports/new",
            data={
                "target_type": "USER",
                "target_id": str(target.id),
                "reason_category": "사기 의심",
                "reason_detail": "반복적으로 의심스러운 행동을 합니다.",
            },
        )
        assert response.status_code == 302
        client.post("/auth/logout")
    assert db.session.get(User, target.id).status == "RESTRICTED"


def test_admin_access_and_audit_log(client, app):
    user = create_user("user")
    admin = create_user("admin", role="ADMIN")
    product = create_product(user)

    login(client, "user")
    assert client.get("/admin/").status_code == 403
    client.post("/auth/logout")

    login(client, "admin")
    response = client.post(f"/admin/products/{product.id}/hide", data={"reason": "정책 위반"})
    assert response.status_code == 302
    assert db.session.get(Product, product.id).status == "HIDDEN"
    log = AdminAuditLog.query.filter_by(admin_id=admin.id, action="PRODUCT_HIDE").first()
    assert log is not None
    assert log.reason == "정책 위반"


def test_admin_cannot_suspend_self_as_last_active_admin(client, app):
    admin = create_user("admin", role="ADMIN")
    login(client, admin.username)
    response = client.post(
        f"/admin/users/{admin.id}/status",
        data={"status": "SUSPENDED", "reason": "자기 잠금"},
    )
    assert response.status_code == 400
    assert db.session.get(User, admin.id).status == "ACTIVE"
    assert AdminAuditLog.query.filter_by(action="USER_STATUS").first() is None


def test_restricted_admin_existing_session_cannot_access_admin(client, app):
    admin = create_user("admin", role="ADMIN")
    login(client, admin.username)
    admin.status = "RESTRICTED"
    db.session.commit()

    assert client.get("/admin/").status_code == 403


def test_regular_user_cannot_use_admin_wallet_grant(client, app):
    user = create_user("user")
    target = create_user("target")
    login(client, user.username)
    response = client.post(
        f"/admin/users/{target.id}/wallet-grant",
        data={"amount": "100", "idempotency_key": "grant-1", "reason": "권한 우회 시도"},
    )
    assert response.status_code == 403
