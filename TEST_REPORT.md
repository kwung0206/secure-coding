# Tiny Market Test Report

## 실행 환경

- Python: 3.14.5
- DB: SQLite isolated test databases
- Test runner: pytest 9.1.1 in fresh venv
- Coverage: pytest-cov, app total 77%
- Static/security: Ruff, Bandit, pip-audit

## 실행 결과

| 명령 | 실제 결과 |
| --- | --- |
| `python -m compileall app tests` | 성공 |
| `python -m pytest` | 56 passed |
| `python -m pytest --cov=app --cov-report=term-missing` | 56 passed, app coverage 77% |
| `python -m ruff check .` | All checks passed |
| `node --check app/static/js/realtime-chat.js` | 성공 |
| `python -m bandit -r app -x app/templates` | No issues identified; High 0, Medium 0 |
| `python -m pip check` | No broken requirements found |
| `python -m pip_audit` | No known vulnerabilities found |

## 테스트 케이스 추적표

| 테스트 ID | 기능 영역 | 테스트 목적 | 사전 조건 | 입력값 | 기대 결과 | 실제 결과 | PASS 또는 FAIL | 관련 테스트 함수 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | 인증 | 회원가입과 해시 저장 | 없음 | 새 사용자/강한 비밀번호 | 사용자 생성, 평문 미저장 | 일치 | PASS | `test_register_success_and_password_is_hashed` |
| AUTH-002 | 인증 | 중복 아이디 거부 | 사용자 존재 | 같은 username | 추가 생성 없음 | 일치 | PASS | `test_duplicate_username_rejected` |
| AUTH-003 | 인증 | 로그인 실패 메시지 일반화 | 없음 | 없는 계정 | 계정 열거 불가 메시지 | 일치 | PASS | `test_login_success_and_failure_message_is_generic` |
| AUTH-004 | 세션 | POST 로그아웃 | 로그인 | GET/POST logout | GET 405, POST 302 | 일치 | PASS | `test_logout_uses_post` |
| AUTH-005 | 세션 | 비밀번호 변경 후 현재 세션 종료 | 로그인 | 현재/새 비밀번호 | `/me` 재접근 redirect | 일치 | PASS | `test_password_change_logs_out_current_session` |
| CONFIG-001 | 설정 | SECRET_KEY 필수 | env secret 없음 | create_app | RuntimeError | 일치 | PASS | `test_secret_key_required_outside_testing` |
| HEAD-001 | 헤더 | 보안 헤더 적용 | test client | GET `/` | CSP/nosniff/referrer/permissions/frame | 일치 | PASS | `test_security_headers_present` |
| HEAD-002 | 헤더 | HTTPS 설정 시 HSTS | secure cookie true | GET `/` | HSTS 존재 | 일치 | PASS | `test_hsts_enabled_when_secure_cookie_configured` |
| ERR-001 | 오류 | 500 본문 스택 미노출 | test-only boom route | GET `/boom` | 500, 민감 문자열 없음 | 일치 | PASS | `test_internal_error_page_does_not_leak_exception_details` |
| PROD-001 | 상품 | CRUD | 판매자 로그인 | create/edit/delete | 정상 반영 | 일치 | PASS | `test_product_create_read_update_delete` |
| PROD-002 | IDOR | 타인 수정/삭제 거부 | 타인 로그인 | edit/delete | 403 | 일치 | PASS | `test_other_user_cannot_edit_or_delete_product` |
| PROD-003 | 계정 상태 | 제한 사용자 기존 상품 변경 거부 | RESTRICTED 판매자 | edit/status/delete | 403 | 일치 | PASS | `test_restricted_user_cannot_mutate_existing_product` |
| PROD-004 | IDOR | 숨김 상품 직접 접근 방어 | HIDDEN 상품 | 타인/작성자 조회 | 타인 404, 작성자 200 | 일치 | PASS | `test_hidden_product_idor_protection` |
| PROD-005 | UI/정책 | 자기 상품 신고 링크 숨김 | 작성자 로그인 | 상세 조회 | 신고 링크 없음 | 일치 | PASS | `test_owner_product_detail_does_not_show_self_report_link` |
| PROD-006 | 상태 전이 | SOLD 되돌림 거부 | SOLD 상품 | RESERVED POST | 400, 상태 유지 | 일치 | PASS | `test_sold_product_cannot_move_back_to_reserved` |
| PROD-007 | 검색 | 필터/정렬 | 상품 2개 | q/max/sort | 조건 상품만 표시 | 일치 | PASS | `test_product_search_filter_and_sort` |
| UPLOAD-001 | 업로드 | 비이미지/대용량 거부 | 로그인 | bad png/large | 400 또는 413 | 일치 | PASS | `test_invalid_and_oversized_images_are_rejected` |
| UPLOAD-002 | 업로드 | 위조 헤더 거부 | 로그인 | fake PNG | 400 | 일치 | PASS | `test_spoofed_image_header_is_rejected` |
| UPLOAD-003 | 업로드 | UUID 저장명 | 로그인 | valid PNG | 원본명 미사용 | 일치 | PASS | `test_valid_image_is_stored_with_uuid_name` |
| UPLOAD-004 | 업로드 | 파일 개수 제한 | 로그인 | 6개 이미지 | 400, 저장 없음 | 일치 | PASS | `test_too_many_product_images_are_rejected` |
| XSS-001 | XSS | 상품명 escape | script 제목 | GET `/` | raw script 없음 | 일치 | PASS | `test_xss_payload_is_escaped` |
| CHAT-001 | 채팅 | 방 권한과 sender spoof 방어 | 방 존재 | sender_id 변조 | 세션 sender 저장 | 일치 | PASS | `test_product_chat_room_permissions_and_sender_spoofing` |
| CHAT-002 | 채팅 | 자기 상품 채팅 금지 | 판매자 | start chat | 400 | 일치 | PASS | `test_seller_cannot_chat_with_self` |
| CHAT-003 | 차단 | 차단 사용자 전송 거부 | block 존재 | message POST | 403 | 일치 | PASS | `test_blocked_users_cannot_chat` |
| CHAT-004 | UI/정책 | 본인 메시지 신고 링크 숨김 | 양측 메시지 | room 조회 | 본인 신고 링크 없음 | 일치 | PASS | `test_chat_does_not_show_report_link_for_own_message` |
| CHAT-005 | 채팅 | 판매자/구매자 채팅방 목록 노출 | 방 존재 | `/chat/rooms` | 당사자만 방 표시 | 일치 | PASS | `test_chat_room_list_is_visible_to_seller_and_buyer` |
| CHAT-006 | 실시간 채팅 | 상품 채팅 Socket.IO 클라이언트 로드 | 방 존재 | room 조회 | realtime data와 JS 포함 | 일치 | PASS | `test_product_chat_room_loads_realtime_client` |
| CHAT-007 | 실시간 채팅 | 광장 Socket.IO 클라이언트 로드 | 로그인 | plaza 조회 | realtime data와 JS 포함 | 일치 | PASS | `test_plaza_loads_realtime_client` |
| CHAT-008 | 실시간 채팅 | 일반 POST 메시지 브로드캐스트 | 구매자 로그인 | message POST | `product_message` emit | 일치 | PASS | `test_http_product_message_broadcasts_to_socket_room` |
| USER-001 | 차단 | 제한 사용자의 차단/해제 조작 거부 | RESTRICTED | block/unblock | 403 | 일치 | PASS | `test_restricted_user_cannot_block_or_unblock_users` |
| SOCK-001 | Socket.IO | 비참여자 room join 거부 | outsider 로그인 | join event | `chat_error` | 일치 | PASS | `test_socket_room_join_requires_membership` |
| SOCK-002 | Socket.IO | Origin 거부 | 악성 Origin | connect | 연결 실패 | 일치 | PASS | `test_socket_rejects_disallowed_origin` |
| SOCK-003 | Socket.IO | rate limit | 빠른 emit | 7회 전송 | rate limited | 일치 | PASS | `test_socket_product_messages_are_rate_limited` |
| SOCK-004 | Socket.IO | sender spoof 방어와 송신자 즉시 수신 | buyer 로그인 | sender_id/username 변조 | buyer 저장 및 이벤트 수신 | 일치 | PASS | `test_socket_product_message_uses_session_sender_and_ignores_spoofing` |
| SOCK-005 | Socket.IO | invalid room/content | 로그인 | 없는 room, 배열 room | 오류 이벤트 | 일치 | PASS | `test_socket_rejects_invalid_room_and_invalid_content` |
| SOCK-006 | Socket.IO | 제한 사용자/blank/long/object 거부 | RESTRICTED 또는 ACTIVE | 여러 payload | 오류 이벤트 | 일치 | PASS | `test_socket_rejects_blank_long_nonstring_and_restricted_sender` |
| SOCK-007 | Socket.IO | join 후 차단 재검사 | join 후 block | send | blocked | 일치 | PASS | `test_socket_block_after_join_is_checked_at_send_time` |
| SOCK-008 | Socket.IO | 다중 소켓/방 rate 우회 방어 | 2 rooms/2 sockets | 교차 전송 | rate limited | 일치 | PASS | `test_socket_rate_limit_shared_across_product_rooms_and_sockets` |
| REPORT-001 | 신고 | 중복 신고와 상품 임계값 | 신고자 3명 | product report | 중복 1건, HIDDEN | 일치 | PASS | `test_duplicate_report_and_product_threshold` |
| REPORT-002 | 신고 | invalid target_id 400 | 로그인 | target_id null | 400 | 일치 | PASS | `test_report_invalid_target_id_returns_400` |
| REPORT-003 | 신고 | 사용자 임계값 | 신고자 5명 | user report | RESTRICTED | 일치 | PASS | `test_user_report_threshold_restricts_user` |
| ADMIN-001 | 관리자 | 일반 사용자 접근 거부와 감사 로그 | admin/user | hide product | user 403, log 생성 | 일치 | PASS | `test_admin_access_and_audit_log` |
| ADMIN-002 | 관리자 | 마지막 관리자 자기 정지 방어 | 단일 admin | self suspend | 400, log 없음 | 일치 | PASS | `test_admin_cannot_suspend_self_as_last_active_admin` |
| ADMIN-003 | 관리자 | 제한 관리자 기존 세션 거부 | ADMIN RESTRICTED | GET admin | 403 | 일치 | PASS | `test_restricted_admin_existing_session_cannot_access_admin` |
| ADMIN-004 | 관리자 지갑 | 일반 사용자 지급 우회 차단 | user 로그인 | wallet-grant | 403 | 일치 | PASS | `test_regular_user_cannot_use_admin_wallet_grant` |
| WALLET-001 | 지갑 | 정상 송금 | 잔액 충분 | 300 TM | 양쪽 반영 | 일치 | PASS | `test_successful_transfer` |
| WALLET-002 | 지갑 | 잔액 부족/self/0/중복 거부 | 로그인 | 다양한 입력 | 거부 | 일치 | PASS | `test_transfer_rejects_insufficient_self_nonpositive_and_duplicate` |
| WALLET-003 | 지갑 | commit 실패 rollback | monkeypatch | forced failure | 잔액/원장 원복 | 일치 | PASS | `test_transfer_rolls_back_on_commit_failure` |
| WALLET-004 | 지갑 | 큰 금액 거부 | 직접 호출 | max+1 | ValueError, 원복 | 일치 | PASS | `test_transfer_rejects_excessive_amount` |
| WALLET-005 | 지갑 | 동시 송금 double-spend 방어 | 100 TM | 80 TM 2회 | 1 success, 1 rejected | 일치 | PASS | `test_concurrent_transfers_cannot_double_spend` |
| WALLET-006 | 회계 | 총 잔액 = 관리자 발행 총액 | grant 후 transfer | 1000/300 | 총량 유지 | 일치 | PASS | `test_wallet_total_balance_matches_admin_grants_after_transfer` |
| WALLET-007 | 관리자 지갑 | 지급 idempotency 중복 거부 | admin | 같은 key 2회 | 두 번째 400 | 일치 | PASS | `test_admin_wallet_grant_duplicate_key_rejected` |
| WALLET-008 | 지갑 | idempotency 전역 unique | 두 sender | 같은 key | 두 번째 400 | 일치 | PASS | `test_transfer_idempotency_key_is_global_across_users` |
| CSRF-001 | CSRF | 토큰 없는 상태 변경 거부 | CSRF enabled app | register POST | 400 | 일치 | PASS | `test_missing_csrf_rejected` |

## 브라우저 QA 요약

- PASS: 회원가입, 중복 아이디, 로그인, 프로필 변경, 비밀번호 변경 후 로그아웃, 새 비밀번호 로그인.
- PASS: 상품 등록, 검색/필터, 관심 등록, 1대1 채팅, 광장 채팅, 차단 후 기존 채팅방 전송 403.
- PASS: 상품 신고, 관리자 신고 처리, 상품 숨김/복구, 사용자 제한/복구, 관리자 테스트 머니 지급, 사용자 송금, 잔액 부족 거부.
- PASS: 403, 404, 429 화면과 콘솔 오류 없음.
- PARTIAL: 브라우저 자동화 wrapper가 OS 파일 선택 또는 `setInputFiles`를 제공하지 않아 이미지 파일 선택 UI는 직접 조작하지 못했습니다. 실제 이미지 multipart 업로드는 pytest에서 검증했습니다.
