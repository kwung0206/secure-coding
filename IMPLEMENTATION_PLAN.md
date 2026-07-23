# Tiny Market Implementation Plan

## Phase 1: Repository Audit

### Current State

- The local working tree contains only an empty Git repository. There is no checked-in Flask application, no templates, no tests, no dependency files, and no migration history.
- The referenced GitHub repository could not be inspected from the local clone because no remote is configured and the current branch has no commits.
- Because there is no existing implementation, the initial security finding is absence of required controls rather than vulnerable code paths in specific files.

### Initial Security Gaps

- No environment-based secret management exists.
- No authentication, authorization, CSRF protection, rate limiting, or session hardening exists.
- No database models or ownership checks exist.
- No upload validation exists.
- No audit trail, reporting workflow, blocking workflow, or wallet transaction integrity exists.
- No tests or security scanner configuration exists.

## Target Architecture

Tiny Market will be implemented as a server-rendered Flask and Jinja application with modular blueprints.

### Application Layout

- `app/__init__.py`: app factory, extension initialization, security headers, error handlers, CLI registration.
- `app/config.py`: environment-driven configuration.
- `app/extensions.py`: shared Flask extensions.
- `app/models/`: SQLAlchemy models and enums.
- `app/auth/`: registration, login, logout.
- `app/users/`: profiles, my page, password changes, block controls.
- `app/products/`: home, product CRUD, image upload, search/filter/sort, favorites.
- `app/chat/`: product chat rooms, plaza chat, Socket.IO events.
- `app/reports/`: user/product/message reports.
- `app/wallet/`: test-money balance and transfers.
- `app/admin/`: admin console and audit logging.
- `app/templates/`: accessible Jinja templates.
- `app/static/`: responsive Tiny Market styles.
- `migrations/`: Flask-Migrate/Alembic migration environment.
- `tests/`: pytest coverage for required security and behavior.

## Data Model Plan

- `User`: account, profile, role, status, region verification, manner score.
- `Product`: seller-owned marketplace item with validated status, price, region, and view count.
- `ProductImage`: UUID-based uploaded image metadata.
- `Favorite`: unique user/product favorite edge.
- `ChatRoom`: unique seller/buyer/product room.
- `ChatMessage`: persisted plain-text chat messages with soft-delete support.
- `PlazaMessage`: persisted global plaza chat messages with soft-delete support.
- `Block`: unique blocker/blocked relationship.
- `Report`: unique reporter/target report with status workflow.
- `Review`: post-transaction user review.
- `Wallet`: one per user, non-negative balance.
- `WalletTransaction`: immutable test-money transfer ledger with idempotency key.
- `AdminAuditLog`: all privileged admin actions with mandatory reason.

## API and Route Plan

### Public

- `GET /`: product list, search, filters, sort, pagination.
- `GET /products/<id>`: product detail and seller profile.
- `GET /users/<username>`: public profile.

### Authenticated User

- `GET|POST /auth/register`
- `GET|POST /auth/login`
- `POST /auth/logout`
- `GET /me`
- `GET|POST /me/edit`
- `GET|POST /me/password`
- `GET|POST /products/new`
- `GET|POST /products/<id>/edit`
- `POST /products/<id>/delete`
- `POST /products/<id>/favorite`
- `POST /products/<id>/status`
- `POST /chat/products/<id>/start`
- `GET /chat/rooms/<id>`
- `GET /chat/plaza`
- `GET|POST /reports/new`
- `POST /users/<id>/block`
- `POST /users/<id>/unblock`
- `GET /wallet`
- `GET|POST /wallet/transfer`

### Admin

- `GET /admin`
- `GET /admin/users`
- `POST /admin/users/<id>/status`
- `POST /admin/users/<id>/wallet-grant`
- `GET /admin/products`
- `POST /admin/products/<id>/hide`
- `POST /admin/products/<id>/restore`
- `POST /admin/products/<id>/delete`
- `GET /admin/reports`
- `POST /admin/reports/<id>/resolve`
- `POST /admin/messages/<id>/hide`

## Security Plan

- Use `SECRET_KEY` and `DATABASE_URL` from environment variables.
- Keep `.env` ignored and provide `.env.example`.
- Hash passwords with Werkzeug password hashing.
- Validate password length and complexity.
- Use generic authentication errors.
- Clear the session before login to mitigate session fixation.
- Require POST for logout and other state changes.
- Enable CSRF protection on all normal forms.
- Use Flask-Limiter for login, registration, reporting, chat, and wallet transfer rate limits.
- Use ORM expressions only; no raw SQL string assembly for user filters.
- Enforce ownership/admin checks after object lookup to prevent IDOR.
- Escape user-generated content through Jinja autoescaping and never mark it safe.
- Limit user input lengths at form and model boundary.
- Validate uploaded images by extension and file signature; allow only jpg, jpeg, png, and webp.
- Regenerate uploaded filenames with UUIDs and never trust original filenames for storage.
- Prevent upload path traversal by storing into configured upload directory only.
- Configure HttpOnly and SameSite session cookies; enable Secure cookies in production.
- Avoid logging passwords, CSRF tokens, sessions, or secrets.
- Record all admin actions in `AdminAuditLog`.
- Use a DB transaction for wallet transfers and unique idempotency keys for replay protection.

## Phase Execution Plan

### Phase 2: Structure, Config, Models

- Create the Flask package, extension registry, models, CLI commands, requirements, and migration scaffold.
- Add model-level constraints and helper methods.
- Test model creation, uniqueness, password hashing, and wallet constraints.

### Phase 3: Auth, Profiles, Permissions

- Implement registration, login, POST logout, profile editing, password changes, and public profiles.
- Add admin and ownership decorators.
- Test auth, session behavior, generic errors, and protected page redirects.

### Phase 4: Products, Images, Search, Favorites

- Implement home listing, filters, product CRUD, image upload validation, status changes, and favorites.
- Test product permissions, search/filter behavior, invalid images, oversized images, and CSRF rejection.

### Phase 5: Product Chat and Plaza Chat

- Implement chat room creation, access control, persisted messages, Socket.IO handlers, blocked relationship checks, and plaza chat.
- Test room permissions, sender identity from session, blocked chat denial, and message length limits.

### Phase 6: Reports, Blocks, Admin

- Implement reporting thresholds, block/unblock, admin moderation, user/product/message controls, and audit logging.
- Test duplicate report rejection, threshold effects, admin-only access, and audit creation.

### Phase 7: Test Money

- Implement wallet dashboard, admin grants, user transfers, idempotency, and rollback-safe transaction handling.
- Test successful transfers, insufficient funds, self-transfer, invalid amounts, duplicate keys, and rollback behavior.

### Phase 8: Test, Security Scan, Docs, UI

- Complete responsive Tiny Market UI.
- Add seed command and docs.
- Run pytest, Bandit, and lint checks where dependencies are available.
- Write `SECURITY_REPORT.md` and `TEST_REPORT.md`.

## Replacement Notes

- No existing features are removed because the repository starts empty.
- New features are implemented directly under the requested Flask/Jinja architecture.
