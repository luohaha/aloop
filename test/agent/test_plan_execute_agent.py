"""Tests for the enhanced Plan-Execute agent."""

from agent.plan_types import (
    ExecutionPlan,
    ExplorationResult,
    PlanStep,
    ReplanRequest,
    ReplanTrigger,
    StepStatus,
)


class TestPlanTypes:
    """Tests for plan data types."""

    def test_step_status_enum(self):
        """Test StepStatus enum values."""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_plan_step_defaults(self):
        """Test PlanStep default values."""
        step = PlanStep(id="step_1", description="Test step")
        assert step.status == StepStatus.PENDING
        assert step.depends_on == []
        assert step.result is None
        assert step.error is None

    def test_execution_plan_get_ready_steps(self):
        """Test getting ready steps respects dependencies."""
        steps = [
            PlanStep(id="step_1", description="First step"),
            PlanStep(id="step_2", description="Second step", depends_on=["step_1"]),
            PlanStep(id="step_3", description="Third step", depends_on=["step_1"]),
        ]
        plan = ExecutionPlan(task="test", steps=steps)

        # Only step_1 should be ready initially
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_1"

        # After completing step_1, step_2 and step_3 should be ready
        steps[0].status = StepStatus.COMPLETED
        ready = plan.get_ready_steps()
        assert len(ready) == 2
        assert {s.id for s in ready} == {"step_2", "step_3"}

    def test_execution_plan_get_parallel_batch(self):
        """Test getting parallel batch of steps."""
        steps = [
            PlanStep(id="step_1", description="First"),
            PlanStep(id="step_2", description="Second"),
            PlanStep(id="step_3", description="Third", depends_on=["step_1", "step_2"]),
        ]
        plan = ExecutionPlan(
            task="test",
            steps=steps,
            parallel_groups=[["step_1", "step_2"]],
        )

        # Should return both step_1 and step_2 as parallel batch
        batch = plan.get_parallel_batch()
        assert len(batch) == 2
        assert {s.id for s in batch} == {"step_1", "step_2"}

    def test_execution_plan_all_completed(self):
        """Test checking if all steps are completed."""
        steps = [
            PlanStep(id="step_1", description="First"),
            PlanStep(id="step_2", description="Second"),
        ]
        plan = ExecutionPlan(task="test", steps=steps)

        assert not plan.all_completed()

        steps[0].status = StepStatus.COMPLETED
        assert not plan.all_completed()

        steps[1].status = StepStatus.COMPLETED
        assert plan.all_completed()

    def test_execution_plan_has_failed_steps(self):
        """Test checking for failed steps."""
        steps = [
            PlanStep(id="step_1", description="First"),
            PlanStep(id="step_2", description="Second"),
        ]
        plan = ExecutionPlan(task="test", steps=steps)

        assert not plan.has_failed_steps()

        steps[0].status = StepStatus.FAILED
        assert plan.has_failed_steps()

    def test_exploration_result_defaults(self):
        """Test ExplorationResult default values."""
        result = ExplorationResult()
        assert result.discovered_files == []
        assert result.code_patterns == {}
        assert result.constraints == []
        assert result.recommendations == []
        assert result.context_summary == ""

    def test_replan_request(self):
        """Test ReplanRequest creation."""
        step = PlanStep(id="step_1", description="Failed step")
        step.error = "Some error"

        request = ReplanRequest(
            trigger=ReplanTrigger.STEP_FAILURE,
            failed_step=step,
            reason="Step failed with error",
        )

        assert request.trigger == ReplanTrigger.STEP_FAILURE
        assert request.failed_step == step
        assert request.reason == "Step failed with error"


class TestPlanParsing:
    """Tests for plan parsing functionality."""

    def test_parse_simple_plan(self):
        """Test parsing a simple plan without dependencies."""
        from unittest.mock import MagicMock

        from agent.plan_execute_agent import PlanExecuteAgent

        # Create mock agent
        agent = MagicMock(spec=PlanExecuteAgent)
        agent._parse_plan = PlanExecuteAgent._parse_plan.__get__(agent)

        plan_text = """
1. Read the configuration file
2. Analyze the code structure
3. Make the required changes
4. Test the changes
"""
        exploration = ExplorationResult()
        plan = agent._parse_plan("test task", plan_text, exploration)

        assert len(plan.steps) == 4
        assert plan.steps[0].id == "step_1"
        assert plan.steps[0].description == "Read the configuration file"
        assert plan.steps[0].depends_on == []

    def test_parse_plan_with_dependencies(self):
        """Test parsing a plan with dependency markers."""
        from unittest.mock import MagicMock

        from agent.plan_execute_agent import PlanExecuteAgent

        agent = MagicMock(spec=PlanExecuteAgent)
        agent._parse_plan = PlanExecuteAgent._parse_plan.__get__(agent)

        plan_text = """
1. Read configuration [depends: none]
2. Analyze code [depends: none] [parallel: 1]
3. Make changes [depends: 1, 2]
4. Write tests [depends: 3]
"""
        exploration = ExplorationResult()
        plan = agent._parse_plan("test task", plan_text, exploration)

        assert len(plan.steps) == 4
        assert plan.steps[0].depends_on == []
        assert plan.steps[1].depends_on == []
        assert plan.steps[2].depends_on == ["step_1", "step_2"]
        assert plan.steps[3].depends_on == ["step_3"]

    def test_parse_plan_with_parallel_groups(self):
        """Test parsing a plan with parallel markers."""
        from unittest.mock import MagicMock

        from agent.plan_execute_agent import PlanExecuteAgent

        agent = MagicMock(spec=PlanExecuteAgent)
        agent._parse_plan = PlanExecuteAgent._parse_plan.__get__(agent)

        plan_text = """
1. Step one [depends: none]
2. Step two [depends: none] [parallel: 1]
3. Step three [depends: 1, 2]
"""
        exploration = ExplorationResult()
        plan = agent._parse_plan("test task", plan_text, exploration)

        assert len(plan.parallel_groups) == 1
        assert set(plan.parallel_groups[0]) == {"step_1", "step_2"}


class TestScopedMemoryView:
    """Tests for ScopedMemoryView."""

    def test_scoped_memory_view_add_message(self):
        """Test adding messages to scoped view."""
        from unittest.mock import MagicMock

        from llm.message_types import LLMMessage
        from memory.scope import MemoryScope, ScopedMemoryView

        manager = MagicMock()
        view = ScopedMemoryView(manager, MemoryScope.EXPLORATION)

        msg = LLMMessage(role="user", content="Test message")
        view.add_message(msg)

        assert len(view.get_messages()) == 1
        assert view.get_messages()[0].content == "Test message"

    def test_scoped_memory_view_get_context_with_parent(self):
        """Test getting context includes parent summary."""
        from unittest.mock import MagicMock

        from llm.message_types import LLMMessage
        from memory.scope import MemoryScope, ScopedMemoryView

        manager = MagicMock()

        # Create parent scope
        parent = ScopedMemoryView(manager, MemoryScope.GLOBAL)
        parent.set_summary("Parent summary content")

        # Create child scope
        child = ScopedMemoryView(manager, MemoryScope.EXPLORATION, parent_view=parent)
        child.add_message(LLMMessage(role="user", content="Child message"))

        context = child.get_context(include_parent=True)
        assert len(context) == 2
        assert "Parent summary content" in context[0].content
        assert context[1].content == "Child message"

    def test_scoped_memory_view_get_summary(self):
        """Test getting summary from scoped view."""
        from unittest.mock import MagicMock

        from llm.message_types import LLMMessage
        from memory.scope import MemoryScope, ScopedMemoryView

        manager = MagicMock()
        view = ScopedMemoryView(manager, MemoryScope.EXPLORATION)

        # Without explicit summary, generates from messages
        view.add_message(LLMMessage(role="user", content="Test message"))
        summary = view.get_summary()
        assert "Test message" in summary

        # With explicit summary
        view.set_summary("Custom summary")
        assert view.get_summary() == "Custom summary"

    def test_scoped_memory_view_clear(self):
        """Test clearing scoped view."""
        from unittest.mock import MagicMock

        from llm.message_types import LLMMessage
        from memory.scope import MemoryScope, ScopedMemoryView

        manager = MagicMock()
        view = ScopedMemoryView(manager, MemoryScope.EXPLORATION)

        view.add_message(LLMMessage(role="user", content="Test"))
        view.set_summary("Summary")

        assert view.message_count() == 1

        view.clear()
        assert view.message_count() == 0
        assert view.get_summary() == ""
