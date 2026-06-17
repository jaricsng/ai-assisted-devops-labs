# UML Diagrams — Task Manager

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively in GitHub, VS Code (with the Mermaid Preview extension), and Claude Code.

---

## 1. Architecture Diagram

Shows how the three tiers, .NET Aspire (preferred local dev) / Docker Compose, and the CI/CD pipeline fit together.

```mermaid
graph TD
    subgraph Client["Client"]
        BR[Browser]
    end

    subgraph FE["Frontend Tier — React 18 + TypeScript (Vite · port 5173)"]
        direction TB
        Pages["Pages\nLoginPage · ProjectsPage · ProjectDetailPage"]
        Components["Components\nKanbanBoard · TaskCard · TaskDetailPanel"]
        APIClient["API Client\naxios + Tanstack Query"]
        Pages --> Components --> APIClient
    end

    subgraph BE["Business Logic Tier — FastAPI (Python 3.12 · port 8000)"]
        direction TB
        Middleware["Middleware Stack (outermost→innermost)\nSecurityHeaders · CORS · MaxBodySize · RateLimit(/auth/login) · RequestLogging · Metrics"]
        Routers["Routers\n/auth · /projects\n/projects/{id}/tasks\n/projects/{id}/tasks/{id}/comments"]
        Services["Services\nTaskService · AuthService"]
        Repos["Repositories\nUserRepo · ProjectRepo · TaskRepo · CommentRepo"]
        Middleware --> Routers --> Services --> Repos
    end

    subgraph DB["Data Tier — PostgreSQL 16 (port 5432)"]
        Tables["Tables\nusers · projects · tasks · comments"]
    end

    subgraph OBS["Observability Stack (--profile observability)"]
        direction LR
        Jaeger["Jaeger\nport 16686\ntrace UI"]
        Prometheus["Prometheus\nport 9090\nmetrics"]
        Grafana["Grafana\nport 3000\ndashboards + alerts"]
        Blackbox["Blackbox Exporter\nport 9115\nreadiness probe"]
        Blackbox -->|"probe_success metric"| Prometheus
        Prometheus --> Grafana
        Jaeger --> Grafana
    end

    subgraph CI["CI/CD — GitHub Actions"]
        direction TB
        CIJobs["ci.yml — every push\nbackend: black · isort · ruff · pytest ≥70%\nfrontend: tsc · eslint · vitest ≥70%\nsecurity: bandit (hard gate) · pip-audit · npm audit · secret grep\ndocker-build: docker compose build\nsmoke-test: k6 smoke (PRs to main only)\ne2e: Playwright (PRs to main only)\nterraform-plan+tfsec: IaC scan (PRs only)"]
        CDJobs["publish.yml — push to main\nbuild → GHCR (sha-commit + latest tag)\nTrivy scan → SARIF (CRITICAL/HIGH hard gate)\nSBOM → CycloneDX JSON artifact\ncosign verify (image signature attestation)\ncloud deploy: Azure CA · AWS ECS · GCP CR · Fly.io (each gated by if:false)\nZAP baseline scan (post-deploy DAST, gated by if:false)"]
        CIJobs --> CDJobs
    end

    BR -->|"HTTP · port 5173"| FE
    APIClient -->|"REST/JSON · port 8000"| BE
    Repos -->|"SQL · asyncpg · port 5432"| DB
    BE -->|"traces (OTLP gRPC :4317)"| Jaeger
    BE -->|"metrics (/metrics)"| Prometheus
    Blackbox -->|"probe GET /ready"| BE
    CI -.->|"quality gate on every push"| BE
    CI -.->|"quality gate on every push"| FE
```

---

## 2. Use Case Diagram

Shows what each actor can do in the system. Mermaid does not have a native use-case diagram type; this uses a directed graph with actor and use-case shapes.

```mermaid
graph LR
    Guest(["👤 Guest"])
    AuthUser(["👤 Authenticated User"])
    System(["⚙️ System"])

    subgraph AuthUseCases["Authentication"]
        UC1["Register account"]
        UC2["Log in"]
        UC3["Log out"]
    end

    subgraph ProjectUseCases["Project Management"]
        UC4["Create project"]
        UC5["View project list"]
        UC6["View project detail"]
        UC7["Delete project"]
    end

    subgraph TaskUseCases["Task Management"]
        UC8["Create task"]
        UC9["View Kanban board"]
        UC10["Update task status"]
        UC11["Assign task to user"]
        UC12["Set task priority"]
        UC13["Set due date"]
        UC14["Delete task"]
    end

    subgraph CommentUseCases["Collaboration"]
        UC15["Add comment"]
        UC16["View comments"]
    end

    subgraph SystemUseCases["System"]
        UC17["Enforce status transition rules"]
        UC18["Validate JWT token"]
        UC19["Hash & verify password"]
        UC20["Revoke JTI on logout"]
        UC21["Emit structured audit log"]
    end

    Guest --> UC1
    Guest --> UC2

    AuthUser --> UC3
    AuthUser --> UC4
    AuthUser --> UC5
    AuthUser --> UC6
    AuthUser --> UC7
    AuthUser --> UC8
    AuthUser --> UC9
    AuthUser --> UC10
    AuthUser --> UC11
    AuthUser --> UC12
    AuthUser --> UC13
    AuthUser --> UC14
    AuthUser --> UC15
    AuthUser --> UC16

    subgraph AccountUseCases["Account Management"]
        UC22["Delete account (GDPR)"]
    end

    AuthUser --> UC22

    UC10 -.->|"«includes»"| UC17
    UC4 & UC5 & UC6 & UC8 & UC9 & UC10 & UC15 -.->|"«includes»"| UC18
    UC1 & UC2 -.->|"«includes»"| UC19
    UC3 -.->|"«includes»"| UC20
    UC4 & UC7 & UC8 & UC10 & UC14 -.->|"«includes»"| UC21

    System --> UC17
    System --> UC18
    System --> UC19
    System --> UC20
    System --> UC21
```

---

## 3. Sequence Diagrams

### 3a. Happy Path — Task Status Transition (TODO → IN_PROGRESS)

```mermaid
sequenceDiagram
    actor User
    participant React as React App
    participant Router as FastAPI Router<br/>(tasks.py)
    participant Deps as Auth Dependency<br/>(deps.py)
    participant Service as Task Service<br/>(task_service.py)
    participant Repo as Task Repository<br/>(task_repository.py)
    participant DB as PostgreSQL

    User->>React: Click "→ In Progress" on a task card
    React->>Router: PATCH /projects/1/tasks/3<br/>{ "status": "IN_PROGRESS" }<br/>Authorization: Bearer <token>

    Router->>Deps: Resolve current_user(token)
    Deps->>DB: SELECT * FROM users WHERE id = <token.sub>
    DB-->>Deps: User row
    Deps-->>Router: user object

    Router->>Repo: get_by_id(db, project_id=1)
    Repo->>DB: SELECT * FROM projects WHERE id=1
    DB-->>Repo: Project row
    Repo-->>Router: project (owner check passes)

    Router->>Repo: get_by_id(db, task_id=3)
    Repo->>DB: SELECT * FROM tasks WHERE id=3
    DB-->>Repo: Task { status: "TODO" }
    Repo-->>Router: task

    Router->>Service: apply_task_update(task, TaskUpdate{status: IN_PROGRESS})
    Service->>Service: validate_status_transition(TODO, IN_PROGRESS)
    Note over Service: VALID_TRANSITIONS[TODO] = {IN_PROGRESS, CANCELLED}<br/>IN_PROGRESS ∈ allowed ✓
    Service-->>Router: mutated task { status: "IN_PROGRESS" }

    Router->>Repo: save(db, task)
    Repo->>DB: UPDATE tasks SET status='IN_PROGRESS' WHERE id=3
    DB-->>Repo: updated row
    Repo-->>Router: Task { status: "IN_PROGRESS" }

    Router-->>React: 200 OK<br/>{ "id": 3, "status": "IN_PROGRESS", ... }
    React->>React: invalidateQueries(["tasks", 1])
    React-->>User: Task card moves to "In Progress" column
```

### 3b. Error Path — Invalid Status Transition (TODO → DONE)

```mermaid
sequenceDiagram
    actor User
    participant React as React App
    participant Router as FastAPI Router
    participant Service as Task Service
    participant Repo as Task Repository
    participant DB as PostgreSQL

    User->>React: API call with status "DONE"<br/>(or future UI bug / direct API call)
    React->>Router: PATCH /projects/1/tasks/3<br/>{ "status": "DONE" }

    Router->>Repo: get_by_id(db, task_id=3)
    Repo->>DB: SELECT * FROM tasks WHERE id=3
    DB-->>Repo: Task { status: "TODO" }
    Repo-->>Router: task

    Router->>Service: apply_task_update(task, TaskUpdate{status: DONE})
    Service->>Service: validate_status_transition(TODO, DONE)
    Note over Service: VALID_TRANSITIONS[TODO] = {IN_PROGRESS, CANCELLED}<br/>DONE ∉ allowed ✗
    Service-->>Router: raise HTTPException(422,<br/>"Cannot transition from 'TODO' to 'DONE'.<br/>Allowed: ['IN_PROGRESS', 'CANCELLED']")

    Router-->>React: 422 Unprocessable Entity<br/>{ "detail": "Cannot transition from 'TODO' to 'DONE'..." }
    React-->>User: Display error message
    Note over DB: Database is never touched — rule<br/>enforced in the service layer
```

### 3c. Authentication Flow — Login and Token Usage

```mermaid
sequenceDiagram
    actor User
    participant React as React App
    participant AuthRouter as Auth Router<br/>(/auth)
    participant AuthService as Auth Service
    participant UserRepo as User Repository
    participant DB as PostgreSQL

    User->>React: Submit login form (email, password)
    React->>AuthRouter: POST /auth/login<br/>{ "email": "...", "password": "..." }

    AuthRouter->>UserRepo: get_by_email(db, email)
    UserRepo->>DB: SELECT * FROM users WHERE email=?
    DB-->>UserRepo: User row
    UserRepo-->>AuthRouter: user

    AuthRouter->>AuthService: verify_password(plain, user.hashed_password)
    Note over AuthService: bcrypt.verify(plain, hash)
    AuthService-->>AuthRouter: True

    AuthRouter->>AuthService: create_access_token(str(user.id))
    Note over AuthService: jwt.encode({sub: "42", exp: now+30min},<br/>SECRET_KEY, HS256)
    AuthService-->>AuthRouter: signed JWT string

    AuthRouter-->>React: 200 OK<br/>{ "access_token": "<jwt>", "token_type": "bearer" }
    React->>React: localStorage.setItem("access_token", jwt)
    React-->>User: Redirect to /projects

    Note over React,AuthRouter: All subsequent requests include:<br/>Authorization: Bearer <jwt>
```

### 3d. Logout and Token Revocation

```mermaid
sequenceDiagram
    actor User
    participant React as React App
    participant AuthRouter as Auth Router
    participant Deps as Auth Dependency
    participant AuthService as Auth Service

    User->>React: Click "Log out"
    React->>AuthRouter: POST /auth/logout<br/>Authorization: Bearer &lt;jwt&gt;
    AuthRouter->>Deps: current_user(request, credentials)
    Deps->>AuthService: get_token_payload(token)
    AuthService-->>Deps: {sub: "42", exp: ..., jti: "uuid-xyz"}
    Deps-->>AuthRouter: user, request.state.jti = "uuid-xyz"
    AuthRouter->>AuthService: revoke_token("uuid-xyz")
    Note over AuthService: _revoked_jtis.add("uuid-xyz")
    AuthService-->>AuthRouter: (void)
    AuthRouter-->>React: 204 No Content
    React->>React: localStorage.removeItem("access_token")
    React-->>User: Redirect to /login

    Note over React,AuthService: Subsequent request with the same token:
    React->>AuthRouter: GET /projects<br/>Authorization: Bearer &lt;same-jwt&gt;
    AuthRouter->>Deps: current_user(request, credentials)
    Deps->>AuthService: is_revoked("uuid-xyz") → True
    Deps-->>AuthRouter: raise 401 "Token has been revoked"
    AuthRouter-->>React: 401 Unauthorized
```

### 3e. GDPR Account Deletion

```mermaid
sequenceDiagram
    actor User
    participant React as React App
    participant AuthRouter as Auth Router
    participant Deps as Auth Dependency
    participant UserRepo as User Repository
    participant DB as PostgreSQL

    User->>React: Request account deletion
    React->>AuthRouter: DELETE /auth/users/me<br/>Authorization: Bearer &lt;jwt&gt;
    AuthRouter->>Deps: current_user(request, credentials)
    Deps-->>AuthRouter: user object (id=42)
    AuthRouter->>UserRepo: soft_delete(db, user_id=42)
    UserRepo->>DB: UPDATE users SET deleted_at=NOW() WHERE id=42
    DB-->>UserRepo: 1 row updated
    Note over DB: Record marked deleted; data retained for audit trail
    AuthRouter-->>React: 204 No Content

    Note over React,DB: Subsequent login attempt:
    React->>AuthRouter: POST /auth/login {email, password}
    AuthRouter->>UserRepo: get_by_email(db, email)
    UserRepo->>DB: SELECT ... WHERE email=? AND deleted_at IS NULL
    DB-->>UserRepo: (empty — user is soft-deleted)
    UserRepo-->>AuthRouter: None
    AuthRouter-->>React: 401 "Invalid credentials"
```

### 3f. Rate-Limited Login (429 Too Many Requests)

Shows the sliding-window rate limiter intercepting a brute-force credential stuffing attempt before the request reaches the auth router. See ADR 0007.

```mermaid
sequenceDiagram
    actor Attacker
    participant RL as RateLimitMiddleware<br/>(rate_limit.py)
    participant Router as Auth Router<br/>(/auth/login)
    participant DB as PostgreSQL

    Note over Attacker,DB: Requests 1–10 succeed (within 10 req/60 s window)
    loop First 10 attempts
        Attacker->>RL: POST /auth/login { email, password }
        RL->>RL: len(bucket) < 10 — append timestamp
        RL->>Router: pass through
        Router->>DB: SELECT user WHERE email=?
        DB-->>Router: user row
        Router-->>Attacker: 200 OK / 401 (wrong password)
    end

    Note over Attacker,DB: 11th attempt — bucket full, window not expired
    Attacker->>RL: POST /auth/login { email, password }
    RL->>RL: drop timestamps older than 60 s from deque front
    RL->>RL: len(bucket) >= 10 — compute Retry-After
    Note over RL: Retry-After = window - (now - bucket[0]) + 1
    RL-->>Attacker: 429 Too Many Requests<br/>{ "detail": "Too many login attempts. Please try again later." }<br/>Retry-After: N

    Note over Router,DB: Router and DB never reached — request blocked in middleware
```

### 3g. Observability — Request Instrumentation Flow

Shows how a single API request generates a structured log entry, a distributed trace (sent to Jaeger), and a metrics data point (scraped by Prometheus). See ADR 0006.

```mermaid
sequenceDiagram
    participant Client
    participant RLM as RequestLoggingMiddleware
    participant MM as MetricsMiddleware
    participant OTel as OTel SDK<br/>(FastAPIInstrumentor)
    participant Router as FastAPI Router
    participant SQLInstr as SQLAlchemyInstrumentor
    participant DB as PostgreSQL
    participant Jaeger
    participant Prometheus

    Client->>RLM: GET /projects (Bearer token)
    RLM->>RLM: bind contextvars<br/>(request_id, method, path)
    RLM->>RLM: logger.info("request_received")
    RLM->>MM: pass through
    MM->>OTel: pass through
    OTel->>OTel: start span<br/>"GET /projects"
    OTel->>Router: pass through

    Router->>SQLInstr: query project_repository.get_all_for_user()
    SQLInstr->>SQLInstr: start child span<br/>"SELECT projects WHERE owner_id=?"
    SQLInstr->>DB: SELECT * FROM projects WHERE owner_id=? AND deleted_at IS NULL
    DB-->>SQLInstr: rows
    SQLInstr->>SQLInstr: end child span (duration recorded)
    SQLInstr-->>Router: project list

    Router-->>OTel: 200 OK
    OTel->>OTel: end span (status=OK, http.status_code=200)
    OTel->>OTel: BatchSpanProcessor buffers span

    OTel-->>MM: response
    MM->>MM: record http_request_duration histogram<br/>(labels: method=GET, route=/projects, status=200)
    MM-->>RLM: response

    RLM->>RLM: bind user_id from request.state<br/>logger.info("request_finished", duration_ms=N)
    RLM-->>Client: 200 OK

    Note over OTel,Jaeger: Async — BatchSpanProcessor flushes every 5 s
    OTel-->>Jaeger: OTLP gRPC — span batch (trace_id, spans, durations)

    Note over MM,Prometheus: Pull-based — Prometheus scrapes /metrics every 15 s
    Prometheus->>MM: GET /metrics
    MM-->>Prometheus: Prometheus text format<br/>(http_server_request_duration_seconds histogram)
```

---

## 4. Class Diagram

Shows the domain model, service layer, and repository layer with their relationships.

```mermaid
classDiagram
    direction TB

    %% ── Enumerations ──────────────────────────────────────────────
    class TaskStatus {
        <<enumeration>>
        TODO
        IN_PROGRESS
        IN_REVIEW
        DONE
        CANCELLED
    }

    class TaskPriority {
        <<enumeration>>
        LOW
        MEDIUM
        HIGH
        URGENT
    }

    %% ── Domain Models (SQLAlchemy ORM) ────────────────────────────
    class User {
        +int id
        +str email
        +str full_name
        +str hashed_password
        +datetime created_at
        +datetime deleted_at
        --
        +list~Project~ owned_projects
        +list~Task~ assigned_tasks
        +list~Comment~ comments
    }

    class Project {
        +int id
        +str name
        +str description
        +int owner_id
        +datetime created_at
        +datetime deleted_at
        --
        +User owner
        +list~Task~ tasks
    }

    class Task {
        +int id
        +int project_id
        +str title
        +str description
        +TaskStatus status
        +TaskPriority priority
        +int assignee_id
        +date due_date
        +datetime created_at
        +datetime updated_at
        +datetime deleted_at
        --
        +Project project
        +User assignee
        +list~Comment~ comments
    }

    class Comment {
        +int id
        +int task_id
        +int author_id
        +str body
        +datetime created_at
        +datetime deleted_at
        --
        +Task task
        +User author
    }

    %% ── Service Layer (business logic, no SQLAlchemy) ─────────────
    class TaskService {
        <<service>>
        +validate_status_transition(current TaskStatus, next_status TaskStatus) None
        +apply_task_update(task Task, update TaskUpdate) Task
    }

    class AuthService {
        <<service>>
        +hash_password(password str) str
        +verify_password(plain str, hashed str) bool
        +create_access_token(subject str) str
        +decode_access_token(token str) str
        +get_token_payload(token str) dict
        +revoke_token(jti str) None
        +is_revoked(jti str) bool
    }

    %% ── Repository Layer (SQL only, no business logic) ────────────
    class UserRepository {
        <<repository>>
        +get_by_email(db, email str) User
        +get_by_id(db, user_id int) User
        +create(db, email, full_name, hashed_password) User
        +soft_delete(db, user_id int) None
    }

    class ProjectRepository {
        <<repository>>
        +get_all_for_user(db, owner_id int) list~Project~
        +get_by_id(db, project_id int) Project
        +create(db, name, description, owner_id) Project
        +delete(db, project Project) None
    }

    class TaskRepository {
        <<repository>>
        +get_all_for_project(db, project_id int) list~Task~
        +get_by_id(db, task_id int) Task
        +create(db, project_id, title, ...) Task
        +save(db, task Task) Task
        +delete(db, task Task) None
    }

    class CommentRepository {
        <<repository>>
        +get_all_for_task(db, task_id int) list~Comment~
        +create(db, task_id, author_id, body) Comment
    }

    %% ── Relationships ─────────────────────────────────────────────
    User "1" --> "0..*" Project : owns
    User "1" --> "0..*" Task : assigned to
    User "1" --> "0..*" Comment : authors
    Project "1" --> "0..*" Task : contains
    Task "1" --> "0..*" Comment : has
    Task --> TaskStatus : uses
    Task --> TaskPriority : uses

    TaskService ..> Task : mutates
    TaskService ..> TaskStatus : validates transitions
    AuthService ..> User : authenticates

    UserRepository ..> User : persists
    ProjectRepository ..> Project : persists
    TaskRepository ..> Task : persists
    CommentRepository ..> Comment : persists
```

> **Soft-delete note:** `ProjectRepository.delete()` and `TaskRepository.delete()` set `deleted_at` to the current UTC timestamp — they do **not** issue a SQL `DELETE`. `UserRepository` names this `soft_delete()` to make the intent explicit. All `get_*` queries filter `WHERE deleted_at IS NULL`. See ADR 0004.

---

## 5. Entity Relationship Diagram

Shows the PostgreSQL schema — tables, columns, data types, and foreign key relationships.

```mermaid
erDiagram
    users {
        serial     id           PK
        varchar255 email        UK "indexed"
        varchar255 full_name
        varchar255 hashed_password
        timestamptz created_at  "server default now()"
        timestamptz deleted_at  "nullable, indexed — soft delete"
    }

    projects {
        serial      id           PK
        varchar255  name
        text        description  "nullable"
        int         owner_id     FK "→ users.id ON DELETE CASCADE, indexed"
        timestamptz created_at   "server default now()"
        timestamptz deleted_at   "nullable, indexed — soft delete"
    }

    tasks {
        serial      id           PK
        int         project_id   FK "→ projects.id ON DELETE CASCADE, indexed"
        varchar255  title
        text        description  "nullable"
        task_status status       "ENUM: TODO IN_PROGRESS IN_REVIEW DONE CANCELLED"
        task_priority priority   "ENUM: LOW MEDIUM HIGH URGENT"
        int         assignee_id  FK "→ users.id ON DELETE SET NULL, indexed, nullable"
        date        due_date     "nullable"
        timestamptz created_at   "server default now()"
        timestamptz updated_at   "server default now(), onupdate now()"
        timestamptz deleted_at   "nullable, indexed — soft delete"
    }

    comments {
        serial      id         PK
        int         task_id    FK "→ tasks.id ON DELETE CASCADE, indexed"
        int         author_id  FK "→ users.id ON DELETE CASCADE, indexed"
        text        body
        timestamptz created_at "server default now()"
        timestamptz deleted_at "nullable, indexed — soft delete"
    }

    users    ||--o{ projects : "owner_id"
    users    ||--o{ tasks    : "assignee_id"
    users    ||--o{ comments : "author_id"
    projects ||--o{ tasks    : "project_id"
    tasks    ||--o{ comments : "task_id"
```

---

## Diagram Summary

| Diagram | Type | What it shows |
|---------|------|---------------|
| Architecture | Flowchart | Three tiers, middleware execution order, CI (ci.yml) and CD (publish.yml) pipelines, observability stack |
| Use Case | Graph | What each actor (Guest / Auth User / System) can do, including GDPR deletion and audit logging |
| Sequence 3a | Sequence | Valid task status transition — happy path |
| Sequence 3b | Sequence | Invalid status transition — 422 error path |
| Sequence 3c | Sequence | Login flow and JWT issuance |
| Sequence 3d | Sequence | Logout and JTI token revocation |
| Sequence 3e | Sequence | GDPR account deletion (soft delete) |
| Sequence 3f | Sequence | Rate-limited login — 429 Too Many Requests (sliding-window, ADR 0007) |
| Sequence 3g | Sequence | Observability instrumentation — structured log + OTel trace + Prometheus metric per request (ADR 0006) |
| Class | Class | Domain models, service layer, repository layer; soft-delete note on delete() methods |
| ER | Entity-Relationship | PostgreSQL schema with columns, foreign keys, and soft-delete fields on all four tables |
