# Tiny Market Security Report

## 최초 코드 감사 결과

로컬 저장소는 빈 Git 저장소였고 기존 Flask 코드가 없었습니다. 따라서 특정 취약 코드의 수정이 아니라, 요구된 보안 통제를 처음부터 적용하는 방식으로 구현했습니다.

## 확인한 약점과 공격 시나리오

| 약점 | 공격 시나리오 | 수정 방법 | 주요 파일 |
| --- | --- | --- | --- |
| 비밀값 관리 없음 | `SECRET_KEY`가 코드에 있으면 세션 위조 위험 | 환경 변수 기반 설정, `.env` ignore, `.env.example` 제공 | `app/config.py`, `.gitignore`, `.env.example` |
| 인증/세션 보호 없음 | 평문 비밀번호 저장, 세션 고정, 사용자 존재 여부 노출 | Werkzeug 해시, 비밀번호 복잡도, 로그인 전 `session.clear()`, 일반화된 오류 | `app/auth/routes.py`, `app/security.py` |
| CSRF 보호 없음 | 공격자가 로그아웃/삭제/송금을 강제 요청 | Flask-WTF CSRF, 상태 변경 POST 라우트 | `app/__init__.py`, templates |
| IDOR 방어 없음 | 타인 상품/채팅방 수정 또는 열람 | 객체 조회 후 소유자/참여자/ADMIN 확인 | `app/products/routes.py`, `app/chat/routes.py`, `app/admin/routes.py` |
| SQL Injection 위험 | 검색 파라미터를 SQL 문자열로 조립 | SQLAlchemy ORM 조건식만 사용 | `app/products/routes.py`, admin routes |
| XSS 위험 | 상품명/채팅 내용에 스크립트 저장 | Jinja autoescape 유지, `safe` 미사용, 길이 제한 | templates, forms, routes |
| 업로드 검증 없음 | SVG/실행 파일/경로 탈출 업로드 | 확장자와 실제 시그니처 검증, UUID 파일명, 저장 경로 확인 | `app/security.py` |
| 신고/차단 부재 | 괴롭힘·사기 대응 불가 | 중복 신고 unique, 임계값 자동 조치, 차단 채팅 제한 | `app/reports/routes.py`, `app/chat/routes.py` |
| 관리자 감사 부재 | 권한 오남용 추적 불가 | 모든 관리자 조치에 사유와 `AdminAuditLog` 기록 | `app/admin/routes.py` |
| 송금 무결성 부재 | 중복 송금, 잔액 음수, 부분 반영 | 잔액 check constraint, idempotency key, 단일 커밋/rollback | `app/wallet/routes.py`, models |

## 수정 전후 차이

- 수정 전: 애플리케이션 코드 없음, 보안 설정 없음, 테스트 없음.
- 수정 후: Flask app factory, 모델 제약조건, 인증/인가, CSRF, rate limit, 파일 검증, 신고/관리자/송금 감사 흐름, pytest/Ruff/Bandit 검증 추가.

## 처음부터 적용한 보안

- 환경 변수 기반 `SECRET_KEY`, `DATABASE_URL`
- HttpOnly/SameSite 세션 쿠키, 운영용 Secure 쿠키 옵션
- 비밀번호 해시 저장과 복잡도 검증
- 로그인 실패 rate limit
- POST 로그아웃과 CSRF 보호
- ORM 기반 검색/필터
- 소유자/참여자/관리자 권한 확인
- 업로드 파일 UUID 저장과 시그니처 검증
- 테스트 머니 송금 idempotency와 rollback
- 관리자 감사 로그

## 구현 후 발견해 수정한 보안/품질 항목

- 테스트 이미지 업로드가 multipart 오버헤드 때문에 앱 검증 전에 413이 나는 테스트 설정을 조정했습니다.
- PostgreSQL URL을 `postgresql+psycopg://`로 정규화해 드라이버 선택을 명확히 했습니다.
- 페이지네이션 URL 생성에서 기존 `page` 파라미터 중복 가능성을 제거했습니다.
- Ruff가 찾은 미사용 import/변수를 제거했습니다.
- 독립 QA에서 fresh venv의 `pytest` 엔트리포인트가 `app` 모듈을 찾지 못하는 README 재현 버그를 발견해 `pytest.ini`에 `pythonpath = .`를 추가했습니다.
- 비밀번호 변경 후 기존 세션이 유지되는 문제를 발견해 변경 완료 시 `logout_user()`와 `session.clear()`를 수행하도록 수정했습니다.
- Socket.IO app factory 재초기화 시 이벤트 핸들러가 새 서버에 붙지 않는 순서 문제를 발견해 Blueprint import 후 `socketio.init_app(app)`을 호출하도록 수정했습니다.
- Socket.IO 메시지 전송에 HTTP 라우트와 별개로 rate limit을 추가했습니다.
- 동시 송금에서 두 요청이 같은 잔액을 보고 모두 성공할 수 있는 double-spend 문제를 발견해 조건부 원자 차감으로 수정했습니다.
- 본인 상품/본인 채팅 메시지 신고 링크가 서버에서 400으로 막히는 가짜 UI를 발견해 해당 링크를 숨겼습니다.

## 남아 있는 위험

- Socket.IO rate limit은 현재 프로세스 메모리 기반입니다. 다중 프로세스 운영에서는 Redis 같은 공유 저장소로 옮겨야 합니다.
- 업로드 이미지는 시그니처 기반 검증입니다. 운영에서는 이미지 디코딩, 리사이징, 바이러스 스캔이 권장됩니다.
- 관리자 기능은 역할 기반입니다. 운영에서는 관리자 MFA, 별도 감사 보관, 권한 세분화가 필요합니다.
- 검색은 `ilike` 기반이라 대규모 데이터에서 성능 튜닝이 필요합니다.
- 광장 채팅 메시지는 저장과 관리자 숨김 route가 있으나, UI에서 별도 신고 버튼은 아직 제공하지 않습니다.

## 보안 검사 결과

```text
bandit -r app -x app/templates
No issues identified.
High: 0, Medium: 0, Low: 0
```
