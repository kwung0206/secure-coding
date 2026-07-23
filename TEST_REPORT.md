# Tiny Market Test Report

## 실행 환경

- Python: 3.14.5
- Test runner: pytest 8.4.2
- Linter: Ruff 0.15.22
- Security scanner: Bandit 1.9.4
- DB: SQLite isolated test databases

## 실행 명령과 결과

| 명령 | 실제 결과 |
| --- | --- |
| `python3 -m compileall app tests` | 성공 |
| `.venv/bin/python -m pytest` | 22 passed |
| `.venv/bin/python -m ruff check .` | All checks passed |
| `.venv/bin/python -m bandit -r app -x app/templates` | No issues identified |

## 테스트 케이스

| ID | 목적 | 사전 조건 | 입력값 | 기대 결과 | 실제 결과 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | 정상 회원가입 | 없음 | `alice` / 강한 비밀번호 | 사용자 생성 | 생성됨 | PASS |
| AUTH-002 | 비밀번호 평문 저장 금지 | 회원가입 | DB 조회 | 해시 저장 | 평문과 다름 | PASS |
| AUTH-003 | 중복 아이디 거부 | `alice` 존재 | 같은 username | 추가 생성 거부 | count 1 | PASS |
| AUTH-004 | 정상 로그인 | 사용자 존재 | 올바른 비밀번호 | 302 redirect | 302 | PASS |
| AUTH-005 | 실패 로그인 | 사용자 없음 | 임의 계정 | 일반화된 오류 | 일반 메시지 | PASS |
| AUTH-006 | 보호 페이지 접근 거부 | 비로그인 | `GET /me` | 로그인으로 redirect | 302 | PASS |
| AUTH-007 | POST 로그아웃 | 로그인 | GET/POST logout | GET 405, POST 성공 | 일치 | PASS |
| USER-001 | 프로필 변경 | 로그인 | bio, region | 저장 | 저장됨 | PASS |
| USER-002 | 현재 비밀번호 오입력 거부 | 로그인 | 틀린 현재 비밀번호 | 400, 기존 비밀번호 유지 | 일치 | PASS |
| PROD-001 | 상품 등록 | 로그인 판매자 | 상품 폼 | 생성 | 생성됨 | PASS |
| PROD-002 | 상품 조회 | 상품 존재 | `GET /products/<id>` | 200 | 200 | PASS |
| PROD-003 | 상품 수정 | 작성자 로그인 | 제목 변경 | 저장 | 저장됨 | PASS |
| PROD-004 | 상품 삭제 | 작성자 로그인 | POST delete | 삭제 | 삭제됨 | PASS |
| PROD-005 | 타인 수정/삭제 거부 | 타인 로그인 | edit/delete | 403 | 403 | PASS |
| PROD-006 | 검색과 필터 | 상품 2개 | q, max_price, sort | 조건 상품만 표시 | 일치 | PASS |
| PROD-007 | 잘못된 이미지 거부 | 로그인 | PNG 확장자, 비이미지 bytes | 400 | 400 | PASS |
| PROD-008 | 대용량 이미지 거부 | 로그인 | 제한 초과 파일 | 400 또는 413 | 거부됨 | PASS |
| PROD-009 | 안전한 이미지 파일명 | 로그인 | 유효 PNG | UUID 파일명 | 원본명 미사용 | PASS |
| PROD-010 | XSS 이스케이프 | 스크립트 제목 상품 | 홈 조회 | raw script 미출력 | escaped 출력 | PASS |
| CHAT-001 | 상품 채팅방 생성 | 구매자 로그인 | start chat | 방 생성 | 생성됨 | PASS |
| CHAT-002 | 채팅방 권한 | 제3자 로그인 | room 접근 | 403 | 403 | PASS |
| CHAT-003 | 사용자명 사칭 불가 | 구매자 로그인 | sender_id 조작 | 세션 사용자로 저장 | buyer id 저장 | PASS |
| CHAT-004 | 자기 상품 채팅 금지 | 판매자 로그인 | start chat | 400 | 400 | PASS |
| CHAT-005 | 차단 사용자 채팅 금지 | 차단 관계 | 메시지 POST | 403 | 403 | PASS |
| REPORT-001 | 중복 신고 거부 | 신고 1회 존재 | 같은 대상 신고 | 중복 저장 없음 | count 1 | PASS |
| REPORT-002 | 상품 신고 임계값 | 서로 다른 3명 | 상품 신고 | HIDDEN | HIDDEN | PASS |
| REPORT-003 | 사용자 신고 임계값 | 서로 다른 5명 | 사용자 신고 | RESTRICTED | RESTRICTED | PASS |
| ADMIN-001 | 일반 사용자 관리자 접근 거부 | 일반 로그인 | `GET /admin` | 403 | 403 | PASS |
| ADMIN-002 | 관리자 조치 감사 로그 | ADMIN 로그인 | 상품 숨김 + 사유 | 로그 생성 | 생성됨 | PASS |
| WALLET-001 | 정상 송금 | 잔액 충분 | 300 TM 송금 | 양쪽 잔액 반영 | 반영됨 | PASS |
| WALLET-002 | 잔액 부족 송금 거부 | 잔액 부족 | 200 TM 송금 | 400 | 400 | PASS |
| WALLET-003 | 자기 자신 송금 거부 | 로그인 | 자기 username | 400 | 400 | PASS |
| WALLET-004 | 0원 송금 거부 | 로그인 | amount 0 | 검증 실패 | 실패 | PASS |
| WALLET-005 | 중복 idempotency key 거부 | 송금 1회 완료 | 같은 key 재요청 | 400 | 400 | PASS |
| WALLET-006 | 송금 오류 rollback | commit 강제 실패 | 송금 함수 호출 | 양쪽 잔액 원복 | 원복됨 | PASS |
| CSRF-001 | CSRF 없는 상태 변경 거부 | CSRF enabled app | register POST without token | 400 | 400 | PASS |

## 실패와 수정 내용

- 최초 이미지 테스트 2건이 `MAX_CONTENT_LENGTH` 테스트 설정 때문에 앱의 이미지 검증 전에 413으로 실패했습니다.
- 테스트 제한값을 multipart 오버헤드보다 크게 조정하고, 대용량 케이스는 더 큰 파일로 바꿔 재실행했습니다.
- 재실행 결과 전체 22개 pytest가 통과했습니다.

