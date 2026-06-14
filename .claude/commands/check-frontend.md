Run all frontend coding-standard checks (TypeScript type checking + ESLint) without modifying any files. Report every violation with an explanation of what rule it breaks and how to fix it.

## Steps

1. From the `frontend/` directory, run each check and capture all output:
   - `npm run typecheck` (runs `tsc --noEmit`) — TypeScript type errors
   - `npm run lint` (runs `eslint . --max-warnings 0`) — ESLint rule violations

2. For TypeScript errors:
   - Show each error with its file path, line number, and error message
   - Group errors by kind: type mismatch, missing property, implicit `any`, unknown module, etc.
   - For each group, explain what invariant TypeScript is enforcing and why it matters

3. For ESLint violations:
   - Show each error/warning with rule name, file, and line
   - Explain the rule in one sentence (e.g., `@typescript-eslint/no-explicit-any` — prevents bypassing the type system with `any`)
   - Mark which violations can be auto-fixed with `eslint --fix`

4. Check for these project-specific conventions that tools may not catch — read relevant source files and flag any violations:
   - All API calls go through `src/api/` (not inline `fetch`/`axios` in components)
   - All component prop types are defined as TypeScript interfaces (not inline types or `any`)
   - All data-fetching components handle loading and error states
   - No hardcoded API base URLs — use `import.meta.env.VITE_API_URL`

5. Produce a summary table:

   | Check | Status | Issues |
   |-------|--------|--------|
   | TypeScript (tsc) | ✅ / ❌ | 0 / N errors |
   | ESLint | ✅ / ❌ | 0 / N errors, N warnings |
   | Conventions | ✅ / ❌ | 0 / N manual checks failed |

6. Final status line:
   - `✅ Frontend standards: all checks passed`
   - `❌ Frontend standards: N check(s) failed`

## Context

- Working directory for all shell commands: `frontend/`
- TypeScript is configured in `frontend/tsconfig.json` with strict mode
- ESLint config is in `frontend/eslint.config.*` or `frontend/.eslintrc.*`
- The `--max-warnings 0` flag in the lint script means ANY warning is a build failure
- Do NOT modify any files — this is a read-only check
