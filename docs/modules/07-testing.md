# Module 7 — Testing (Unit, Integration, Component)

## Learning Objectives

- Write tests that verify behaviour, not just coverage numbers
- Understand the four levels of the test pyramid and when to use each
- Use Claude Code to find gaps in your test suite

## The Test Pyramid

```
           /\
          /  \
         / E2E \  ← Module 07b (Playwright — real browser, full stack)
        /--------\
       /Integration\ ← API endpoint tests (httpx + test DB)
      /-------------\
     / Component     \ ← React Testing Library (DOM, no API calls)
    /-----------------\
   /  Unit Tests       \ ← business logic, pure functions, no I/O
  /---------------------\
```

| Level | Speed | Confidence | When to write |
|-------|-------|-----------|---------------|
| Unit | ~1 ms/test | High for logic | Always — for every business rule |
| Integration | ~100 ms/test | High for plumbing | Key API flows and DB interactions |
| Component | ~10 ms/test | High for UI logic | Every interactive component |
| E2E | ~5 s/test | Highest (real browser) | Critical user journeys only |

**Rule:** Most tests should be unit tests. E2E tests are expensive — write them only for the flows that must never break (login, create task, status transition).

---

## Backend — Unit Tests

Unit tests run without a database, a network, or Docker. They test pure Python logic.

### Run existing tests

```bash
cd backend
pip install -e ".[dev]"
pytest tests/test_task_service.py tests/test_auth_service.py -v
```

Look at `tests/test_task_service.py`. Notice:

- `make_task()` constructs a `Task` object directly — no DB, no `async`, no fixtures
- Each test case covers one specific scenario
- The test names read like specifications: `test_todo_to_done_raises`

### Write a new unit test

The `apply_task_update` function has a case not yet covered: what happens when `description` is explicitly set to an empty string?

Ask Claude Code:
> "Write a pytest unit test for apply_task_update that verifies: when description is set to an empty string, the task's description is updated to '' (not None, not ignored)."

Add it to `tests/test_task_service.py`.

### What makes a good unit test?

Ask Claude Code:
> "Look at tests/test_task_service.py. Which tests are the weakest — testing implementation details instead of behaviour? How would you rewrite them?"

---

## Backend — Integration Tests

Integration tests spin up the FastAPI app with a real (in-memory SQLite) database. They test that all the layers work together correctly over HTTP.

### Write an integration test

Ask Claude Code:
> "Write an integration test in tests/test_tasks_api.py using httpx.AsyncClient and the conftest fixtures that:
>
> 1. Registers a user via POST /auth/register
> 2. Logs in via POST /auth/login to get a token
> 3. Creates a project via POST /projects
> 4. Creates a task in that project
> 5. Attempts to PATCH the task status directly from TODO to DONE
> 6. Asserts the response is 422 with an error message mentioning the invalid transition"

Look at `tests/conftest.py` to understand how the test client and database are set up before writing the test yourself.

### Check coverage

```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html   # macOS
# xdg-open htmlcov/index.html  # Linux
```

Find a file below 70%. Ask Claude Code:
> "Which lines in app/routers/projects.py are not covered by tests? Write integration tests to cover the DELETE /projects/{id} endpoint."

---

## Frontend — Component Tests

Component tests render a React component into a virtual DOM and assert on what the user would see and interact with. There is no real browser and no API calls.

### Run existing tests

```bash
cd frontend
npm test
```

Look at `src/components/TaskCard.test.tsx`:

- Task data is created as a plain TypeScript object — no API call
- `vi.fn()` creates a mock function so we can assert it was called with the right args
- Assertions use `@testing-library/jest-dom` matchers like `toBeInTheDocument()`

### Write a new component test

Ask Claude Code:
> "Write a Vitest component test for KanbanBoard that verifies:
>
> - When two tasks have status TODO and one has status IN_PROGRESS, the TODO column shows 2 tasks and the IN_PROGRESS column shows 1 task
> - Clicking the '→ In Progress' button on a TODO task calls onStatusChange with the correct taskId and 'IN_PROGRESS'"

### Testing with mock API (MSW)

`msw` (Mock Service Worker) intercepts network requests in tests so you can test components that call the API. Ask Claude Code:
> "Show me how to write a Vitest test for ProjectsPage.tsx using msw to mock GET /projects. The test should verify that a project named 'My Project' appears in the list after the mock returns it."

---

## Checkpoint

- [ ] `pytest --cov-fail-under=70` passes
- [ ] `npm test` passes with coverage ≥ 70%
- [ ] You've written at least one unit test, one integration test, and one component test
- [ ] You ran `/code-review` on your test files and addressed at least one finding
- [ ] `/check-python` shows no lint violations in the test files
- [ ] `/check-standards` produces a full green report across both tiers
- [ ] Continue to **Module 07b** for E2E testing with Playwright

---

## Best Practice: AAA Pattern

Every test — unit, integration, or component — should follow **Arrange → Act → Assert**:

```python
def test_valid_transition():
    # Arrange
    task = make_task(status=TaskStatus.TODO)
    update = TaskUpdate(status=TaskStatus.IN_PROGRESS)

    # Act
    result = apply_task_update(task, update)

    # Assert
    assert result.status == TaskStatus.IN_PROGRESS
```

```tsx
it("calls onStatusChange when transition button is clicked", () => {
  // Arrange
  const onStatusChange = vi.fn();
  render(<TaskCard task={todoTask} onStatusChange={onStatusChange} />);

  // Act
  fireEvent.click(screen.getByText("→ In Progress"));

  // Assert
  expect(onStatusChange).toHaveBeenCalledWith(1, "IN_PROGRESS");
});
```
