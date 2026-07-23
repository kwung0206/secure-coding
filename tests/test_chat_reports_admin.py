from app.extensions import db
from app.models import AdminAuditLog, Block, ChatMessage, ChatRoom, Product, Report, User

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


def test_regular_user_cannot_use_admin_wallet_grant(client, app):
    user = create_user("user")
    target = create_user("target")
    login(client, user.username)
    response = client.post(
        f"/admin/users/{target.id}/wallet-grant",
        data={"amount": "100", "idempotency_key": "grant-1", "reason": "권한 우회 시도"},
    )
    assert response.status_code == 403
