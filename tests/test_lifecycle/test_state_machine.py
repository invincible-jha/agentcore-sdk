"""Tests for agentcore.lifecycle.state_machine."""
from __future__ import annotations

import pytest

from agentcore.lifecycle.state_machine import (
    AgentState,
    AgentStateMachine,
    StateTransitionError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sm() -> AgentStateMachine:
    return AgentStateMachine(agent_id="agent-test")


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_default_initial_state(self, sm: AgentStateMachine) -> None:
        assert sm.state == AgentState.INITIALIZED

    def test_custom_initial_state(self) -> None:
        sm = AgentStateMachine("a1", initial_state=AgentState.RUNNING)
        assert sm.state == AgentState.RUNNING

    def test_agent_id(self, sm: AgentStateMachine) -> None:
        assert sm.agent_id == "agent-test"

    def test_not_terminal_initially(self, sm: AgentStateMachine) -> None:
        assert sm.is_terminal is False

    def test_repr_contains_state(self, sm: AgentStateMachine) -> None:
        assert "initialized" in repr(sm)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_initialized_to_running(self, sm: AgentStateMachine) -> None:
        sm.transition_to(AgentState.RUNNING)
        assert sm.state == AgentState.RUNNING

    def test_running_to_paused(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.pause()
        assert sm.state == AgentState.PAUSED

    def test_paused_to_running(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.pause()
        sm.resume()
        assert sm.state == AgentState.RUNNING

    def test_running_to_completed(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.complete()
        assert sm.state == AgentState.COMPLETED

    def test_running_to_failed(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.fail()
        assert sm.state == AgentState.FAILED

    def test_running_to_terminated(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.terminate()
        assert sm.state == AgentState.TERMINATED

    def test_completed_to_terminated(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.complete()
        sm.terminate()
        assert sm.state == AgentState.TERMINATED

    def test_failed_to_terminated(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.fail()
        sm.terminate()
        assert sm.state == AgentState.TERMINATED

    def test_initialized_to_terminated(self, sm: AgentStateMachine) -> None:
        sm.terminate()
        assert sm.state == AgentState.TERMINATED


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_initialized_cannot_pause(self, sm: AgentStateMachine) -> None:
        with pytest.raises(StateTransitionError):
            sm.pause()

    def test_initialized_cannot_complete(self, sm: AgentStateMachine) -> None:
        with pytest.raises(StateTransitionError):
            sm.complete()

    def test_initialized_cannot_fail(self, sm: AgentStateMachine) -> None:
        with pytest.raises(StateTransitionError):
            sm.fail()

    def test_completed_cannot_run(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.complete()
        with pytest.raises(StateTransitionError):
            sm.start()

    def test_terminated_cannot_transition(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.terminate()
        with pytest.raises(StateTransitionError):
            sm.start()

    def test_failed_cannot_run(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.fail()
        with pytest.raises(StateTransitionError):
            sm.start()

    def test_error_contains_states(self, sm: AgentStateMachine) -> None:
        with pytest.raises(StateTransitionError) as exc_info:
            sm.pause()
        assert "initialized" in str(exc_info.value).lower()
        assert "paused" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Terminal state
# ---------------------------------------------------------------------------


class TestTerminalState:
    def test_terminated_is_terminal(self, sm: AgentStateMachine) -> None:
        sm.terminate()
        assert sm.is_terminal is True

    def test_completed_is_terminal(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.complete()
        assert sm.is_terminal is True

    def test_failed_is_terminal(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.fail()
        assert sm.is_terminal is True

    def test_running_is_not_terminal(self, sm: AgentStateMachine) -> None:
        sm.start()
        assert sm.is_terminal is False


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    def test_callback_called_on_transition(self, sm: AgentStateMachine) -> None:
        calls: list[tuple[AgentState, AgentState]] = []
        sm.on_transition(lambda f, t: calls.append((f, t)))
        sm.start()
        assert calls == [(AgentState.INITIALIZED, AgentState.RUNNING)]

    def test_multiple_callbacks_called(self, sm: AgentStateMachine) -> None:
        count1 = [0]
        count2 = [0]
        sm.on_transition(lambda f, t: count1.__setitem__(0, count1[0] + 1))
        sm.on_transition(lambda f, t: count2.__setitem__(0, count2[0] + 1))
        sm.start()
        assert count1[0] == 1
        assert count2[0] == 1

    def test_callback_receives_correct_states(self, sm: AgentStateMachine) -> None:
        transitions: list[tuple[AgentState, AgentState]] = []
        sm.on_transition(lambda f, t: transitions.append((f, t)))
        sm.start()
        sm.pause()
        sm.resume()
        sm.complete()
        assert transitions[0] == (AgentState.INITIALIZED, AgentState.RUNNING)
        assert transitions[1] == (AgentState.RUNNING, AgentState.PAUSED)
        assert transitions[2] == (AgentState.PAUSED, AgentState.RUNNING)
        assert transitions[3] == (AgentState.RUNNING, AgentState.COMPLETED)

    def test_remove_callback(self, sm: AgentStateMachine) -> None:
        calls: list[int] = [0]

        def cb(f: AgentState, t: AgentState) -> None:
            calls[0] += 1

        sm.on_transition(cb)
        sm.start()
        sm.remove_callback(cb)
        sm.pause()
        assert calls[0] == 1  # Only called once (before removal)

    def test_remove_nonexistent_callback_returns_false(
        self, sm: AgentStateMachine
    ) -> None:
        result = sm.remove_callback(lambda f, t: None)
        assert result is False

    def test_callback_exception_does_not_halt_transition(
        self, sm: AgentStateMachine
    ) -> None:
        def bad_callback(f: AgentState, t: AgentState) -> None:
            raise RuntimeError("callback error")

        sm.on_transition(bad_callback)
        sm.start()  # Should not raise
        assert sm.state == AgentState.RUNNING


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_empty_initially(self, sm: AgentStateMachine) -> None:
        assert sm.get_history() == []

    def test_history_grows_with_transitions(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.complete()
        history = sm.get_history()
        assert len(history) == 2

    def test_history_contains_timestamps(self, sm: AgentStateMachine) -> None:
        sm.start()
        history = sm.get_history()
        assert history[0][2] is not None

    def test_history_order_correct(self, sm: AgentStateMachine) -> None:
        sm.start()
        sm.pause()
        sm.resume()
        history = sm.get_history()
        assert history[0][0] == AgentState.INITIALIZED
        assert history[1][0] == AgentState.RUNNING
        assert history[2][0] == AgentState.PAUSED


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class TestIntrospection:
    def test_can_transition_to_valid(self, sm: AgentStateMachine) -> None:
        assert sm.can_transition_to(AgentState.RUNNING) is True

    def test_can_transition_to_invalid(self, sm: AgentStateMachine) -> None:
        assert sm.can_transition_to(AgentState.PAUSED) is False

    def test_valid_next_states_from_initialized(self, sm: AgentStateMachine) -> None:
        states = sm.valid_next_states()
        assert AgentState.RUNNING in states
        assert AgentState.TERMINATED in states

    def test_valid_next_states_from_terminated(self, sm: AgentStateMachine) -> None:
        sm.terminate()
        states = sm.valid_next_states()
        assert states == []

    def test_state_enum_values(self) -> None:
        assert AgentState.INITIALIZED.value == "initialized"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.PAUSED.value == "paused"
        assert AgentState.COMPLETED.value == "completed"
        assert AgentState.FAILED.value == "failed"
        assert AgentState.TERMINATED.value == "terminated"
