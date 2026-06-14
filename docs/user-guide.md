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

> **Rate limiting:** After 10 failed login attempts within 60 seconds from the same IP address, further attempts are blocked for the remainder of that window. Wait 60 seconds and try again.

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

| Current status | Can move to |
|---------------|-------------|
| To Do | In Progress, Cancelled |
| In Progress | In Review, To Do (undo), Cancelled |
| In Review | Done, In Progress (undo), Cancelled |
| Done | — (terminal) |
| Cancelled | — (terminal) |

**DONE** and **CANCELLED** are terminal states. Once a task reaches either, it cannot be moved again.

### Business rules enforced server-side

The server rejects any transition not in the table above with `422 Unprocessable Entity`. The UI only shows valid next-state buttons, so you cannot reach this error through the normal interface — it protects against direct API misuse.

---

## Logging Out

There is no logout button in the current UI. To end your session:

1. Open your browser's developer tools (F12 → Application → Local Storage)
2. Delete the `access_token` entry for `localhost:5173`
3. Refresh the page — you will be redirected to the login screen

Alternatively, closing the browser tab or clearing site data achieves the same result. Your account and data are preserved; only the local session token is removed.

---

## Advanced: API & Swagger UI

Everything in the web UI is backed by the REST API. The Swagger UI at **http://localhost:8000/docs** gives you full access to every endpoint, including features not yet in the web UI:

| Feature | Endpoint | Available in UI? |
|---------|----------|-----------------|
| Register account | `POST /auth/register` | No — use API |
| Log in | `POST /auth/login` | ✅ |
| List / create projects | `GET / POST /projects` | ✅ |
| List / create tasks | `GET / POST /projects/{id}/tasks` | ✅ |
| Update task title, description, priority | `PATCH /projects/{id}/tasks/{taskId}` | No — use API |
| Move task status | `PATCH /projects/{id}/tasks/{taskId}` | ✅ (buttons) |
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
| Log out | Clear `access_token` from browser LocalStorage |
| API documentation | http://localhost:8000/docs |
