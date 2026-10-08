"""Core interfaces for language-grounded Assetto Corsa agents.

The module deliberately has no simulator or third-party dependency. A game
adapter implements DrivingEnvironment against an already running session.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any, Mapping, Protocol, runtime_checkable

@dataclass(frozen=True, slots=True)
class Observation:
    """Timestamped simulator snapshot. Numeric units: SI, radians, seconds."""
    timestamp: float
    speed_mps: float
    lateral_offset_m: float = 0.0
    heading_error_rad: float = 0.0
    yaw_rate_rad_s: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    steering: float = 0.0
    gear: int = 0
    rpm: float = 0.0
    lap: int | None = None
    lap_time_s: float | None = None
    damage: float = 0.0
    off_track: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class Action:
    """Normalized control request, bounded before it reaches an adapter."""
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    handbrake: float = 0.0
    duration_s: float = 0.05
    note: str = ""

    def bounded(self, *, max_duration_s: float = 0.1) -> "Action":
        clamp = lambda value: max(-1.0, min(1.0, float(value)))
        return Action(
            steering=clamp(self.steering),
            throttle=max(0.0, min(1.0, float(self.throttle))),
            brake=max(0.0, min(1.0, float(self.brake))),
            handbrake=max(0.0, min(1.0, float(self.handbrake))),
            duration_s=max(0.01, min(max_duration_s, float(self.duration_s))),
            note=self.note,
        )

@dataclass(frozen=True, slots=True)
class StepResult:
    observation: Observation
    reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    info: Mapping[str, Any] = field(default_factory=dict)

@runtime_checkable
class DrivingEnvironment(Protocol):
    """Gym-like bridge to a user-started game session; never starts the game."""
    def reset(self) -> Observation: ...
    def step(self, action: Action) -> StepResult: ...
    def close(self) -> None: ...

class GoalKind(StrEnum):
    DRIFT = "drift"
    TIME_ATTACK = "time_attack"
    FOLLOW = "follow"
    DRIVE = "drive"

@dataclass(frozen=True, slots=True)
class DrivingGoal:
    kind: GoalKind
    instruction: str
    target_speed_kmh: float | None = None
    laps: int | None = None
    constraints: tuple[str, ...] = ()

_SPEED = re.compile(r"(\d+(?:\.\d+)?)\s*(?:km/h|kph|キロ(?:毎時)?)", re.I)
_LAPS = re.compile(r"(\d+)\s*(?:laps?|周)", re.I)

def parse_goal(instruction: str) -> DrivingGoal:
    """Compile common Japanese/English phrases into a first-pass task spec."""
    text = instruction.strip()
    normalized = text.casefold()
    if any(w in normalized for w in ("drift", "ドリフト", "流し", "滑らせ")):
        kind = GoalKind.DRIFT
    elif any(w in normalized for w in ("time attack", "タイムアタック", "最速", "タイムを縮め")):
        kind = GoalKind.TIME_ATTACK
    elif any(w in normalized for w in ("follow", "chase", "追従", "追いかけ", "後ろを走")):
        kind = GoalKind.FOLLOW
    else:
        kind = GoalKind.DRIVE
    speed, laps = _SPEED.search(text), _LAPS.search(text)
    constraints = []
    if any(w in normalized for w in ("安全", "safe", "事故なし", "ぶつからず")):
        constraints.append("avoid_collision")
    if any(w in normalized for w in ("コース内", "コースアウトせず", "stay on track")):
        constraints.append("stay_on_track")
    return DrivingGoal(kind, text, float(speed.group(1)) if speed else None,
                       int(laps.group(1)) if laps else None, tuple(constraints))

class Agent(Protocol):
    def act(self, goal: DrivingGoal, observation: Observation) -> Action: ...

class HeuristicAgent:
    """Very conservative low-speed wiring baseline, not a racing policy."""
    def __init__(self, *, speed_limit_kmh: float = 40.0) -> None:
        self.speed_limit_mps = max(0.0, speed_limit_kmh) / 3.6

    def act(self, goal: DrivingGoal, observation: Observation) -> Action:
        if observation.off_track or observation.damage > 0:
            return Action(brake=0.7, note="safety stop")
        target = goal.target_speed_kmh / 3.6 if goal.target_speed_kmh else self.speed_limit_mps
        target = min(target, self.speed_limit_mps)
        error = target - max(0.0, observation.speed_mps)
        throttle = max(0.0, min(0.3, error * 0.15))
        brake = max(0.0, min(0.4, -error * 0.2))
        steering = max(-0.25, min(0.25,
            -0.45 * observation.heading_error_rad - 0.08 * observation.lateral_offset_m))
        if goal.kind == GoalKind.DRIFT:
            return Action(brake=0.2, note="drift requires a trained policy")
        if goal.kind == GoalKind.FOLLOW and not observation.extra.get("target_visible", False):
            return Action(brake=0.5, note="target not visible; hold")
        return Action(steering, throttle, brake, duration_s=0.05, note="baseline")

def run_episode(environment: DrivingEnvironment, agent: Agent, goal: DrivingGoal,
                *, max_steps: int = 10_000, max_action_duration_s: float = 0.1) -> Observation:
    """Observe, act, and observe again within a strict time/step budget."""
    observation = environment.reset()
    try:
        for _ in range(max(0, max_steps)):
            action = agent.act(goal, observation).bounded(max_duration_s=max_action_duration_s)
            result = environment.step(action)
            observation = result.observation
            if result.terminated or result.truncated:
                break
        return observation
    finally:
        environment.close()
