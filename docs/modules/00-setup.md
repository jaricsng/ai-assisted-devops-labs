# Module 0 — Environment Setup & Claude Code Orientation

## Learning Objectives

- Have a working development environment before writing any code
- Understand what Claude Code is and how to interact with it
- Run the starter repo successfully

## Prerequisites Checklist

Run each command to verify your setup:

```bash
git --version          # ≥ 2.40
docker --version       # ≥ 25
node --version         # ≥ 20
python3 --version      # ≥ 3.12
claude --version       # Claude Code CLI
```

Install Claude Code if needed:
```bash
npm install -g @anthropic-ai/claude-code
```

## Getting Started

```bash
# Clone the lab repo (or fork it first on GitHub)
git clone <repo-url> task-manager
cd task-manager

# Copy environment file — never commit .env
cp .env.example .env

# Generate a real secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as SECRET_KEY in .env

# Start all services
docker compose up
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) — you should see the FastAPI Swagger UI.

## Claude Code Orientation Tasks

Open Claude Code in the project directory:
```bash
claude
```

Try these prompts to get familiar with Claude Code:

1. **Explore:** `"Explain the docker-compose.yml file to me"`
2. **Understand the codebase:** `"Walk me through how a PATCH /tasks/{id} request flows from the router to the database"`
3. **Generate CLAUDE.md:** Run `/init` and review what Claude Code writes
4. **Settings:** Run `/config` to see your current settings

## Checkpoint

You're done with Module 0 when:
- [ ] `docker compose up` starts all three services without errors
- [ ] `curl http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] You can open `http://localhost:5173` in a browser
- [ ] You've run at least one Claude Code prompt and got a useful response
