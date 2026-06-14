Auto-fix all ESLint violations that have a safe automatic fix in the frontend tier, then run the full suite of checks to surface what remains.

## Steps

1. From the `frontend/` directory, apply ESLint's auto-fixer:
   ```
   npx eslint . --fix
   ```
   Capture which files were modified.

2. Run the read-only checks to find anything that remains:
   - `npm run typecheck` — TypeScript errors (auto-fix cannot resolve type errors)
   - `npm run lint` — ESLint violations that require manual changes

3. Report what changed:
   - List every file modified by `eslint --fix`
   - For remaining TypeScript errors, show the error with file/line and a suggested fix
   - For remaining ESLint violations (no auto-fix available), explain the manual change needed

4. For each remaining **TypeScript error**, apply the correct fix:
   - `Type X is not assignable to type Y` → the variable type annotation or the returned value needs updating
   - `Property X does not exist on type Y` → the interface is missing a field, or a wrong property name was used
   - `Argument of type X is not assignable to parameter of type Y` → function call is passing wrong type
   - `Object is possibly null/undefined` → add a null check or use optional chaining
   - If the fix is clear and low-risk, apply it. If it requires understanding business logic, describe what change is needed and why.

5. Re-run `npm run typecheck && npm run lint` after all fixes are applied.

6. Print the final status:
   - `✅ All frontend issues fixed`
   - `⚠️ ESLint auto-fix applied — N issues require manual changes` with a numbered list

## Context

- Working directory for all shell commands: `frontend/`
- Only ESLint has an auto-fixer; TypeScript type errors always require manual code changes
- If the user passes a file path as an argument (`/fix-frontend src/components/TaskCard.tsx`), scope the ESLint fix to `$ARGUMENTS`
- Do not add `// eslint-disable` comments as a fix — fix the underlying issue instead
- Do not change a type to `any` to suppress a TypeScript error — that defeats the purpose of strict mode
