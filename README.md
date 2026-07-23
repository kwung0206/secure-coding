# Tiny Market

Tiny Market은 Flask와 Jinja로 만든 반응형 중고거래 실습 플랫폼입니다. 실제 결제나 현금성 자산과 연결되지 않으며, 지갑 기능은 과제 검증용 테스트 머니만 다룹니다.

## 주요 기능

- 비로그인 상품 탐색, 검색, 카테고리·지역·가격·상태 필터, 정렬
- 회원가입, 로그인, POST 로그아웃, 프로필 변경, 비밀번호 변경 후 현재 세션 무효화
- 상품 등록, 상세, 수정, 삭제, 판매 상태 변경, 관심 상품
- jpg/jpeg/png/webp 이미지 업로드, Pillow 재인코딩, UUID 저장명, 1회 최대 5개
- 상품별 1대1 채팅, 로그인 사용자용 광장 채팅
- 사용자/상품/메시지 신고, 차단, 신고 임계값 기반 자동 숨김/제한
- ADMIN 전용 사용자·상품·신고·메시지 관리, 테스트 머니 지급, 감사 로그
- 테스트 머니 지갑, 사용자 간 송금, idempotency key 기반 중복 요청 방어

## 기술 스택

- Python 3.14.5에서 최종 검증
- Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- Flask-SocketIO, Flask-Limiter, Pillow, Werkzeug password hashing
- 개발 및 자동 테스트는 SQLite에서 검증했습니다.
- DATABASE_URL을 통한 다른 DB 연결 구조를 제공하지만 PostgreSQL 운영 동시성은 별도 검증이 필요합니다.
- pytest, pytest-cov, Ruff, Bandit, pip-audit

## 설치

Ubuntu 또는 Linux 예시:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/kwung0206/secure-coding.git
cd secure-coding
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Conda 예시:

```bash
conda create -n tiny-market python=3.14
conda activate tiny-market
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## 환경 변수

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

생성한 값을 `.env`의 `SECRET_KEY`에 넣습니다. 운영 또는 외부 공개 환경에서는 강한 `SECRET_KEY`, HTTPS, `SESSION_COOKIE_SECURE=true`, 운영 DB를 설정하세요.

주요 변수:

- `SECRET_KEY`: 필수. 비어 있거나 예시값이면 앱이 시작되지 않습니다.
- `DATABASE_URL`: 기본값은 SQLite. 예: `postgresql://db_user:<db-pass>@db-host:5432/tiny_market`
- `UPLOAD_FOLDER`: 기본값은 `instance/uploads`
- `SESSION_COOKIE_SECURE`: HTTPS 환경에서 `true`
- `SOCKETIO_ALLOWED_ORIGINS`: 추가 허용 Origin이 필요할 때 쉼표로 구분
- `RATELIMIT_ENABLED`: 기본 `true`; 로컬 QA 재현 때만 명시적으로 `false` 사용 가능

`.env`, SQLite DB, 업로드 파일, 로그, 캐시, 가상환경은 커밋하지 않습니다.

## DB와 시드

```bash
source .venv/bin/activate
flask --app run.py db upgrade
```

개발용 시드:

```bash
read -s ADMIN_PASSWORD
export ADMIN_PASSWORD
read -s SEED_USER_PASSWORD
export SEED_USER_PASSWORD
flask --app run.py seed
```

관리자 생성:

```bash
read -s ADMIN_PASSWORD
export ADMIN_PASSWORD
flask --app run.py create-admin --username admin
```

`seed`는 기존 사용자가 있으면 중복 생성을 거부합니다.

## 실행

```bash
source .venv/bin/activate
flask --app run.py db upgrade
HOST=127.0.0.1 PORT=5000 python run.py
```

LAN 또는 기기 외부 브라우저에서 확인해야 하면 필요한 인터페이스로 바인딩합니다.

```bash
HOST=0.0.0.0 PORT=5001 python run.py
```

실시간 채팅은 Socket.IO 서버 실행 경로를 사용해야 하므로 `flask --app run.py run` 대신 `python run.py`를 사용하세요.

## 검사 명령

```bash
python -m compileall app tests
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
python -m ruff check .
python -m bandit -r app -x app/templates
python -m pip check
python -m pip_audit
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
```

최종 감사 결과:

- `pytest`: 56 passed
- `coverage`: app 전체 77%
- `ruff check .`: All checks passed
- `bandit -r app -x app/templates`: High 0, Medium 0
- `pip check`: No broken requirements found
- `pip-audit`: 운영/개발 의존성 모두 known vulnerability 없음

## 최종 점검 사항과 결과

최종 제출 전 보안 감사자와 QA 엔지니어 관점에서 다음 항목을 실제로 점검했습니다. 상세 재현 절차와 테스트 함수는 `SECURITY_REPORT.md`, `TEST_REPORT.md`, `QA_AUDIT_REPORT.md`에 기록했습니다.

| 점검 항목 | 수행 내용 | 결과 |
| --- | --- | --- |
| Git 민감정보 | `.env`, DB, 업로드, 로그, 캐시, venv, secret/API key/private key, 개인 절대 경로 검색 | PASS: 추적 중인 민감 파일 없음 |
| README 재현성 | fresh venv 생성, 운영/개발 의존성 설치, README 명령 검증 | PASS |
| 의존성 감사 | `pip check`, `pip-audit`, 운영/개발 requirements 분리 검사 | PASS: known vulnerability 없음 |
| Flask 운영 설정 | `SECRET_KEY` 필수화, debug 기본 비활성, 쿠키/세션 설정 확인 | PASS |
| 보안 응답 헤더 | CSP, nosniff, Referrer-Policy, Permissions-Policy, frame 방어, 조건부 HSTS | PASS |
| 인증/세션 | 평문 비밀번호 금지, 로그인 실패 메시지, POST 로그아웃, 비밀번호 변경 후 세션 종료 | PASS |
| CSRF | 상태 변경 라우트 토큰 검증 | PASS |
| SQL Injection | 검색/필터/관리자 조회에서 ORM 조건식 사용 확인 | PASS |
| XSS | 상품명, 소개글, 채팅, 신고 사유 렌더링과 `safe`/`innerHTML` 위험 패턴 확인 | PASS |
| IDOR | 타인 상품, 숨김 상품, 채팅방, 신고, 관리자, 지갑 권한 우회 테스트 | PASS |
| 파일 업로드 | 위조 이미지, 비이미지, 대용량, 다중 파일, UUID 저장명, Pillow 재인코딩 | PASS |
| Socket.IO | 비로그인/비참여자 거부, sender spoof 방어, Origin 검증, rate limit, 차단 후 재검사, 실시간 UI 연결 | PASS |
| 신고/차단 | 자기 신고, 중복 신고, 임계값, invalid target_id, 차단 후 기존 채팅 제한 | PASS |
| 관리자 권한 | ACTIVE ADMIN만 허용, 마지막 관리자 자기 정지 방어, 감사 로그 | PASS |
| 테스트 머니 | 음수/0/잔액 부족/자기 송금/중복 key/과대 금액/동시 송금/rollback/총량 무결성 | PASS |
| DB migration | 빈 DB upgrade, downgrade, 재-upgrade, seed 중복 거부 | PASS |
| 브라우저 QA | 회원가입부터 상품 등록, 검색, 관심, 채팅, 신고, 관리자 처리, 지급, 송금, 오류 화면 확인 | PASS |

브라우저 QA에서 OS 파일 선택 UI는 자동화 도구가 직접 조작 API를 제공하지 않아 부분 검증으로 기록했습니다. 대신 실제 multipart 이미지 업로드 서버 경로는 pytest로 검증했습니다.

이번 점검에서 발견해 수정한 주요 문제:

- 운영 `SECRET_KEY` 누락 시 안전하지 않은 실행 가능성 제거
- 취약한 개발 의존성 범위 갱신
- 제한 계정의 기존 세션을 통한 상품/차단/관리자 기능 우회 차단
- Socket.IO 악성 Origin 연결 거부
- 실시간 채팅 프론트엔드 누락과 `flask run` 실행 안내 불일치 수정
- 이미지 위조/과다 업로드 방어 강화
- 조작된 신고 `target_id`가 500을 내던 문제 수정
- 동시 송금 double-spend와 과대 금액/중복 요청 방어 강화

## ngrok

```bash
ngrok http 5000
```

ngrok 또는 프록시 뒤에서 사용할 때도 Host/Origin 검증을 무력화하지 마세요. Socket.IO는 기본적으로 현재 Host와 일치하는 Origin만 허용하며, 필요한 추가 Origin만 `SOCKETIO_ALLOWED_ORIGINS`에 좁게 등록합니다.

## 보안 정책 요약

- 비밀번호는 Werkzeug 해시로만 저장합니다.
- 상태 변경 라우트는 POST와 CSRF 토큰을 사용합니다.
- 제한 또는 정지된 사용자는 상품 수정/삭제/상태 변경, 관심 변경, 차단/해제, 채팅, 신고, 송금을 수행할 수 없습니다.
- ACTIVE ADMIN만 관리자 콘솔을 사용할 수 있습니다.
- 업로드 이미지는 확장자, 실제 이미지 디코딩, 픽셀 수, 크기를 검증하고 재인코딩합니다.
- 상품 삭제 시 연결된 업로드 파일은 즉시 삭제합니다. 별도 고아 파일 정리 배치는 아직 없습니다.
- 테스트 머니 1회 송금/지급 상한은 1,000,000,000 TM입니다.
- 송금 idempotency key는 전역 unique 정책입니다.

## 알려진 제한사항

- Socket.IO rate limit은 단일 프로세스 메모리 기반입니다. 다중 프로세스 운영에서는 Redis 같은 공유 저장소가 필요합니다.
- SQLite 동시성 검증은 자동 테스트 범위에서 수행했습니다. PostgreSQL 운영 동시성은 별도 검증이 필요합니다.
- 이미지 보안은 Pillow 검증/재인코딩까지 포함합니다. 운영에서는 백신/콘텐츠 스캔과 전용 스토리지를 권장합니다.
- 비밀번호 변경은 현재 세션을 무효화합니다. 다른 브라우저의 기존 세션 전체 무효화는 아직 구현하지 않았습니다.
- 광장 채팅 메시지는 관리자 숨김이 가능하지만, UI에 별도 광장 메시지 신고 버튼은 없습니다.
