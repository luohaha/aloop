"""Data types for the enhanced plan-execute agent."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StepStatus(Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReplanTrigger(Enum):
    """Reason for replanning."""

    STEP_FAILURE = "step_failure"
    UNEXPECTED_RESULT = "unexpected_result"
    CONSTRAINT_VIOLATION = "constraint_violation"


@dataclass
class ExplorationResult:
    """Results from the exploration phase."""

    discovered_files: List[str] = field(default_factory=list)
    code_patterns: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    context_summary: str = ""


@dataclass
class PlanStep:
    """A single step in the execution plan."""

    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Structured plan with dependency information."""

    task: str
    steps: List[PlanStep] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)
    exploration_context: Optional[ExplorationResult] = None
    version: int = 1

    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute (all dependencies completed).

        Returns:
            List of steps whose dependencies are all completed.
        """
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        return [
            s
            for s in self.steps
            if s.status == StepStatus.PENDING and all(d in completed_ids for d in s.depends_on)
        ]

    def get_parallel_batch(self) -> List[PlanStep]:
        """Get a batch of independent steps that can run in parallel.

        Returns:
            List of steps that can be executed concurrently.
        """
        ready = self.get_ready_steps()
        if not ready:
            return []

        first_id = ready[0].id
        for group in self.parallel_groups:
            if first_id in group:
                return [s for s in ready if s.id in group]
        return [ready[0]]

    def all_completed(self) -> bool:
        """Check if all steps are completed.

        Returns:
            True if all steps have COMPLETED status.
        """
        return all(s.status == StepStatus.COMPLETED for s in self.steps)

    def has_failed_steps(self) -> bool:
        """Check if any steps have failed.

        Returns:
            True if any step has FAILED status.
        """
        return any(s.status == StepStatus.FAILED for s in self.steps)


@dataclass
class ReplanRequest:
    """Request to replan due to execution issues."""

    trigger: ReplanTrigger
    failed_step: Optional[PlanStep] = None
    reason: str = ""
