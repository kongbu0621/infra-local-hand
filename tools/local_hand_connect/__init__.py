"""Controller-side adapter for the bounded Local Hand protocol."""

from .controller import (
    GitMailboxControllerAdapter,
    LocalHandControllerAdapter,
    build_task,
    call_task,
    initialize_controller_mailbox,
    new_task_id,
    submit_task,
    validate_expected_provenance,
    wait_for_result,
)

__all__ = [
    "GitMailboxControllerAdapter",
    "LocalHandControllerAdapter",
    "build_task",
    "call_task",
    "initialize_controller_mailbox",
    "new_task_id",
    "submit_task",
    "validate_expected_provenance",
    "wait_for_result",
]
