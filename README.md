# Tiny Market

Tiny Market은 Flask와 Jinja로 만든 반응형 중고거래 실습 플랫폼입니다. 당근의 편한 탐색 경험에서 아이디어를 얻었지만, 로고·상표·문구·이미지·HTML·디자인을 복제하지 않은 독자 UI입니다.

## 주요 기능

- 비로그인 상품 탐색, 검색, 카테고리·지역·가격·상태 필터, 최신순/가격순 정렬
- 회원가입, 로그인, POST 로그아웃, 프로필/비밀번호 변경
- 상품 등록, 상세, 수정, 삭제, 거래 상태 변경, 관심 상품
- jpg/jpeg/png/webp 다중 이미지 업로드와 실제 파일 시그니처 검증
- 상품별 1대1 채팅, 로그인 사용자용 광장 채팅
- 사용자/상품/메시지 신고, 차단, 신고 임계값에 따른 자동 숨김/제한
- ADMIN 전용 사용자·상품·신고·메시지 관리와 감사 로그
- 실제 금전 가치가 없는 테스트 머니 지갑, 관리자 지급, 사용자 간 송금

## 기술 스택

- Python 3.14.5에서 검증
- Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- Flask-SocketIO, Flask-Limiter, Werkzeug password hashing
- SQLite 개발 DB, `DATABASE_URL` 설정 시 PostgreSQL 구조 지원
- pytest, Ruff, Bandit

## 디렉터리 구조

```text
app/
  __init__.py
  config.py
  extensions.py
  models/
  auth/
  users/
  products/
  chat/
  reports/
  wallet/
  admin/
  templates/
  static/
migrations/
tests/
instance/
run.py
requirements.txt
requirements-dev.txt
.env.example
IMPLEMENTATION_PLAN.md
SECURITY_REPORT.md
TEST_REPORT.md
```

## Ubuntu 환경 설정

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
git clone https://github.com/kwung0206/secure-coding.git
cd secure-coding
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Conda를 쓰는 경우:

```bash
conda create -n tiny-market python=3.12
conda activate tiny-market
pip install -r requirements-dev.txt
```

## 환경 변수

```bash
cp .env.example .env
```

필수 운영 값:

- `SECRET_KEY`: 긴 랜덤 문자열
- `DATABASE_URL`: 기본값은 SQLite. PostgreSQL 예시는 `postgresql://user:password@localhost:5432/tiny_market`
- `SESSION_COOKIE_SECURE`: HTTPS 운영 환경에서는 `true`

`.env`는 커밋하지 않습니다.

## DB 초기화와 Migration

```bash
source .venv/bin/activate
flask --app run.py db upgrade
```

새 모델 변경 후:

```bash
flask --app run.py db migrate -m "describe change"
flask --app run.py db upgrade
```

개발용으로 migration 없이 테이블만 만들 때:

```bash
flask --app run.py init-db
```

## 시드 데이터 생성

비밀번호는 코드에 저장하지 않고 환경 변수나 명령 옵션으로 전달합니다.

```bash
export ADMIN_PASSWORD='StrongAdmin1!'
export SEED_USER_PASSWORD='StrongUser1!'
flask --app run.py seed
```

## 관리자 생성

```bash
export ADMIN_PASSWORD='StrongAdmin1!'
flask --app run.py create-admin --username admin
```

## 서버 실행

```bash
source .venv/bin/activate
flask --app run.py db upgrade
flask --app run.py run --host 127.0.0.1 --port 5000
```

Socket.IO 개발 실행:

```bash
python run.py
```

## 테스트와 보안 검사

```bash
pytest
ruff check .
bandit -r app -x app/templates
```

현재 결과:

- `pytest`: 30 passed
- `ruff check .`: All checks passed
- `bandit -r app -x app/templates`: No issues identified

## ngrok 예시

```bash
ngrok http 5000
```

운영처럼 외부에 열 때는 HTTPS를 사용하고 `SESSION_COOKIE_SECURE=true`, 강한 `SECRET_KEY`, 운영 DB를 설정하세요.

## 테스트 머니 안내

Tiny Market의 지갑과 송금은 실제 현금, 계좌, 카드, PG와 연결되지 않습니다. 화면에도 “실제 금전 가치가 없는 실습용 테스트 머니”라고 표시합니다.

## 알려진 제한사항

- 지역 인증은 필드와 시간 구조만 있으며 실제 위치 인증 연동은 없습니다.
- 이미지 검증은 허용 확장자와 파일 시그니처 검증 중심이며, 고급 악성 이미지 분석은 포함하지 않습니다.
- 채팅 속도 제한은 HTTP 전송 라우트에 적용되어 있고 Socket.IO는 기본 검증만 제공합니다.
- 검색은 ORM `ilike` 기반입니다. 대규모 운영에서는 DB 인덱스/전문 검색을 추가해야 합니다.
- 업로드 파일은 로컬 디스크에 저장합니다. 운영에서는 전용 스토리지와 백신/콘텐츠 스캔 연동을 권장합니다.
- 로그인 rate limit이 실제로 적용되므로 브라우저 QA에서 짧은 시간에 여러 계정으로 반복 로그인하면 429가 발생할 수 있습니다.
