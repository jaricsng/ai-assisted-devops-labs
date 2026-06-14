# Module 6 — Frontend Tier (React + TypeScript)

## Learning Objectives

- Understand how the React app is structured and connects to the FastAPI backend
- Use auto-generated TypeScript types from the OpenAPI spec
- Extend the UI with a new feature using Claude Code as a pair programmer
- See how Tanstack Query eliminates boilerplate for data fetching and caching

## Background

The frontend is a React 18 SPA built with Vite. Key decisions:

| Decision | Why |
|----------|-----|
| TypeScript strict mode | Catch type errors at compile time, not runtime |
| Tanstack Query | Handles loading states, caching, and refetching without manual `useState` |
| Types from OpenAPI spec | `frontend/src/api/types.ts` stays in sync with the backend contract |
| All API calls through `src/api/` | Components never call axios directly — easy to mock in tests |

## Activities

### 1. Run the frontend and explore the code

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Register a user, create a project, add tasks, and move them through the Kanban board.

Then read:
- `src/api/client.ts` — the axios instance with the auth token interceptor
- `src/components/KanbanBoard.tsx` — how tasks are grouped into columns
- `src/pages/ProjectDetailPage.tsx` — how Tanstack Query's `useQuery` and `useMutation` work together

Ask Claude Code:
> "In ProjectDetailPage.tsx, why does useMutation call qc.invalidateQueries on success instead of updating the cache directly? What are the trade-offs?"

### 2. Regenerate TypeScript types from the OpenAPI spec

Whenever the API contract changes, regenerate the types:

```bash
npx openapi-typescript ../docs/api/openapi.yaml -o src/api/types.ts
```

If you added the filter query params to the spec in Module 2, the generated types will now include them. Review the diff.

Ask Claude Code:
> "How would I add a typed wrapper function in src/api/tasks.ts for the new filter query params? Show me a tasksApi.listFiltered function."

### 3. Add a task detail panel (new feature)

Currently, clicking a task does nothing. Add a side panel that shows the task's comments.

**Step 1 — Plan with Claude Code:**
> "I want to add a side panel that appears when a user clicks a task card. It should show the task title, description, and a list of comments with an input to add a new comment. What React patterns would you recommend — local state, a URL param, or a context?"

**Step 2 — Implement:**

Ask Claude Code to generate the component:
> "Create a TaskDetailPanel component in src/components/TaskDetailPanel.tsx that:
> - Accepts a taskId and projectId as props
> - Fetches comments using useQuery and the tasksApi.listComments function
> - Shows a form to add a new comment using useMutation and tasksApi.addComment
> - Has a close button that calls an onClose prop
> Use TypeScript with proper types from src/api/types.ts."

**Step 3 — Wire it into KanbanBoard:**

Update `TaskCard.tsx` to call an `onSelect` prop when clicked, and update `KanbanBoard.tsx` to track the selected task in local state and render the panel.

### 4. Handle loading and error states

Open `ProjectDetailPage.tsx`. The `isLoading` check shows a plain string. Improve it:

Ask Claude Code:
> "Add proper loading skeleton and error boundary handling to ProjectDetailPage.tsx. When loading, show placeholder cards in each Kanban column. When there's an API error, show a retry button."

### 5. Type-safety check

```bash
npm run typecheck
```

Fix all TypeScript errors before moving on. Ask Claude Code for help with any errors:
> "TypeScript says: [paste error]. How do I fix this without using `any`?"

## Best Practices in This Module

- **Never use `any`** — if you're tempted, there's a typed alternative
- **Colocate query keys** — define `["tasks", projectId]` in one place so invalidation is consistent
- **Optimistic updates** — for fast UI, update the cache before the API call confirms (ask Claude Code to show you how for the status change)
- **Environment variable for API URL** — `import.meta.env.VITE_API_URL` never hardcoded

## Checkpoint

- [ ] The app runs end-to-end: login → project → kanban board with working status transitions
- [ ] `npm run typecheck` exits clean (zero errors)
- [ ] `npm run lint` exits clean
- [ ] You've implemented the task detail panel (or a comparable new feature)
- [ ] At least one component has a loading state and an error state
- [ ] `npm test` still passes
- [ ] Commit: `feat(frontend): add task detail panel with comments`
