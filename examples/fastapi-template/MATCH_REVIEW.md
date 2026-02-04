# Match Review Report
**Product:** fastapi-template
**Generated for validation**

## Summary
- Coverage: 60.4%
- Complete: 55
- Partial: 0
- Missing: 36
- Extra: 0

## Drift Items (Coverage Checklist vs Content Inventory)

### ❌ List users — `missing`
- Missing surface nodes (1):
  - `verb:GET:/users/` — get_users (verb)
- Action: Create new reference topic: List users

### ❌ Create users — `missing`
- Missing surface nodes (1):
  - `verb:POST:/users/` — create_users (verb)
- Action: Create new reference topic: Create users

### ❌ Update me — `missing`
- Missing surface nodes (1):
  - `verb:PATCH:/users/me` — patch_me (verb)
- Action: Create new reference topic: Update me

### ❌ Update password — `missing`
- Missing surface nodes (1):
  - `verb:PATCH:/users/me/password` — patch_password (verb)
- Action: Create new reference topic: Update password

### ❌ List me — `missing`
- Missing surface nodes (1):
  - `verb:GET:/users/me` — get_me (verb)
- Action: Create new reference topic: List me

### ❌ Delete me — `missing`
- Missing surface nodes (1):
  - `verb:DELETE:/users/me` — delete_me (verb)
- Action: Create new reference topic: Delete me

### ❌ Create signup — `missing`
- Missing surface nodes (1):
  - `verb:POST:/users/signup` — create_signup (verb)
- Action: Create new reference topic: Create signup

### ❌ Get users — `missing`
- Missing surface nodes (1):
  - `verb:GET:/users/{user_id}` — get_users (verb)
- Action: Create new reference topic: Get users

### ❌ Update users — `missing`
- Missing surface nodes (1):
  - `verb:PATCH:/users/{user_id}` — patch_users (verb)
- Action: Create new reference topic: Update users

### ❌ Delete users — `missing`
- Missing surface nodes (1):
  - `verb:DELETE:/users/{user_id}` — delete_users (verb)
- Action: Create new reference topic: Delete users

### ❌ Create access-token — `missing`
- Missing surface nodes (1):
  - `verb:POST:/login/access-token` — create_access-token (verb)
- Action: Create new reference topic: Create access-token

### ❌ Create test-token — `missing`
- Missing surface nodes (1):
  - `verb:POST:/login/test-token` — create_test-token (verb)
- Action: Create new reference topic: Create test-token

### ❌ Create password-recovery — `missing`
- Missing surface nodes (1):
  - `verb:POST:/password-recovery/{email}` — create_password-recovery (verb)
- Action: Create new reference topic: Create password-recovery

### ❌ Create reset-password — `missing`
- Missing surface nodes (1):
  - `verb:POST:/reset-password/` — create_reset-password (verb)
- Action: Create new reference topic: Create reset-password

### ❌ Create password-recovery-html-content — `missing`
- Missing surface nodes (1):
  - `verb:POST:/password-recovery-html-content/{email}` — create_password-recovery-html-content (verb)
- Action: Create new reference topic: Create password-recovery-html-content

### ❌ Create users — `missing`
- Missing surface nodes (1):
  - `verb:POST:/private/users/` — create_users (verb)
- Action: Create new reference topic: Create users

### ✅ Create test-email — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ❌ List health-check — `missing`
- Missing surface nodes (1):
  - `verb:GET:/utils/health-check/` — get_health-check (verb)
- Action: Create new reference topic: List health-check

### ❌ List items — `missing`
- Missing surface nodes (1):
  - `verb:GET:/items/` — get_items (verb)
- Action: Create new reference topic: List items

### ❌ Get items — `missing`
- Missing surface nodes (1):
  - `verb:GET:/items/{id}` — get_items (verb)
- Action: Create new reference topic: Get items

### ❌ Create items — `missing`
- Missing surface nodes (1):
  - `verb:POST:/items/` — create_items (verb)
- Action: Create new reference topic: Create items

### ❌ Update items — `missing`
- Missing surface nodes (1):
  - `verb:PUT:/items/{id}` — update_items (verb)
- Action: Create new reference topic: Update items

### ❌ Delete items — `missing`
- Missing surface nodes (1):
  - `verb:DELETE:/items/{id}` — delete_items (verb)
- Action: Create new reference topic: Delete items

### ❌ User — `missing`
- Missing surface nodes (1):
  - `noun:user` — user (noun)
- Action: Create new concept topic: User

### ❌ Util — `missing`
- Missing surface nodes (1):
  - `noun:util` — util (noun)
- Action: Create new concept topic: Util

### ❌ Item — `missing`
- Missing surface nodes (1):
  - `noun:item` — item (noun)
- Action: Create new concept topic: Item

### ✅ Technology Stack And Features — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Dashboard Login — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Dashboard - Admin — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Dashboard - Items — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Dashboard - Dark Mode — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Interactive Api Documentation — `complete`
- Matched to inventory topic: `atm_topic_2`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ How To Use It — `complete`
- Matched to inventory topic: `atm_topic_3`
- Quality issues: missing error docs

### ✅ How To Use A Private Repository — `complete`
- Matched to inventory topic: `atm_topic_3`
- Quality issues: missing error docs

### ✅ Update From The Original Template — `complete`
- Matched to inventory topic: `atm_topic_3`
- Quality issues: missing error docs

### ✅ Configure — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Generate Secret Keys — `complete`
- Matched to inventory topic: `atm_topic_3`
- Quality issues: missing error docs

### ✅ How To Use It - Alternative With Copier — `complete`
- Matched to inventory topic: `atm_topic_4`
- Quality issues: missing error docs

### ✅ Install Copier — `complete`
- Matched to inventory topic: `atm_topic_4`
- Quality issues: missing error docs

### ✅ Generate A Project With Copier — `complete`
- Matched to inventory topic: `atm_topic_4`
- Quality issues: missing error docs

### ✅ Input Variables — `complete`
- Matched to inventory topic: `atm_topic_4`
- Quality issues: missing error docs

### ❌ Backend Development — `missing`
- Missing surface nodes (1):
  - `concept:backend development` — backend development (concept)
- Action: Create new concept topic: Backend Development

### ❌ Frontend Development — `missing`
- Missing surface nodes (1):
  - `concept:frontend development` — frontend development (concept)
- Action: Create new concept topic: Frontend Development

### ❌ Release Notes — `missing`
- Missing surface nodes (1):
  - `concept:release notes` — release notes (concept)
- Action: Create new concept topic: Release Notes

### ✅ Note — `complete`
- Matched to inventory topic: `atm_topic_4`
- Quality issues: missing error docs

### ❌ Preparation — `missing`
- Missing surface nodes (1):
  - `concept:preparation` — preparation (concept)
- Action: Create new concept topic: Preparation

### ✅ Public Traefik — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Traefik Docker Compose — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Traefik Public Network — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Traefik Environment Variables — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Start The Traefik Docker Compose — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Deploy The Fastapi Project — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Required Environment Variables — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Github Actions Environment Variables — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Deploy With Docker Compose — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Continuous Deployment (Cd) — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Install Github Actions Runner — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Set Secrets — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Github Action Deployment Workflows — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Urls — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Main Traefik Dashboard — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Production — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ✅ Staging — `complete`
- Matched to inventory topic: `atm_topic_11`
- Quality issues: missing error docs

### ❌ Docker Compose — `missing`
- Missing surface nodes (1):
  - `concept:docker compose` — docker compose (concept)
- Action: Create new concept topic: Docker Compose

### ✅ Mailcatcher — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Local Development — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Docker Compose In `Localhost.Tiangolo.Com` — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Docker Compose Files And Env Vars — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ The .Env File — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Pre-Commits And Code Linting — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Development Urls — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Development Urls With `Localhost.Tiangolo.Com` Configured — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Removing The Frontend — `complete`
- Matched to inventory topic: `atm_topic_15`
- Quality issues: missing error docs, missing use cases

### ✅ Generate Client — `complete`
- Matched to inventory topic: `atm_topic_16`
- Quality issues: missing error docs, missing use cases

### ✅ Manually — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Using A Remote Api — `complete`
- Matched to inventory topic: `atm_topic_17`
- Quality issues: missing error docs

### ✅ Code Structure — `complete`
- Matched to inventory topic: `atm_topic_18`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ End-To-End Testing With Playwright — `complete`
- Matched to inventory topic: `atm_topic_19`
- Quality issues: missing error docs, missing use cases

### ❌ General Workflow — `missing`
- Missing surface nodes (1):
  - `concept:general workflow` — general workflow (concept)
- Action: Create new concept topic: General Workflow

### ✅ Vs Code — `complete`
- Matched to inventory topic: `atm_topic_23`
- Quality issues: missing error docs, missing examples, missing use cases

### ✅ Docker Compose Override — `complete`
- Matched to inventory topic: `atm_topic_12`
- Quality issues: missing error docs, auth-protected endpoint but no auth docs

### ✅ Backend Tests — `complete`
- Matched to inventory topic: `atm_topic_25`

### ✅ Test Running Stack — `complete`
- Matched to inventory topic: `atm_topic_25`

### ✅ Test Coverage — `complete`
- Matched to inventory topic: `atm_topic_25`

### ✅ Migrations — `complete`
- Matched to inventory topic: `atm_topic_26`

### ✅ Email Templates — `complete`
- Matched to inventory topic: `atm_topic_27`
- Quality issues: missing error docs, missing examples, missing use cases

### ❌ How to authenticate — `missing`
- Missing surface nodes (4):
  - `noun:user` — user (noun)
  - `verb:POST:/users/signup` — create_signup (verb)
  - `verb:POST:/login/access-token` — create_access-token (verb)
  - `verb:POST:/login/test-token` — create_test-token (verb)
- Action: Create new task topic: How to authenticate

### ❌ How to manage your account — `missing`
- Missing surface nodes (4):
  - `verb:PATCH:/users/me` — patch_me (verb)
  - `verb:PATCH:/users/me/password` — patch_password (verb)
  - `verb:GET:/users/me` — get_me (verb)
  - `verb:DELETE:/users/me` — delete_me (verb)
- Action: Create new task topic: How to manage your account

### ❌ How to recover your password — `missing`
- Missing surface nodes (3):
  - `verb:POST:/password-recovery/{email}` — create_password-recovery (verb)
  - `verb:POST:/reset-password/` — create_reset-password (verb)
  - `verb:POST:/password-recovery-html-content/{email}` — create_password-recovery-html-content (verb)
- Action: Create new task topic: How to recover your password

### ❌ How to work with Users — `missing`
- Missing surface nodes (17):
  - `noun:user` — user (noun)
  - `verb:GET:/users/` — get_users (verb)
  - `verb:POST:/users/` — create_users (verb)
  - `verb:PATCH:/users/me` — patch_me (verb)
  - `verb:PATCH:/users/me/password` — patch_password (verb)
  - `verb:GET:/users/me` — get_me (verb)
  - `verb:DELETE:/users/me` — delete_me (verb)
  - `verb:POST:/users/signup` — create_signup (verb)
  - `verb:GET:/users/{user_id}` — get_users (verb)
  - `verb:PATCH:/users/{user_id}` — patch_users (verb)
  - ... and 7 more
- Action: Create new task topic: How to work with Users

### ❌ How to work with Items — `missing`
- Missing surface nodes (6):
  - `noun:item` — item (noun)
  - `verb:GET:/items/` — get_items (verb)
  - `verb:GET:/items/{id}` — get_items (verb)
  - `verb:POST:/items/` — create_items (verb)
  - `verb:PUT:/items/{id}` — update_items (verb)
  - `verb:DELETE:/items/{id}` — delete_items (verb)
- Action: Create new task topic: How to work with Items

## Content Inventory (ATM) Details

### Technology Stack and Features — 20%
- Source: `README.md`
- Type: reference
- Covers: ['concept:technology stack and features', 'concept:dashboard - items', 'concept:dashboard - admin', 'concept:dashboard login', 'concept:dashboard - dark mode', 'concept:interactive api documentation']

### How To Use It — 40%
- Source: `README.md`
- Type: reference
- Covers: ['concept:update from the original template', 'concept:how to use it', 'concept:generate secret keys', 'concept:how to use a private repository']

### How To Use It - Alternative With Copier — 40%
- Source: `README.md`
- Type: reference
- Covers: ['concept:install copier', 'concept:how to use it - alternative with copier', 'concept:note', 'concept:input variables', 'concept:generate a project with copier']

### Deployment — 40%
- Source: `deployment.md`
- Type: reference
- Covers: ['concept:production', 'concept:public traefik', 'concept:traefik environment variables', 'concept:traefik public network', 'concept:traefik docker compose', 'concept:main traefik dashboard', 'concept:github action deployment workflows', 'concept:continuous deployment (cd)', 'concept:start the traefik docker compose', 'concept:urls', 'concept:install github actions runner', 'concept:set secrets', 'concept:deploy with docker compose', 'concept:staging', 'concept:required environment variables', 'concept:deploy the fastapi project', 'concept:github actions environment variables']

### Development — 40%
- Source: `development.md`
- Type: reference
- Covers: ['concept:local development', 'concept:docker compose override', 'verb:POST:/utils/test-email/', 'concept:configure', 'concept:pre-commits and code linting', 'concept:the .env file', 'concept:development urls with `localhost.tiangolo.com` configured', 'concept:docker compose files and env vars', 'concept:docker compose in `localhost.tiangolo.com`', 'concept:development urls', 'concept:manually', 'concept:mailcatcher']

### Quick Start — 40%
- Source: `frontend/README.md`
- Type: reference
- Covers: ['concept:removing the frontend']

### Generate Client — 40%
- Source: `frontend/README.md`
- Type: reference
- Covers: ['concept:generate client']

### Using a Remote API — 40%
- Source: `frontend/README.md`
- Type: reference
- Covers: ['concept:using a remote api']

### Code Structure — 20%
- Source: `frontend/README.md`
- Type: reference
- Covers: ['concept:code structure']

### End-to-End Testing with Playwright — 40%
- Source: `frontend/README.md`
- Type: reference
- Covers: ['concept:end-to-end testing with playwright']

### VS Code — 20%
- Source: `backend/README.md`
- Type: reference
- Covers: ['concept:vs code']

### Backend tests — 50%
- Source: `backend/README.md`
- Type: reference
- Covers: ['concept:test running stack', 'concept:test coverage', 'concept:backend tests']

### Migrations — 50%
- Source: `backend/README.md`
- Type: reference
- Covers: ['concept:migrations']

### Email Templates — 20%
- Source: `backend/README.md`
- Type: reference
- Covers: ['concept:email templates']
