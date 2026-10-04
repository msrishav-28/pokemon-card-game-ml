"""Honest, seat-balanced local evaluation on the official ``cabt`` engine."""

from __future__ import annotations

import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

from .opponents import AgentSpec, load_agent, load_opponent


_BAD_STATUSES = {"INVALID", "TIMEOUT", "ERROR"}


def wilson_ci(wins: int, games: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for the binary win rate ``wins / games``."""

    if games <= 0:
        return 0.0, 1.0
    proportion = wins / games
    denominator = 1.0 + z * z / games
    center = (proportion + z * z / (2.0 * games)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / games + z * z / (4.0 * games * games)
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile_value / 100.0
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _round_optional(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def _plain_json(value: Any) -> Any:
    """Detach Kaggle Struct objects while preserving the exact live content."""

    return json.loads(json.dumps(value, ensure_ascii=False))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _invoke(agent: Callable[..., list[int]], observation: Any, configuration: Any) -> list[int]:
    code = getattr(agent, "__code__", None)
    if code is not None and code.co_argcount <= 1:
        return agent(observation)
    return agent(observation, configuration)


def action_contract(observation: dict[str, Any], action: Any) -> dict[str, Any]:
    """Pre-engine structural check; final legality remains the engine's verdict."""

    is_list = isinstance(action, list)
    integers = is_list and all(
        isinstance(index, int) and not isinstance(index, bool) for index in action
    )
    select = observation.get("select")
    if select is None:
        length_ok = is_list and len(action) == 60
        return {
            "phase": "deck",
            "ok": bool(is_list and integers and length_ok),
            "is_list": is_list,
            "integers": integers,
            "length_ok": length_ok,
            "expected_count": 60,
            "option_count": None,
            "indices_in_range": None,
            "indices_unique": None,
        }

    expected = int(select.get("maxCount", 0))
    options = select.get("option") or []
    length_ok = is_list and len(action) == expected
    in_range = bool(
        integers and all(0 <= index < len(options) for index in action)
    )
    unique = bool(integers and len(set(action)) == len(action))
    return {
        "phase": "selection",
        "ok": bool(is_list and integers and length_ok and in_range and unique),
        "is_list": is_list,
        "integers": integers,
        "length_ok": length_ok,
        "expected_count": expected,
        "option_count": len(options),
        "indices_in_range": in_range,
        "indices_unique": unique,
    }


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: TextIO | None = None

    def __enter__(self) -> "JsonlWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", buffering=1)
        return self

    def __exit__(self, *_args: Any) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def write(self, record: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("JSONL writer is not open")
        self._handle.write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        )


@dataclass
class DecisionTelemetry:
    durations_ms: list[float] = field(default_factory=list)
    remaining_before_s: list[float] = field(default_factory=list)
    estimated_remaining_after_s: list[float] = field(default_factory=list)
    contract_failures: int = 0
    exceptions: int = 0


class ObservedAgent:
    """Time an agent and append its exact live observation/action to JSONL."""

    def __init__(
        self,
        spec: AgentSpec,
        *,
        writer: JsonlWriter,
        experiment_id: str,
        game_id: str,
        pair_id: int,
        seat: int,
        role: str,
        python_seed: int,
    ) -> None:
        self.spec = spec
        self.writer = writer
        self.experiment_id = experiment_id
        self.game_id = game_id
        self.pair_id = pair_id
        self.seat = seat
        self.role = role
        self.python_seed = python_seed
        self.decision_index = 0
        self.telemetry = DecisionTelemetry()

    def __call__(self, observation: Any, configuration: Any) -> list[int]:
        raw_observation = _plain_json(observation)
        remaining_before = _as_float(raw_observation.get("remainingOverageTime"))
        act_timeout = _as_float(configuration.get("actTimeout", 0)) or 0.0
        started = time.perf_counter()
        exception: dict[str, str] | None = None
        action: Any = None
        try:
            action = _invoke(self.spec.agent, observation, configuration)
            return action
        except BaseException as exc:
            self.telemetry.exceptions += 1
            exception = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            duration_s = time.perf_counter() - started
            duration_ms = duration_s * 1000.0
            self.telemetry.durations_ms.append(duration_ms)
            if remaining_before is not None:
                self.telemetry.remaining_before_s.append(remaining_before)
            estimated_after = (
                max(0.0, remaining_before - max(0.0, duration_s - act_timeout))
                if remaining_before is not None
                else None
            )
            if estimated_after is not None:
                self.telemetry.estimated_remaining_after_s.append(estimated_after)

            contract = action_contract(raw_observation, action)
            if not contract["ok"]:
                self.telemetry.contract_failures += 1
            try:
                serialized_action = _plain_json(action)
            except (TypeError, ValueError):
                serialized_action = {"unserializable_repr": repr(action)}
            policy_details = self.spec.decision_telemetry()
            decision_record = {
                "kind": "decision",
                "schema_version": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "experiment_id": self.experiment_id,
                "game_id": self.game_id,
                "pair_id": self.pair_id,
                "python_seed": self.python_seed,
                "engine_seed": None,
                "seat": self.seat,
                "role": self.role,
                "agent": self.spec.name,
                "decision_index": self.decision_index,
                "duration_ms": round(duration_ms, 6),
                "remaining_overage_before_s": remaining_before,
                "estimated_remaining_overage_after_s": estimated_after,
                "contract": contract,
                "observation": raw_observation,
                "action": serialized_action,
                "exception": exception,
            }
            if policy_details is not None:
                # Keep common diagnostics fields top-level so terminal-linked
                # replay analysis does not need agent-specific schema logic.
                for key in ("scores", "features", "policy_fallback", "policy_error"):
                    if key in policy_details:
                        decision_record[key] = _plain_json(policy_details[key])
            self.writer.write(decision_record)
            self.decision_index += 1


def _git_metadata(repo_root: Path) -> tuple[str, bool | None]:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", None
    try:
        dirty = bool(subprocess.check_output(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        dirty = None
    return commit, dirty


def _status(state: Any) -> str:
    return str(getattr(state, "status", "UNKNOWN"))


def _reward(state: Any) -> int | float | None:
    return getattr(state, "reward", None)


def _remaining(state: Any) -> float | None:
    observation = getattr(state, "observation", None)
    if observation is None:
        return None
    value = (
        observation.get("remainingOverageTime")
        if hasattr(observation, "get")
        else getattr(observation, "remainingOverageTime", None)
    )
    return _as_float(value)


def _outcome(
    agent_status: str,
    opponent_status: str,
    agent_reward: int | float | None,
) -> str:
    if agent_status in _BAD_STATUSES:
        return "loss"
    if opponent_status in _BAD_STATUSES:
        return "win"
    if agent_reward == 1:
        return "win"
    if agent_reward == -1:
        return "loss"
    return "draw"


def _timing_summary(wrappers: list[ObservedAgent]) -> dict[str, Any]:
    durations = [
        duration
        for wrapper in wrappers
        for duration in wrapper.telemetry.durations_ms
    ]
    return {
        "decisions": len(durations),
        "mean_ms": _round_optional(_mean(durations), 6),
        "p95_ms": _round_optional(percentile(durations, 95), 6),
        "max_ms": _round_optional(max(durations) if durations else None, 6),
        "contract_failures": sum(
            wrapper.telemetry.contract_failures for wrapper in wrappers
        ),
        "exceptions": sum(wrapper.telemetry.exceptions for wrapper in wrappers),
    }


def _summarize_games(games: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [game for game in games if game["outcome"] in {"win", "loss", "draw"}]
    wins = sum(game["outcome"] == "win" for game in completed)
    losses = sum(game["outcome"] == "loss" for game in completed)
    draws = sum(game["outcome"] == "draw" for game in completed)
    ci_low, ci_high = wilson_ci(wins, len(completed))
    leftovers = [
        game["agent_remaining_overage_s"]
        for game in games
        if game["agent_remaining_overage_s"] is not None
    ]
    return {
        "attempted": len(games),
        "completed": len(completed),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / len(completed), 6) if completed else None,
        "win_rate_wilson95": [round(ci_low, 6), round(ci_high, 6)],
        "invalid": sum(game["agent_status"] == "INVALID" for game in games),
        "timeout": sum(game["agent_status"] == "TIMEOUT" for game in games),
        "error": sum(game["agent_status"] == "ERROR" for game in games),
        "runner_error": sum(game["runner_error"] is not None for game in games),
        "mean_leftover_overage_s": _round_optional(_mean(leftovers), 6),
        "min_leftover_overage_s": _round_optional(min(leftovers) if leftovers else None, 6),
    }


def _new_experiment_id(tag: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in tag)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return f"exp_{timestamp}_{cleaned or 'eval'}"


def run_batch(
    *,
    n_games: int,
    agent_path: str | os.PathLike[str],
    opponent: str,
    tag: str,
    output_dir: str | os.PathLike[str],
    replay_dir: str | os.PathLike[str],
    repo_root: str | os.PathLike[str],
    base_seed: int = 0,
    debug: bool = False,
) -> dict[str, Any]:
    """Run exactly ``n_games``, alternating seats, and persist honest telemetry.

    The Python RNG is reset to the same ``python_seed`` for both games in a
    full seat pair.  The native cabt engine exposes no seed control, so chance
    events are *not* paired.  Records therefore say ``seat-paired`` and leave
    ``engine_seed`` null.
    """

    if n_games <= 0:
        raise ValueError("n_games must be positive")

    from kaggle_environments import __version__ as kaggle_version
    from kaggle_environments import make

    root = Path(repo_root).resolve()
    agent_path = Path(agent_path)
    if not agent_path.is_absolute():
        agent_path = root / agent_path
    agent_spec = load_agent(
        agent_path,
        root,
        name="submission",
        deck_name="buddy-lucario-locked",
    )
    opponent_spec = load_opponent(opponent, root)
    # The harness owns the result-linked replay stream. Disable the legacy
    # daily policy logger on in-process file agents to avoid duplicate,
    # unjoinable records (and cross-process append races during eval).
    for spec in (agent_spec, opponent_spec):
        if spec.module is not None and hasattr(spec.module, "log_turn"):
            spec.module.log_turn = lambda *_args, **_kwargs: None
    experiment_id = _new_experiment_id(tag)
    output_path = Path(output_dir).resolve() / f"{experiment_id}.json"
    replay_path = Path(replay_dir).resolve() / f"{experiment_id}.jsonl"
    commit, dirty = _git_metadata(root)

    games: list[dict[str, Any]] = []
    agent_wrappers: list[ObservedAgent] = []
    opponent_wrappers: list[ObservedAgent] = []
    started_at = datetime.now(timezone.utc)
    wall_started = time.perf_counter()

    with JsonlWriter(replay_path) as writer:
        writer.write({
            "kind": "experiment_start",
            "schema_version": 1,
            "ts": started_at.isoformat(),
            "experiment_id": experiment_id,
            "engine": {"name": "cabt", "kaggle_environments": kaggle_version},
            "agent": agent_spec.metadata(),
            "opponent": opponent_spec.metadata(),
            "games_requested": n_games,
            "pairing": {
                "mode": "seat-paired",
                "engine_seed_control": False,
                "engine_seed": None,
                "python_seed_base": base_seed,
            },
        })

        for game_index in range(n_games):
            pair_id = game_index // 2
            agent_seat = game_index % 2
            python_seed = base_seed + pair_id
            random.seed(python_seed)
            game_id = f"{experiment_id}_g{game_index:05d}"
            agent_observed = ObservedAgent(
                agent_spec,
                writer=writer,
                experiment_id=experiment_id,
                game_id=game_id,
                pair_id=pair_id,
                seat=agent_seat,
                role="agent",
                python_seed=python_seed,
            )
            opponent_observed = ObservedAgent(
                opponent_spec,
                writer=writer,
                experiment_id=experiment_id,
                game_id=game_id,
                pair_id=pair_id,
                seat=1 - agent_seat,
                role="opponent",
                python_seed=python_seed,
            )
            agent_wrappers.append(agent_observed)
            opponent_wrappers.append(opponent_observed)
            players = (
                [agent_observed, opponent_observed]
                if agent_seat == 0
                else [opponent_observed, agent_observed]
            )

            game_started = time.perf_counter()
            runner_error: dict[str, str] | None = None
            state: list[Any] | None = None
            env = make("cabt", debug=debug)
            try:
                env.run(players)
                state = list(env.state)
            except BaseException as exc:
                runner_error = {"type": type(exc).__name__, "message": str(exc)}
                if debug:
                    raise

            if state is not None and len(state) == 2:
                statuses = [_status(item) for item in state]
                rewards = [_reward(item) for item in state]
                remaining = [_remaining(item) for item in state]
                agent_status = statuses[agent_seat]
                opponent_status = statuses[1 - agent_seat]
                outcome = _outcome(agent_status, opponent_status, rewards[agent_seat])
            else:
                statuses = ["UNKNOWN", "UNKNOWN"]
                rewards = [None, None]
                remaining = [None, None]
                agent_status = "UNKNOWN"
                opponent_status = "UNKNOWN"
                outcome = "runner_error"

            game_record = {
                "game_index": game_index,
                "game_id": game_id,
                "pair_id": pair_id,
                "pair_member": "A" if game_index % 2 == 0 else "B",
                "agent_seat": agent_seat,
                "python_seed": python_seed,
                "engine_seed": None,
                "outcome": outcome,
                "statuses": statuses,
                "rewards": rewards,
                "agent_status": agent_status,
                "opponent_status": opponent_status,
                "agent_remaining_overage_s": remaining[agent_seat],
                "opponent_remaining_overage_s": remaining[1 - agent_seat],
                "engine_steps": len(env.steps),
                "agent_decisions": agent_observed.decision_index,
                "opponent_decisions": opponent_observed.decision_index,
                "wall_time_s": round(time.perf_counter() - game_started, 6),
                "runner_error": runner_error,
            }
            games.append(game_record)
            writer.write({
                "kind": "game_end",
                "schema_version": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "experiment_id": experiment_id,
                **game_record,
            })

    overall = _summarize_games(games)
    summary = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "wall_time_s": round(time.perf_counter() - wall_started, 6),
        "engine": {
            "name": "cabt",
            "kaggle_environments": kaggle_version,
            "seed_control": False,
        },
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "git_hash": commit,
        "git_dirty": dirty,
        "agent": agent_spec.metadata(),
        "opponent": opponent_spec.metadata(),
        "deck_name": agent_spec.deck_name,
        "opponent_name": opponent_spec.name,
        "games": n_games,
        "seed_policy": "seat-paired",
        "outcome_policy": (
            "Agent INVALID, TIMEOUT, or ERROR is counted as a loss; the same "
            "opponent status is counted as an agent win. Clean games use cabt reward."
        ),
        "pairing": {
            "mode": "seat-paired",
            "full_pairs": n_games // 2,
            "unpaired_games": n_games % 2,
            "engine_seed_control": False,
            "engine_seed": None,
            "python_seed_base": base_seed,
            "note": (
                "Seats are swapped within each pair and Python agent RNG is reset; "
                "native cabt chance is uncontrolled and is not paired."
            ),
        },
        "results": overall,
        "by_agent_seat": {
            "0": _summarize_games([game for game in games if game["agent_seat"] == 0]),
            "1": _summarize_games([game for game in games if game["agent_seat"] == 1]),
        },
        "opponent_failures": {
            "invalid": sum(game["opponent_status"] == "INVALID" for game in games),
            "timeout": sum(game["opponent_status"] == "TIMEOUT" for game in games),
            "error": sum(game["opponent_status"] == "ERROR" for game in games),
        },
        "agent_timing": _timing_summary(agent_wrappers),
        "opponent_timing": _timing_summary(opponent_wrappers),
        "mean_engine_steps": _round_optional(
            _mean([float(game["engine_steps"]) for game in games]), 3
        ),
        "replay_jsonl": str(replay_path),
        "game_records": games,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    summary["experiment_json"] = str(output_path)
    return summary
