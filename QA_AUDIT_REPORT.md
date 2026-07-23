# Tiny Market Independent QA Audit

## README Reproduction

| Step | Result | Notes |
| --- | --- | --- |
| Fresh venv creation | PASS | `/private/tmp/tiny-market-audit.6J6toy/.venv` |
| `pip install -r requirements-dev.txt` | PASS after network approval | Initial sandbox DNS block was external to the project |
| `flask --app run.py db upgrade` | PASS | Fresh SQLite DB under `/private/tmp` |
| `pytest` from venv entrypoint | FAIL, then fixed | Added `pythonpath = .` to `pytest.ini` |
| `ruff check .` | PASS | No lint findings |
| `bandit -r app -x app/templates` | PASS | No issues identified |
| Browser flow | PASS after fixes | Signup, product, search, chat, report, admin resolve, grant, transfer |

## Requirement Traceability

| Requirement Area | Implementation | Coverage | Status |
| --- | --- | --- | --- |
| Flask/Jinja server rendering | App factory, blueprints, Jinja templates | Browser and route tests | PASS |
| Environment config | `SECRET_KEY`, `DATABASE_URL`, upload path, cookie settings | README reproduction, config review | PASS |
| User model | Required fields and constraints | Model creation via tests/seed | PASS |
| Product/ProductImage/Favorite | Required models, image metadata, unique favorites | Product tests | PASS |
| ChatRoom/ChatMessage | Unique room tuple, persisted messages | HTTP and Socket.IO tests | PASS |
| Block/Report/Review | Block constraints, duplicate report constraint, review model | Report/block tests | PASS |
| Wallet/WalletTransaction | Non-negative balance, idempotency key, immutable ledger route | Wallet tests, concurrent transfer test | PASS |
| AdminAuditLog | Admin actions log mandatory reason | Admin audit test | PASS |
| Home/search/filter/sort | ORM filters, pagination, responsive cards | Product search test, browser QA | PASS |
| Auth/session | Hashing, generic login error, POST logout, password-change logout | Auth tests | PASS |
| Products | CRUD, owner/admin checks, hidden product protection | Product/IDOR tests | PASS |
| Image security | Extension plus signature, UUID filename, size limit | Upload tests | PASS |
| Product chat | Participant-only rooms, session sender, block enforcement | Chat tests | PASS |
| Plaza chat | Login-only persisted global chat | Route/code review | PARTIAL |
| Reports/thresholds | Duplicate report block, product/user thresholds | Report tests | PASS |
| Admin console | Users, products, reports, wallet grant, message hide route | Admin tests/browser QA | PASS |
| Test money | No real payment, transfer validation, rollback, idempotency | Wallet tests/browser QA | PASS |
| Responsive UI | CSS media queries, mobile bottom nav | Code review | PASS |
| Socket.IO | Room authorization, sender from session, rate limit | Socket.IO tests | PASS |
| Documentation | README, security report, test report | This audit update | PASS |

Partial note: plaza chat supports persisted login-only messages and admin hide route, but it does not yet expose a first-class plaza-message report button in the UI.

## Fake Or Disconnected UI Findings

| Severity | Problem Location | Reproduction | Impact | Fix | Added Tests | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Medium | `app/templates/products/detail.html` | Log in as product owner, open own product, click `신고` | UI offered an action the server rejects as self-report | Hide product report/favorite action block for owner | `test_owner_product_detail_does_not_show_self_report_link` | PASS |
| Medium | `app/templates/chat/room.html` | Send a chat message, click report on own message | UI offered an action the server rejects as self-report | Hide report link on messages sent by current user | `test_chat_does_not_show_report_link_for_own_message` | PASS |

## Security Findings And Fixes

| Severity | Problem Location | Reproduction | Expected Impact | Fix | Added Tests | Result |
| --- | --- | --- | --- | --- | --- | --- |
| High | `app/wallet/routes.py` | Run two concurrent transfers of 80 TM from a 100 TM wallet | Double-spend or inconsistent ledger possible | Atomic conditional debit with `UPDATE ... WHERE balance >= amount`, rollback on failure | `test_concurrent_transfers_cannot_double_spend` | PASS |
| High | `app/__init__.py`, `app/chat/routes.py` | Create multiple app instances, then use Socket.IO test client | Socket.IO handlers missing on later app factory instances, room checks not exercised | Register blueprints before `socketio.init_app(app)` and use explicit `chat_error` event | `test_socket_room_join_requires_membership` | PASS |
| Medium | `app/chat/routes.py` | Rapidly emit Socket.IO messages | No Socket.IO-side send rate limit | Added per-user per-room in-memory socket rate bucket | `test_socket_product_messages_are_rate_limited` | PASS |
| Medium | `app/users/routes.py` | Change password, then request `/me` with same session | Session remains authenticated after password change | `logout_user()` and `session.clear()` after password update | `test_password_change_logs_out_current_session` | PASS |
| Medium | `pytest.ini` | Run fresh venv `pytest` entrypoint | `ModuleNotFoundError: app`; README test command broken | Added `pythonpath = .` | README reproduction | PASS |

## Focused Security Checklist

| Item | Result |
| --- | --- |
| Plaintext passwords | PASS: stored through Werkzeug hashes only |
| Hardcoded secrets | PASS: no committed real secret; `.env.example` placeholders only |
| SQL Injection | PASS: ORM conditions, no raw user SQL |
| Stored/reflected XSS | PASS: Jinja autoescape, no `safe` rendering of user content |
| CSRF | PASS: Flask-WTF enabled; missing-token test returns 400 |
| IDOR | PASS: product, chat, admin, hidden product, wallet checks tested |
| File upload | PASS: extension, signature, UUID storage, path guard |
| Auth/admin bypass | PASS: admin routes require `ADMIN`; user grant attempt 403 |
| Chat username spoofing | PASS: sender comes from session |
| Socket.IO room entry | PASS: non-participant gets `chat_error: forbidden` |
| Duplicate report | PASS: unique reporter/target constraint and test |
| Block bypass | PASS: blocked 1:1 chat POST returns 403 |
| Negative/zero transfer | PASS: validation rejects |
| Insufficient transfer | PASS: validation rejects |
| Duplicate transfer key | PASS: duplicate idempotency key rejected |
| Partial transfer | PASS: rollback test passes |
| Concurrent transfer | PASS after atomic debit fix |
| Debug in production | PASS: default debug false |
| Sensitive logs | PASS: no password/session/CSRF logging found |

## Browser QA Summary

- Verified public home with 12 seeded product cards and search filters.
- Registered a new browser QA user and logged in.
- Created a product and found it through search.
- Opened another seller's product, started a chat, and sent a message.
- Submitted a product report.
- Logged in as admin, resolved the report, and granted test money.
- Logged back in as the QA user and transferred test money to another user.
- Verified owner product and own chat message no longer expose fake self-report links.

