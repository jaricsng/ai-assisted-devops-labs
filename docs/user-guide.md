# User Guide — Task Manager

A practical walkthrough of every feature available in the Task Manager web application.

---

## Accessing the Application

Open your browser and go to:

```
http://localhost:5173
```

The application requires the stack to be running. If you see a blank page or connection error, ask your administrator to start the services — see [docs/operations.md](operations.md).

You will be redirected to the login page automatically if you are not signed in.

---

## Demo Account

A demo account with sample data is included for quick exploration. To load it, run once after starting the stack:

```bash
docker compose exec api python seed.py
```

Then log in immediately with:

| Field | Value |
|-------|-------|
| Email | `demo@example.com` |
| Password | `Demo1234!` |

The demo account includes two projects — **Website Redesign** and **Payment & Notifications Integration** — each with six tasks spread across every status column.

To reset back to a clean slate: `docker compose down -v && docker compose up -d`, then run `seed.py` again.

---

## Creating an Account

There is no registration form in the web UI. Accounts are created via the API. You have two options:

### Option A — Swagger UI (browser)

1. Open **http://localhost:8000/docs**
2. Expand **POST /auth/register**
3. Click **Try it out**
4. Fill in the request body:

```json
{
  "email": "you@example.com",
  "full_name": "Your Name",
  "password": "MyPassword1"
}
```

5. Click **Execute** — a `201 Created` response confirms success

### Option B — curl (terminal)

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","full_name":"Your Name","password":"MyPassword1"}'
```

### Password requirements

Passwords must meet all three rules:

| Rule | Example |
|------|---------|
| At least 8 characters | `short` ❌ → `longer1A` ✅ |
| At least one uppercase letter | `password1` ❌ → `Password1` ✅ |
| At least one digit | `Password` ❌ → `Password1` ✅ |

If any rule is not met, the API returns `422 Unprocessable Entity` with details.

---

## Logging In

1. Go to **http://localhost:5173/login**
2. Enter your **email** and **password**
3. Click **Log in**

On success you are taken directly to the Projects page. On failure, an "Invalid email or password" message appears below the form.

> **Rate limiting:** The login endpoint allows 10 requests per 60 seconds per IP address. All login attempts count toward this limit — including successful ones. After the 10th request in a window, further attempts return `429 Too Many Requests`. Wait for the 60-second window to expire and try again.

---

## Projects

Projects are the top-level containers. Each project holds a set of tasks.

### View all projects

After logging in you land on the **Projects** page (`/projects`). All projects you own are listed here, with their names as clickable links.

### Create a project

1. Type a project name in the **"New project name"** input at the top of the page
2. Click **Create**

The new project appears in the list immediately.

### Open a project

Click the project name link to open its **Kanban board**.

> **Navigation note:** The current UI has no breadcrumb or "back to projects" link on the board page. Use your browser's **Back** button to return to the projects list, or go directly to `http://localhost:5173/projects`.

---

## Tasks

Tasks live inside a project. Every task moves through a status workflow on the Kanban board.

### The Kanban Board

The board has four visible columns, left to right:

| Column | Status value | Meaning |
|--------|-------------|---------|
| **To Do** | `TODO` | Not started — the default for new tasks |
| **In Progress** | `IN_PROGRESS` | Actively being worked on |
| **In Review** | `IN_REVIEW` | Submitted for review or testing |
| **Done** | `DONE` | Completed — no further transitions possible |

Tasks can also be **Cancelled** (`CANCELLED`). Cancelled tasks are removed from the board columns and are not shown.

### Create a task

1. On the project page, type a task title in the **"New task title"** input
2. Click **Add Task**

The task appears in the **To Do** column immediately. New tasks default to **MEDIUM** priority.

> **Current UI limitation:** The project page heading shows **"Project #N"** (the numeric ID) rather than the project name. The project name is visible on the projects list and in your browser tab. This is a known UI gap for students to address in Module 6.

### Task card

Each card shows:

- **Title** — what the task is
- **Priority badge** — colour-coded in the top-right corner
- **Description** — shown below the title if one was set (editable via API)
- **Transition buttons** — the valid next statuses for this task

### Priority levels

| Priority | Colour | Meaning |
|----------|--------|---------|
| LOW | Grey | Background item, no urgency |
| MEDIUM | Blue | Normal work item (default) |
| HIGH | Amber | Needs attention soon |
| URGENT | Red | Drop everything, do this now |

Priority is set when creating a task via the API or Swagger UI. The web UI defaults all new tasks to MEDIUM.

---

## Moving Tasks Through the Workflow

Click one of the **→ Status** buttons on a task card to advance it. Only valid transitions are offered — the buttons shown change as the task moves forward.

### Allowed transitions

```
TODO ──────────────► IN_PROGRESS ──────────────► IN_REVIEW ──────────────► DONE
  │                      │    ▲                     │    ▲
  │                      │    │                     │    │
  └──► CANCELLED          └──► TODO                  └──► IN_PROGRESS
                          └──► CANCELLED              └──► CANCELLED
```

| Current status | Can move to (buttons shown left → right) |
|---------------|------------------------------------------|
| To Do | In Progress, Cancelled |
| In Progress | In Review, To Do (undo), Cancelled |
| In Review | In Progress (undo), Done, Cancelled |
| Done | — (terminal) |
| Cancelled | — (terminal) |

**DONE** and **CANCELLED** are terminal states. Once a task reaches either, it cannot be moved again.

### Business rules enforced server-side

The server rejects any transition not in the table above with `422 Unprocessable Entity`. The UI only shows valid next-state buttons, so you cannot reach this error through the normal interface — it protects against direct API misuse.

---

## Logging Out

> **Current UI limitation:** The web UI has no logout button. Log out via the API (preferred) or by clearing your local session (fallback).

The API supports server-side session revocation via `POST /auth/logout`. Calling it immediately invalidates the current JWT — any further requests using the same token return `401 Unauthorized`, even if the token has not yet expired. This is the secure method and the one the pen test verifies.

### Option A — Swagger UI (preferred)

1. Open **http://localhost:8000/docs**
2. Ensure you are authorized (padlock icon, top right)
3. Expand **POST /auth/logout** → **Try it out** → **Execute**
4. A `204 No Content` response confirms the token is revoked

### Option B — curl

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer <your-access-token>"
# 204 No Content — token is now revoked
```

### Option C — clear local session (fallback only)

If you cannot reach the API:
1. Open browser developer tools (F12 → Application → Local Storage)
2. Delete the `access_token` entry for `localhost:5173`
3. Refresh — you are redirected to the login screen

> **Note:** Option C only removes your local copy of the token. The JWT remains valid on the server until it expires. Use Option A or B to prevent reuse if the token may have been captured.

---

## Account Deletion (GDPR Right to Erasure)

To permanently close your account, call `DELETE /auth/users/me`:

```bash
curl -X DELETE http://localhost:8000/auth/users/me \
  -H "Authorization: Bearer <your-access-token>"
# 204 No Content — account soft-deleted
```

After deletion:
- Login with the same email returns `401 Invalid credentials`
- Any existing tokens return `401 User not found`
- Your data is retained in the database with a `deleted_at` timestamp for audit compliance
- To re-register, you must use a different email address

This satisfies GDPR Article 17 (right to erasure) in the context of this application.

---

## Advanced: API & Swagger UI

Everything in the web UI is backed by the REST API. The Swagger UI at **http://localhost:8000/docs** gives you full access to every endpoint, including features not yet in the web UI:

| Feature | Endpoint | Available in UI? |
|---------|----------|-----------------|
| Register account | `POST /auth/register` | No — use Swagger UI or curl (no registration form) |
| Log in | `POST /auth/login` | ✅ — `/login` page |
| Log out (revoke token) | `POST /auth/logout` | No — use Swagger UI or curl (no logout button) |
| Delete account (GDPR) | `DELETE /auth/users/me` | No — use Swagger UI or curl |
| List projects | `GET /projects` | ✅ — Projects page |
| Create project | `POST /projects` | ✅ — Projects page form |
| List tasks (Kanban board) | `GET /projects/{id}/tasks` | ✅ — Project detail page |
| Create task | `POST /projects/{id}/tasks` | ✅ — Project detail page form |
| Move task status | `PATCH /projects/{id}/tasks/{taskId}` | ✅ — transition buttons on task card |
| Update task title, description, priority | `PATCH /projects/{id}/tasks/{taskId}` | No — use API |
| Delete a task | `DELETE /projects/{id}/tasks/{taskId}` | No — use API |
| Delete a project | `DELETE /projects/{id}` | No — use API |
| Add a comment to a task | `POST /projects/{id}/tasks/{taskId}/comments` | No — use API |
| List comments on a task | `GET /projects/{id}/tasks/{taskId}/comments` | No — use API |

### Authenticating in Swagger UI

1. Open **http://localhost:8000/docs**
2. Call `POST /auth/login` with your credentials → copy the `access_token` value from the response
3. Click the **Authorize** button (padlock icon, top right)
4. Paste the token in the **Value** field: `Bearer <your-token>`
5. Click **Authorize** — all subsequent calls will include your token

---

## Monitoring & Observability

The observability stack (Jaeger, Prometheus, Grafana) lets you see what the API is doing in real time as you use the application. It runs as an optional set of containers alongside the core stack.

### Start the observability stack

```bash
docker compose --profile observability up -d
```

If the core stack is already running, this adds Jaeger, Prometheus, Grafana, and the Blackbox Exporter without restarting the API or frontend.

### Service URLs

| Tool | URL | Credentials | Purpose |
|------|-----|-------------|---------|
| Jaeger | http://localhost:16686 | — | Distributed trace UI |
| Prometheus | http://localhost:9090 | — | Metrics query UI |
| Grafana | http://localhost:3000 | admin / admin | Dashboards and alerts |
| Blackbox Exporter | http://localhost:9115 | — | Readiness probe metrics |

---

### Jaeger — trace a user action

Every API request generates a distributed trace. Use Jaeger to see the full lifecycle of any action — the middleware chain, SQL queries, and response time broken down by layer.

**Steps:**

1. Open **http://localhost:16686**
2. Select **`task-manager-api`** from the **Service** dropdown
3. Click **Find Traces**
4. Click any trace row to expand it

**What to look for:**

- The root span shows the total request duration (e.g., `POST /projects/{id}/tasks`)
- Child spans show each middleware (rate limit check, logging, security headers) and each SQLAlchemy query
- A slow child span pointing at `sqlalchemy` is a database bottleneck; a slow root span with fast children is application-layer overhead

**Try it:** Create a task in the UI, then immediately open Jaeger and find the `POST /projects/{id}/tasks` trace. Expand the SQLAlchemy span to see the INSERT statement that was executed.

---

### Prometheus — query live metrics

Prometheus scrapes the API's `/metrics` endpoint every 15 seconds. Open **http://localhost:9090** and paste any of these queries into the expression bar, then click **Execute**.

```promql
# Requests per second across all endpoints
rate(http_server_request_count_total[1m])

# P95 response time in milliseconds
histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[5m])) * 1000

# Error rate (5xx responses only)
rate(http_server_request_count_total{http_response_status_code=~"5.."}[5m])

# Rate-limited requests (429 Too Many Requests)
rate(http_server_request_count_total{http_response_status_code="429"}[1m])
```

> **No data?** Generate some traffic first (`curl http://localhost:8000/health` a few times), then widen the Prometheus time range using the **Graph** tab.

---

### Grafana — dashboards and alerts

Grafana provides a pre-provisioned dashboard that combines the Prometheus metrics and Jaeger traces in one view.

1. Open **http://localhost:3000** and log in with `admin` / `admin`
2. Go to **Dashboards** → find the **Task Manager** dashboard
3. Set the time range (top right) to **Last 15 minutes** if panels show "No data"

**Pre-configured alerts** (visible under Alerting → Alert rules):

| Alert | Triggers when |
|-------|--------------|
| `HighErrorRate` | 5xx error rate > 5% for 5 minutes |
| `HighLatency` | P95 latency > 500 ms for 5 minutes |
| `DatabaseUnreachable` | `/ready` returns 503 for more than 1 minute |
| `HighRejectionRate` | 429 rate > 50/min (potential brute-force signal) |

> **`DatabaseUnreachable` never fires?** This alert depends on the Blackbox Exporter probing `/ready`. If you stopped and restarted only the core stack (without `--profile observability`), the exporter is not running — restart with the full profile.

---

### Practical walkthrough: observe a task creation end-to-end

1. **Create a task** — use the UI or `POST /projects/{id}/tasks` in Swagger
2. **Jaeger** → find the `POST /projects/{id}/tasks` trace → note total duration and the SQL INSERT span
3. **Prometheus** → run `rate(http_server_request_count_total[1m])` → confirm the request appears in the series labelled with your endpoint
4. **Grafana** → open the Task Manager dashboard → see the request reflected in the Request Rate panel

This end-to-end view connects what you do in the UI to what happens inside the API — the foundation of Module 05b (Observability).

---

## Quick Reference

| Action | How |
|--------|-----|
| Create account | Swagger UI → POST /auth/register, or `curl` |
| Log in | http://localhost:5173/login |
| Create a project | Projects page → type name → Create |
| Open a project | Click the project name |
| Create a task | Project page → type title → Add Task |
| Move a task | Click the → button on the task card |
| Cancel a task | Click → Cancelled on the task card |
| Update title / priority / description | Swagger UI → PATCH /projects/{id}/tasks/{taskId} |
| Add a comment | Swagger UI → POST /projects/{id}/tasks/{taskId}/comments |
| Log out (server-side) | Swagger UI → POST /auth/logout, or `curl` (no UI button) |
| Delete account | `DELETE /auth/users/me` via Swagger UI or curl |
| API documentation | http://localhost:8000/docs |
