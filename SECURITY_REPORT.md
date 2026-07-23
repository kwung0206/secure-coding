# Tiny Market Security Report

## 적용된 기본 보안

- `SECRET_KEY`는 환경 변수 필수값이며 안전하지 않은 기본값으로 실행하지 않습니다.
- 세션 쿠키는 HttpOnly, SameSite=Lax이며 HTTPS 운영 환경에서 Secure를 켤 수 있습니다.
- 비밀번호는 Werkzeug 해시로 저장하고 평문 저장/로그 출력을 하지 않습니다.
- Flask-WTF CSRF, POST 기반 상태 변경, Jinja autoescape, SQLAlchemy ORM 조건식을 사용합니다.
- 보안 헤더: CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-Frame-Options, 조건부 HSTS.
- 관리자 조치는 사유와 함께 `AdminAuditLog`에 기록합니다.

## 이번 최종 감사에서 수정한 문제

| ID | 심각도 | 문제 위치 | 공격 또는 재현 시나리오 | 예상 영향 | 수정 전 동작 | 수정 내용 | 수정 파일 | 추가 테스트 | 수정 후 결과 | 남아 있는 위험 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEC-FINAL-001 | High | `app/config.py`, `app/__init__.py` | 운영 환경에서 `SECRET_KEY` 없이 실행 | 세션 서명 약화 또는 배포 실수 | 기본값 의존 가능 | 필수값 검증, 예시값 거부 | `app/config.py`, `app/__init__.py` | `test_secret_key_required_outside_testing` | PASS | 배포 자동화에서 secret 주입 필요 |
| SEC-FINAL-002 | Medium | `requirements-dev.txt` | `pip-audit` 실행 | 알려진 취약 pytest/pip 사용 | pip 26.1.1, pytest 8.4.2 취약점 탐지 | pytest 9.x 범위로 상향, venv pip 26.1.2 적용 | `requirements-dev.txt` | fresh venv audit | PASS | pip 자체는 환경별 업그레이드 필요 |
| SEC-FINAL-003 | High | `app/decorators.py`, product/user routes | 제한 사용자의 기존 세션으로 상품 수정·차단 조작 | 제재 우회 | 일부 라우트가 `login_required`만 사용 | `writable_account_required`, ACTIVE ADMIN 검사 적용 | `app/decorators.py`, `app/products/routes.py`, `app/users/routes.py` | `test_restricted_user_cannot_mutate_existing_product`, `test_restricted_user_cannot_block_or_unblock_users`, `test_restricted_admin_existing_session_cannot_access_admin` | PASS | 다른 기기 세션 전체 무효화는 미구현 |
| SEC-FINAL-004 | High | `app/chat/routes.py` | 악성 Origin으로 Socket.IO test client 연결 | CSWSH/세션 기반 이벤트 남용 | 테스트 클라이언트에서 Origin 우회 가능 | connect 이벤트에서 Origin과 allowlist 검증 | `app/chat/routes.py`, `app/config.py` | `test_socket_rejects_disallowed_origin` | PASS | 프록시 환경에서 올바른 Host/Origin 설정 필요 |
| SEC-FINAL-005 | Medium | `app/security.py` | `.jpg` 확장 비이미지, 위조 PNG, SVG/HTML 업로드 | 저장형 XSS/악성 파일 저장 | 시그니처 중심 검증 | Pillow 디코딩, 픽셀 제한, 안전 포맷 재인코딩 | `app/security.py`, upload routes | `test_spoofed_image_header_is_rejected`, 기존 업로드 테스트 | PASS | 운영 백신 스캔은 별도 |
| SEC-FINAL-006 | Medium | `app/products/routes.py` | 6개 이상 이미지 업로드 | 저장소 남용 | 파일 개수 제한 없음 | 상품 이미지 최대 5개 제한 | `app/products/routes.py` | `test_too_many_product_images_are_rejected` | PASS | 총 사용자별 quota는 없음 |
| SEC-FINAL-007 | Medium | `app/reports/routes.py` | `target_id=null` POST | 500 오류와 서버 로그 스택 | `int()` ValueError가 500으로 전파 | 비정수/0 이하 target_id 400 처리 | `app/reports/routes.py` | `test_report_invalid_target_id_returns_400` | PASS | Flask 기본 예외 로그는 운영 로깅 정책 필요 |
| SEC-FINAL-008 | Medium | `app/products/routes.py` | `SOLD -> RESERVED` 상태 조작 | 거래 상태 되돌림 | 허용 값이면 전이 가능 | 판매자 상태 전이표 적용 | `app/products/routes.py` | `test_sold_product_cannot_move_back_to_reserved` | PASS | 관리자 예외 전이는 별도 정책 필요 |
| SEC-FINAL-009 | Medium | `app/admin/routes.py` | 마지막 ACTIVE 관리자 자기 정지 | 관리자 잠금 | self/last-admin 방어 부족 | 자기 비활성화와 마지막 관리자 비활성화 거부 | `app/admin/routes.py` | `test_admin_cannot_suspend_self_as_last_active_admin` | PASS | 관리자 MFA는 없음 |
| SEC-FINAL-010 | High | `app/wallet/routes.py` | 동시 송금 2건이 잔액 초과 | double-spend | 읽은 잔액 기준 경쟁 가능 | 조건부 원자 차감, rollback 유지 | `app/wallet/routes.py` | `test_concurrent_transfers_cannot_double_spend` | PASS | PostgreSQL 운영 동시성 별도 검증 필요 |
| SEC-FINAL-011 | Medium | `app/wallet/forms.py`, `app/admin/forms.py` | 지나치게 큰 송금/지급 금액 | DB overflow/500 | 상한 없음 | 1회 1,000,000,000 TM 상한 | wallet/admin forms, wallet route | `test_transfer_rejects_excessive_amount` | PASS | 장기 총량 quota는 없음 |
| SEC-FINAL-012 | Medium | `app/admin/routes.py` | 관리자 지급 idempotency race | 500 또는 부분 반영 | commit IntegrityError 처리 부족 | IntegrityError rollback 후 400 | `app/admin/routes.py` | `test_admin_wallet_grant_duplicate_key_rejected` | PASS | 고부하 분산락은 없음 |

## 집중 점검 결과

| 항목 | 결과 |
| --- | --- |
| 평문 비밀번호 | PASS: 해시 저장 |
| 하드코딩 비밀값 | PASS: 실제 secret 없음, `.env.example`은 빈 예시 |
| SQL Injection | PASS: 사용자 입력 raw SQL 없음 |
| Stored/Reflected XSS | PASS: autoescape, `safe`/`innerHTML` 위험 패턴 없음 |
| CSRF | PASS: 상태 변경 POST와 CSRF 테스트 |
| IDOR | PASS: 상품, 채팅방, 신고, 관리자, 지갑 권한 테스트 |
| 파일 업로드 | PASS: Pillow 검증/재인코딩, UUID 파일명, 경로 탈출 방어 |
| 인증/관리자 우회 | PASS: ACTIVE ADMIN만 허용 |
| 사용자명 채팅 사칭 | PASS: sender는 세션 사용자로 결정 |
| Socket.IO room 무단 입장 | PASS: 멤버십 검사 |
| 중복 신고 | PASS: reporter/target unique |
| 차단 우회 | PASS: 전송 시점 재검사 |
| 음수/잔액 초과/중복/동시 송금 | PASS |
| 운영 debug | PASS: 기본 false |
| 민감정보 로그 | PASS: 비밀번호/세션/CSRF 직접 로깅 없음 |

## 남아 있는 위험

- PostgreSQL 운영 동시성은 실제 PostgreSQL에서 검증하지 않았습니다.
- Socket.IO rate limit은 메모리 기반이라 다중 프로세스 운영에서는 공유 저장소가 필요합니다.
- 비밀번호 변경은 현재 세션만 종료합니다.
- 브라우저 자동화 도구가 OS 파일 선택을 지원하지 않아, 이미지 업로드 UI 파일 선택은 pytest multipart 테스트로 대체 검증했습니다.
