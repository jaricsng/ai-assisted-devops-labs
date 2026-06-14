Run all Python coding-standard checks for the backend tier without modifying any files. Report every violation grouped by tool, explain what each rule enforces, and tell the user exactly which command to run to fix it.

## Steps

1. Run each check tool from the `backend/` directory. Capture stdout, stderr, and exit code for each:
   - `black --check --diff .` — formatting (shows what would change)
   - `isort --check --diff .` — import ordering
   - `ruff check .` — linting (style, complexity, common bugs)
   - `python -m pytest --co -q 2>&1 | tail -5` — verify tests are discoverable (not a full run)

2. For each tool that reported violations:
   - Show the raw output (file paths, line numbers, violation descriptions)
   - Explain in one sentence what the rule enforces and why it matters in this project
   - Show the exact command to auto-fix it (or the manual change needed if auto-fix isn't possible)

3. Produce a final summary table:

   | Tool | Status | Violations |
   |------|--------|------------|
   | black | ✅ / ❌ | 0 / N files |
   | isort | ✅ / ❌ | 0 / N files |
   | ruff | ✅ / ❌ | 0 / N errors |

4. If all tools pass, print: `✅ Python standards: all checks passed`
   If any tool fails, print: `❌ Python standards: N tool(s) failed — run /fix-python to auto-fix formatting issues`

## Context

- Working directory for all commands: `backend/`
- Tools are installed via `pip install -e ".[dev]"`
- Project uses black (line-length 88, Python 3.12), isort (black profile), ruff
- Do NOT modify any files — this is a read-only check
