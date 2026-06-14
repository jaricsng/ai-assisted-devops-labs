# Module 1 — Architecture Design with Claude Code

## Learning Objectives

- Use Claude Code as a design partner, not just a code generator
- Understand the three-tier architecture and why it's used here
- Write your first Architecture Decision Record (ADR)

## Background

Before writing a single line of implementation code, professional teams align on *why* they're making architectural choices. The ADR format captures the context, decision, and consequences — so future contributors (or your future self) understand the reasoning.

## Activities

### 1. Explore the existing architecture

Read `docs/adr/0001-architecture.md` and `docs/adr/0002-api-first-design.md`.

Then ask Claude Code:
> "Based on the existing ADRs and the codebase, what are the three tiers in this project, and what responsibility does each tier have?"

### 2. Challenge the design

Use Claude Code to explore trade-offs:
> "What would be the trade-offs of moving the status transition validation from the Python service layer into a PostgreSQL trigger instead?"

Write down Claude Code's answer. Do you agree? If not, push back:
> "I think keeping logic in PostgreSQL makes testing harder. Can you make the case for keeping it in Python?"

### 3. Draw the system context diagram

Ask Claude Code:
> "Generate a Mermaid diagram showing the three tiers of this application and how they communicate. Include the GitHub Actions CI pipeline."

Add the output to `docs/adr/0001-architecture.md` under a **Diagram** section.

### 4. Write your own ADR

Pick a technology decision you'd make for this project (e.g., "Why Tanstack Query instead of plain fetch?", "Why asyncpg instead of psycopg2?"). Write a new ADR at `docs/adr/0003-<your-topic>.md` using the template from the existing ADRs.

Ask Claude Code to review it:
> "Review my ADR at docs/adr/0003-xyz.md. Is the rationale convincing? What have I missed?"

## Checkpoint

- [ ] You can explain the three tiers and their responsibilities without looking at the code
- [ ] The Mermaid diagram is in the architecture ADR
- [ ] You've written a new ADR (`docs/adr/0003-*.md`) and committed it

## Key Takeaway

Claude Code is a design partner. Use it to stress-test your thinking, not just to generate code. A good prompt starts with *why*, not *how*.
