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
flask --app run.py run --host 127.0.0.1 --port 5000
```

Socket.IO 개발 실행:

```bash
python run.py
```

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

- `pytest`: 52 passed
- `coverage`: app 전체 77%
- `ruff check .`: All checks passed
- `bandit -r app -x app/templates`: High 0, Medium 0
- `pip check`: No broken requirements found
- `pip-audit`: 운영/개발 의존성 모두 known vulnerability 없음

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
