"""Unit tests for task_service — no database required."""
import pytest
from fastapi import HTTPException

from app.models.task import Task, TaskStatus, TaskPriority
from app.schemas.task import TaskUpdate
from app.services.task_service import validate_status_transition, apply_task_update


def make_task(**kwargs) -> Task:
    defaults = dict(
        id=1,
        project_id=1,
        title="Test task",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        assignee_id=None,
        due_date=None,
    )
    defaults.update(kwargs)
    task = Task()
    for k, v in defaults.items():
        setattr(task, k, v)
    return task


class TestValidateStatusTransition:
    def test_todo_to_in_progress_is_allowed(self):
        validate_status_transition(TaskStatus.TODO, TaskStatus.IN_PROGRESS)

    def test_todo_to_cancelled_is_allowed(self):
        validate_status_transition(TaskStatus.TODO, TaskStatus.CANCELLED)

    def test_todo_to_done_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(TaskStatus.TODO, TaskStatus.DONE)
        assert exc.value.status_code == 422

    def test_in_progress_to_in_review_is_allowed(self):
        validate_status_transition(TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW)

    def test_done_is_terminal_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(TaskStatus.DONE, TaskStatus.TODO)
        assert exc.value.status_code == 422

    def test_cancelled_is_terminal_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_status_transition(TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS)
        assert exc.value.status_code == 422

    def test_same_status_is_allowed(self):
        validate_status_transition(TaskStatus.IN_PROGRESS, TaskStatus.IN_PROGRESS)


class TestApplyTaskUpdate:
    def test_updates_title(self):
        task = make_task(title="Old title")
        result = apply_task_update(task, TaskUpdate(title="New title"))
        assert result.title == "New title"

    def test_valid_status_transition_applied(self):
        task = make_task(status=TaskStatus.TODO)
        result = apply_task_update(task, TaskUpdate(status=TaskStatus.IN_PROGRESS))
        assert result.status == TaskStatus.IN_PROGRESS

    def test_invalid_status_transition_raises(self):
        task = make_task(status=TaskStatus.TODO)
        with pytest.raises(HTTPException):
            apply_task_update(task, TaskUpdate(status=TaskStatus.DONE))

    def test_none_fields_not_applied(self):
        task = make_task(title="Original", priority=TaskPriority.HIGH)
        result = apply_task_update(task, TaskUpdate())
        assert result.title == "Original"
        assert result.priority == TaskPriority.HIGH
