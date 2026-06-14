Auto-fix all Python formatting and import-order issues in the backend tier, then run linting to surface any remaining violations that require manual attention.

## Steps

1. From the `backend/` directory, apply auto-fixers in this order (order matters — black must run before isort):
   - `black .` — reformat all Python files to project style
   - `isort .` — reorder imports to black-compatible order
   - `ruff check --fix .` — fix all auto-fixable lint violations

2. After fixing, run the read-only checks to find anything that remains:
   - `black --check .`
   - `isort --check .`
   - `ruff check .`

3. Report what was changed:
   - List every file that was modified by the auto-fixers (from their stdout)
   - For any remaining violations (things auto-fix couldn't handle), show them with an explanation of the manual change required

4. Print the final status:
   - `✅ All Python issues fixed` if the post-fix checks all pass
   - `⚠️ Auto-fix applied — N violations still require manual changes` if any checks still fail

5. Remind the user to re-stage modified files before committing:
   ```
   git add backend/
   git status
   ```

## Context

- Working directory for all commands: `backend/`
- black and ruff auto-fix are safe to apply — they only change formatting, not logic
- ruff `--fix` only applies fixes marked as "safe" in the ruff docs; it will NOT silently remove code
- If the user only wants to fix a specific file, they can pass it: `/fix-python app/services/task_service.py`
  In that case, scope all commands to `$ARGUMENTS` instead of `.`
