"""Seed the database with a demo account and sample data.

Creates (idempotently — safe to run multiple times):
  - One demo user
  - Two sample projects with tasks spread across every status column

Usage (from inside the API container):
    docker compose exec api python seed.py

Usage (locally, with DATABASE_URL pointing at the running DB):
    DATABASE_URL=postgresql+asyncpg://taskuser:taskpass@localhost:5432/taskmanager \
    SECRET_KEY=any-value python seed.py
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models.comment import Comment  # noqa: F401 — needed for metadata
from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.services.auth_service import hash_password

# ── Demo credentials ──────────────────────────────────────────────────────────

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo1234!"
DEMO_NAME = "Demo User"

# ── Sample data ───────────────────────────────────────────────────────────────

PROJECTS = [
    {
        "name": "Website Redesign",
        "description": "Modernise the company website with new branding and improved UX.",
        "tasks": [
            {
                "title": "Define new brand guidelines",
                "description": "Colours, typography, logo usage rules. Sign-off from marketing required.",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
            },
            {
                "title": "Design homepage wireframes",
                "description": "Cover desktop, tablet, and mobile breakpoints.",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.HIGH,
            },
            {
                "title": "Implement responsive navigation",
                "description": "Hamburger menu on mobile; sticky header on scroll.",
                "status": TaskStatus.IN_REVIEW,
                "priority": TaskPriority.HIGH,
            },
            {
                "title": "Write copy for About page",
                "description": "500-word company story. Draft ready; waiting on CEO approval.",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.MEDIUM,
            },
            {
                "title": "Set up analytics tracking",
                "description": "Google Analytics 4 + custom event tracking for CTA clicks.",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
            },
            {
                "title": "Conduct user testing sessions",
                "description": "Recruit 5 participants. Run moderated sessions on staging.",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.LOW,
            },
        ],
    },
    {
        "name": "Payment & Notifications Integration",
        "description": "Connect Stripe for payments and SendGrid for transactional emails.",
        "tasks": [
            {
                "title": "Research payment gateway options",
                "description": "Evaluated Stripe, Paddle, and Braintree. Decision: Stripe.",
                "status": TaskStatus.DONE,
                "priority": TaskPriority.URGENT,
            },
            {
                "title": "Implement Stripe checkout flow",
                "description": "One-time payments and subscription plans. Use Stripe Elements.",
                "status": TaskStatus.IN_PROGRESS,
                "priority": TaskPriority.URGENT,
            },
            {
                "title": "Add email notification service",
                "description": "Order confirmation, password reset, and weekly digest templates.",
                "status": TaskStatus.IN_REVIEW,
                "priority": TaskPriority.HIGH,
            },
            {
                "title": "Write integration tests",
                "description": "Cover happy path, card decline, and webhook replay scenarios.",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.HIGH,
            },
            {
                "title": "Document API endpoints",
                "description": "Update OpenAPI spec with new /payments and /webhooks routes.",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.MEDIUM,
            },
            {
                "title": "Load test payment endpoints",
                "description": "Simulate 200 concurrent checkouts. Target: p95 < 800 ms.",
                "status": TaskStatus.TODO,
                "priority": TaskPriority.LOW,
            },
        ],
    },
]


# ── Seed logic ────────────────────────────────────────────────────────────────

async def seed() -> None:
    # Ensure tables exist (safe if they already do)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check whether demo user already exists
        result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"Demo user '{DEMO_EMAIL}' already exists — skipping seed.")
            print("To re-seed, reset the database first: docker compose down -v && docker compose up -d")
            return

        # Create demo user
        user = User(
            email=DEMO_EMAIL,
            full_name=DEMO_NAME,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        session.add(user)
        await session.flush()  # populate user.id before FK references

        # Create projects and tasks
        for project_data in PROJECTS:
            project = Project(
                name=project_data["name"],
                description=project_data["description"],
                owner_id=user.id,
            )
            session.add(project)
            await session.flush()  # populate project.id

            for task_data in project_data["tasks"]:
                task = Task(
                    project_id=project.id,
                    title=task_data["title"],
                    description=task_data.get("description"),
                    status=task_data["status"],
                    priority=task_data["priority"],
                )
                session.add(task)

        await session.commit()

    print("✅  Seed complete.")
    print()
    print("  Demo account")
    print(f"  Email    : {DEMO_EMAIL}")
    print(f"  Password : {DEMO_PASSWORD}")
    print()
    print("  Projects created : 2")
    print("  Tasks created    : 12  (spread across TODO / IN_PROGRESS / IN_REVIEW / DONE)")
    print()
    print("  Open the app at: http://localhost:5173")


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as exc:
        print(f"❌  Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
