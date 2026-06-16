import structlog
from fastapi import HTTPException, status

from app.business_metrics import task_status_transitions_total
from app.models.task import Task, TaskStatus, VALID_TRANSITIONS
from app.schemas.task import TaskUpdate

logger = structlog.get_logger(__name__)


def validate_status_transition(current: TaskStatus, next_status: TaskStatus) -> None:
    """Raise 422 if the requested status transition is not permitted.

    Terminal states (DONE, CANCELLED) cannot be left. All other transitions
    must follow the VALID_TRANSITIONS map defined on the model.
    """
    if current == next_status:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if next_status not in allowed:
        logger.warning(
            "invalid_status_transition",
            current_status=current.value,
            requested_status=next_status.value,
            allowed=[s.value for s in allowed],
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Cannot transition task from '{current}' to '{next_status}'. "
                f"Allowed transitions: {[s.value for s in allowed] or 'none (terminal state)'}."
            ),
        )


def apply_task_update(task: Task, update: TaskUpdate) -> Task:
    """Apply a partial update payload to a task, enforcing status transition rules.

    Returns the mutated task object (caller is responsible for persisting it).
    Logs a structured event when the status changes so the transition is auditable.
    """
    if update.status is not None:
        old_status = task.status
        validate_status_transition(task.status, update.status)
        task.status = update.status
        logger.info(
            "task_status_changed",
            task_id=task.id,
            old_status=old_status.value,
            new_status=task.status.value,
        )
        task_status_transitions_total.labels(
            from_status=old_status.value,
            to_status=task.status.value,
        ).inc()

    if update.title is not None:
        task.title = update.title
    if update.description is not None:
        task.description = update.description
    if update.priority is not None:
        task.priority = update.priority
    if update.assignee_id is not None:
        task.assignee_id = update.assignee_id
    if update.due_date is not None:
        task.due_date = update.due_date

    return task
