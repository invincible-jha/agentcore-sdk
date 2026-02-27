"""Agent lifecycle state machine.

Defines the canonical agent lifecycle states and valid transitions.
Supports callbacks on state change for telemetry, logging, and policy hooks.

States
------
INITIALIZED  : Agent has been created but not started.
RUNNING      : Agent is actively processing tasks.
PAUSED       : Agent execution is suspended but resumable.
COMPLETED    : Agent has finished all tasks successfully.
FAILED       : Agent has encountered a fatal error.
TERMINATED   : Agent has been explicitly shut down (terminal state).

Valid transitions
-----------------
INITIALIZED  → RUNNING, TERMINATED
RUNNING      → PAUSED, COMPLETED, FAILED, TERMINATED
PAUSED       → RUNNING, TERMINATED
COMPLETED    → TERMINATED
FAILED       → TERMINATED
"""
from __future__ import annotations

import datetime
import logging
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TransitionCallback = Callable[["AgentState", "AgentState"], None]
"""Callback signature: (from_state, to_state) → None."""


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


class AgentState(str, Enum):
    """Canonical lifecycle states for an agent."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted.

    Attributes
    ----------
    from_state:
        The current state when the invalid transition was attempted.
    to_state:
        The target state that was not reachable from *from_state*.
    """

    def __init__(self, from_state: AgentState, to_state: AgentState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition: {from_state.value!r} → {to_state.value!r}"
        )


# ---------------------------------------------------------------------------
# Valid transition map
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.INITIALIZED: frozenset({AgentState.RUNNING, AgentState.TERMINATED}),
    AgentState.RUNNING: frozenset({
        AgentState.PAUSED,
        AgentState.COMPLETED,
        AgentState.FAILED,
        AgentState.TERMINATED,
    }),
    AgentState.PAUSED: frozenset({AgentState.RUNNING, AgentState.TERMINATED}),
    AgentState.COMPLETED: frozenset({AgentState.TERMINATED}),
    AgentState.FAILED: frozenset({AgentState.TERMINATED}),
    AgentState.TERMINATED: frozenset(),  # Terminal state
}

_TERMINAL_STATES: frozenset[AgentState] = frozenset({
    AgentState.COMPLETED,
    AgentState.FAILED,
    AgentState.TERMINATED,
})


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class AgentStateMachine:
    """Manage agent lifecycle transitions with callback support.

    Parameters
    ----------
    agent_id:
        Identifier of the agent this machine tracks.
    initial_state:
        Starting state (default: INITIALIZED).

    Example
    -------
    ::

        sm = AgentStateMachine("agent-42")
        sm.on_transition(lambda f, t: print(f"Transition: {f} → {t}"))
        sm.transition_to(AgentState.RUNNING)
        sm.transition_to(AgentState.COMPLETED)
        sm.transition_to(AgentState.TERMINATED)
    """

    def __init__(
        self,
        agent_id: str,
        initial_state: AgentState = AgentState.INITIALIZED,
    ) -> None:
        self._agent_id = agent_id
        self._state: AgentState = initial_state
        self._callbacks: list[TransitionCallback] = []
        self._history: list[tuple[AgentState, AgentState, datetime.datetime]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> AgentState:
        """Return the current lifecycle state."""
        return self._state

    @property
    def agent_id(self) -> str:
        """Return the agent ID this machine tracks."""
        return self._agent_id

    @property
    def is_terminal(self) -> bool:
        """Return True if the current state is terminal (no further transitions)."""
        return self._state in _TERMINAL_STATES

    # ------------------------------------------------------------------
    # Transition
    # ------------------------------------------------------------------

    def transition_to(self, new_state: AgentState) -> None:
        """Attempt a state transition to *new_state*.

        Parameters
        ----------
        new_state:
            The desired target state.

        Raises
        ------
        StateTransitionError
            If the transition from the current state to *new_state* is not
            in the valid transition map.
        """
        if new_state not in _VALID_TRANSITIONS.get(self._state, frozenset()):
            raise StateTransitionError(self._state, new_state)

        previous = self._state
        self._state = new_state
        now = datetime.datetime.now(datetime.timezone.utc)
        self._history.append((previous, new_state, now))

        logger.debug(
            "Agent %s: %s → %s", self._agent_id, previous.value, new_state.value
        )

        for callback in self._callbacks:
            try:
                callback(previous, new_state)
            except Exception as exc:
                logger.warning(
                    "Transition callback raised for %s: %s", self._agent_id, exc
                )

    # ------------------------------------------------------------------
    # Convenience transition methods
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Transition to RUNNING state.

        Raises
        ------
        StateTransitionError
            If RUNNING is not reachable from the current state.
        """
        self.transition_to(AgentState.RUNNING)

    def pause(self) -> None:
        """Transition to PAUSED state.

        Raises
        ------
        StateTransitionError
            If PAUSED is not reachable from the current state.
        """
        self.transition_to(AgentState.PAUSED)

    def resume(self) -> None:
        """Transition from PAUSED back to RUNNING.

        Raises
        ------
        StateTransitionError
            If RUNNING is not reachable from the current state.
        """
        self.transition_to(AgentState.RUNNING)

    def complete(self) -> None:
        """Transition to COMPLETED state.

        Raises
        ------
        StateTransitionError
            If COMPLETED is not reachable from the current state.
        """
        self.transition_to(AgentState.COMPLETED)

    def fail(self) -> None:
        """Transition to FAILED state.

        Raises
        ------
        StateTransitionError
            If FAILED is not reachable from the current state.
        """
        self.transition_to(AgentState.FAILED)

    def terminate(self) -> None:
        """Transition to TERMINATED state.

        Raises
        ------
        StateTransitionError
            If TERMINATED is not reachable from the current state.
        """
        self.transition_to(AgentState.TERMINATED)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_transition(self, callback: TransitionCallback) -> None:
        """Register a callback to be invoked on every state transition.

        Parameters
        ----------
        callback:
            A callable ``(from_state, to_state) → None``.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: TransitionCallback) -> bool:
        """Remove a previously registered callback.

        Parameters
        ----------
        callback:
            The callback to remove.

        Returns
        -------
        bool
            True if the callback was found and removed.
        """
        try:
            self._callbacks.remove(callback)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # History and introspection
    # ------------------------------------------------------------------

    def get_history(
        self,
    ) -> list[tuple[AgentState, AgentState, datetime.datetime]]:
        """Return all transitions recorded, oldest first.

        Returns
        -------
        list[tuple[AgentState, AgentState, datetime.datetime]]
            Each entry is (from_state, to_state, timestamp).
        """
        return list(self._history)

    def can_transition_to(self, target: AgentState) -> bool:
        """Return True if *target* is a valid next state.

        Parameters
        ----------
        target:
            The state to check reachability for.

        Returns
        -------
        bool
            True when a transition from the current state to *target*
            is permitted.
        """
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def valid_next_states(self) -> list[AgentState]:
        """Return all states reachable from the current state.

        Returns
        -------
        list[AgentState]
            Valid target states, sorted by enum value.
        """
        return sorted(
            _VALID_TRANSITIONS.get(self._state, frozenset()),
            key=lambda s: s.value,
        )

    def __repr__(self) -> str:
        return (
            f"AgentStateMachine(agent_id={self._agent_id!r}, "
            f"state={self._state.value!r})"
        )


__all__ = [
    "AgentState",
    "AgentStateMachine",
    "StateTransitionError",
    "TransitionCallback",
]
