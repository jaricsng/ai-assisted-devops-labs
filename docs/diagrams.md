# UML Diagrams — Task Manager

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively in GitHub, VS Code (with the Mermaid Preview extension), and Claude Code.

---

## 1. Architecture Diagram

Shows how the three tiers, Docker Compose, and the CI/CD pipeline fit together.

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
        Routers["Routers\n/auth · /projects · /projects/{id}/tasks"]
        Services["Services\nTaskService · AuthService"]
        Repos["Repositories\nUserRepo · ProjectRepo · TaskRepo · CommentRepo"]
        Routers --> Services --> Repos
    end

    subgraph DB["Data Tier — PostgreSQL 16 (port 5432)"]
        Tables["Tables\nusers · projects · tasks · comments"]
    end

    subgraph CI["CI/CD — GitHub Actions"]
        direction LR
        Backend["backend job\nblack · isort · ruff · pytest ≥70%"]
        Frontend["frontend job\ntsc · eslint · vitest ≥70%"]
        Docker["docker-build job\ndocker compose build"]
        E2E["e2e job\nPlaywright (PRs to main only)"]
    end

    BR -->|"HTTP · port 5173"| FE
    APIClient -->|"REST/JSON · port 8000"| BE
    Repos -->|"SQL · asyncpg · port 5432"| DB
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

    UC10 -.->|"«includes»"| UC17
    UC4 & UC5 & UC6 & UC8 & UC9 & UC10 & UC15 -.->|"«includes»"| UC18
    UC1 & UC2 -.->|"«includes»"| UC19

    System --> UC17
    System --> UC18
    System --> UC19
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
    }

    %% ── Repository Layer (SQL only, no business logic) ────────────
    class UserRepository {
        <<repository>>
        +get_by_email(db, email str) User
        +get_by_id(db, user_id int) User
        +create(db, email, full_name, hashed_password) User
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
    }

    projects {
        serial      id           PK
        varchar255  name
        text        description  "nullable"
        int         owner_id     FK "→ users.id ON DELETE CASCADE, indexed"
        timestamptz created_at   "server default now()"
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
    }

    comments {
        serial      id         PK
        int         task_id    FK "→ tasks.id ON DELETE CASCADE, indexed"
        int         author_id  FK "→ users.id ON DELETE CASCADE, indexed"
        text        body
        timestamptz created_at "server default now()"
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
| Architecture | Flowchart | Three tiers, Docker Compose ports, CI/CD jobs |
| Use Case | Graph | What each actor (Guest / Auth User) can do |
| Sequence 3a | Sequence | Valid task status transition — happy path |
| Sequence 3b | Sequence | Invalid status transition — 422 error path |
| Sequence 3c | Sequence | Login flow and JWT issuance |
| Class | Class | Domain models, service layer, repository layer |
| ER | Entity-Relationship | PostgreSQL schema with columns and foreign keys |
