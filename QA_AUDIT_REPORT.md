# Tiny Market Final QA Audit Report

## Git 및 민감정보 검사

| 검사 | 결과 |
| --- | --- |
| `git status --short` | commit/push 없이 작업트리에 수정 파일 존재 |
| `git diff --check` | 통과 |
| `git ls-files` | `.env`, DB, 업로드, 로그, venv 추적 없음 |
| `git diff --stat` | 코드, 테스트, 문서 수정 확인 |
| secret pattern 검색 | 실제 secret/API key/private key 없음. 환경 변수명과 테스트용 key 문자열만 탐지 |
| 개인 절대 경로 | 문서에는 개인 홈 절대 경로를 기록하지 않음 |
| `.gitignore` | `.env`, `.venv/`, `venv/`, `*.db`, `instance/`, `uploads/`, 캐시, coverage, log 포함 |

추적 제거가 필요한 민감 파일은 발견하지 못했습니다.

## Fresh Venv 재현 및 최신 재검증

| 단계 | 결과 |
| --- | --- |
| `python3 -m venv /tmp/tiny-market-audit-venv` | PASS |
| `python -m pip install --upgrade pip` | PASS, pip 26.1.2 |
| `python -m pip install -r requirements.txt` | PASS |
| `python -m pip install -r requirements-dev.txt` | PASS |
| Fresh venv baseline `python -m pytest` | 52 passed |
| Current venv after realtime chat fix `python -m pytest` | 56 passed |
| Fresh venv `python -m ruff check .` | All checks passed |
| Fresh venv `python -m bandit -r app -x app/templates` | No issues identified |
| Fresh venv `python -m pip check` | No broken requirements found |
| Fresh venv `python -m pip_audit` | No known vulnerabilities found |

## 명령 실행 결과

| 명령 | 테스트 수 | 실패 수 | 결과 |
| --- | ---: | ---: | --- |
| `python -m compileall app tests` | N/A | 0 | 성공 |
| `python -m pytest` | 56 | 0 | PASS |
| `python -m pytest --cov=app --cov-report=term-missing` | 56 | 0 | PASS, app coverage 77% |
| `python -m ruff check .` | N/A | 0 | PASS |
| `python -m bandit -r app -x app/templates` | N/A | 0 | PASS, High 0, Medium 0 |
| `python -m pip check` | N/A | 0 | PASS |
| `python -m pip_audit` | N/A | 0 | PASS |
| `python -m pip_audit -r requirements.txt` | N/A | 0 | PASS |
| `python -m pip_audit -r requirements-dev.txt` | N/A | 0 | PASS |

## Migration 및 초기 데이터

| 검사 | 결과 |
| --- | --- |
| 빈 SQLite DB `flask --app run.py db upgrade` | PASS |
| 테스트 DB `flask --app run.py db downgrade` | PASS |
| 재 `flask --app run.py db upgrade` | PASS |
| `flask --app run.py seed` 최초 실행 | PASS |
| `seed` 두 번째 실행 | PASS: 기존 사용자 존재로 거부 |

## 요구사항 추적표

| 요구사항 | 구현 위치 | 검증 | 상태 |
| --- | --- | --- | --- |
| Flask app factory와 Blueprint | `app/__init__.py`, 각 blueprint | routes, pytest | PASS |
| 사용자 인증/세션 | `app/auth`, `app/users` | auth/session tests, browser QA | PASS |
| 상품 CRUD/검색/상태 | `app/products` | product tests, browser QA | PASS |
| 이미지 업로드 보안 | `app/security.py` | upload tests | PASS |
| 1대1 채팅/광장 | `app/chat` | HTTP/Socket tests, browser QA | PASS |
| 신고/차단 | `app/reports`, `app/users` | report/block tests, browser QA | PASS |
| 관리자 처리와 감사 로그 | `app/admin` | admin tests, browser QA | PASS |
| 테스트 머니 송금 | `app/wallet` | wallet tests, concurrency tests, browser QA | PASS |
| CSRF/XSS/SQLi/IDOR | routes/templates/tests | static review, pytest | PASS |
| Socket.IO 보안 | `app/chat/routes.py` | Socket.IO tests | PASS |
| 보안 헤더 | `app/__init__.py` | header tests | PASS |
| 문서 정합성 | README/Reports | final audit update | PASS |

## 가짜 UI 점검

| 위치 | 발견 내용 | 조치 | 테스트 |
| --- | --- | --- | --- |
| 상품 상세 | 본인 상품 신고 UI가 서버에서 거부되는 동작을 노출 | 본인 상품에서는 신고/관심 블록 숨김 | `test_owner_product_detail_does_not_show_self_report_link` |
| 채팅방 | 본인 메시지 신고 링크 노출 | 본인 메시지 신고 링크 숨김 | `test_chat_does_not_show_report_link_for_own_message` |

이번 감사에서 새로 확인한 화면 버튼은 대응 서버 라우트가 있었습니다. 광장 메시지 신고 버튼은 UI에 없으며, 구현된 기능처럼 문서화하지 않았습니다.

## 브라우저 QA 결과

| 단계 | 기대 결과 | 실제 결과 | 상태 |
| --- | --- | --- | --- |
| 회원가입/중복 아이디/로그인 | 정상 처리와 중복 거부 | 정상 | PASS |
| 프로필 변경/비밀번호 변경 | 저장, 비밀번호 변경 후 로그아웃 | 정상 | PASS |
| 상품 등록/검색 | 상품 생성 후 검색 노출 | 정상 | PASS |
| 상품 이미지 업로드 | 파일 선택 UI를 통한 이미지 등록 | 자동화 wrapper가 파일 선택 API 미제공 | PARTIAL |
| 이미지 multipart 서버 검증 | 실제 이미지 저장, 위조 이미지 거부 | pytest로 검증 | PASS |
| 관심/1대1 채팅/광장 | 정상 처리 | 정상 | PASS |
| 차단 후 기존 채팅 | 403 | 정상 | PASS |
| 신고/관리자 처리 | 신고 접수, 처리, 상품 숨김/복구 | 정상 | PASS |
| 사용자 제한/복구 | ADMIN 처리 | 정상 | PASS |
| 테스트 머니 지급/송금/잔액 부족 | 지급, 송금, 부족 거부 | 정상 | PASS |
| 403/404/429 | 오류 페이지 표시 | 정상 | PASS |
| 콘솔 오류/CSP | 콘솔 오류 없음 | 브라우저 dev logs에서 오류 없음 | PASS |

## 수정된 문제

- 운영 `SECRET_KEY` 필수화와 보안 헤더 강화.
- pip-audit 취약 pytest/pip 조합 해소.
- Socket.IO Origin 검증, sender spoof/room/rate limit, 실시간 UI 연결 테스트 강화.
- 제한/정지 계정의 기존 세션을 통한 상품·차단·관리자 동작 우회 차단.
- 파일 업로드 Pillow 재인코딩, 픽셀 수 제한, 상품 이미지 개수 제한.
- 잘못된 신고 target_id가 500이 아닌 400이 되도록 수정.
- 테스트 머니 금액 상한, 전역 idempotency key 정책, 동시 송금/rollback 테스트 강화.
- 관리자 지급 IntegrityError rollback 처리.

## 남은 제한사항

- PostgreSQL 운영 동시성은 실제 PostgreSQL에서 검증하지 않았습니다.
- Socket.IO rate limit은 단일 프로세스 메모리 기반입니다.
- 브라우저 자동화에서 OS 파일 선택 UI는 직접 조작하지 못했습니다. 업로드 서버 경로는 pytest로 검증했습니다.
- 운영용 MFA, 바이러스 스캔, 외부 스토리지, 중앙 감사 로그 보관은 과제 범위 밖입니다.
