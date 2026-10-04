"""Read-only diagnostics for cabt JSONL replay streams.

The repository currently has more than one replay schema.  This module keeps
their evidence separate:

* evaluation ``decision`` records contain exact observations/legal options and
  share ``game_id`` with a terminal ``game_end`` record;
* policy logger records contain option scores and ``episode_id`` but (at the
  time this module was written) no terminal record or raw legal-option payload;
* the oldest records contain options but no episode identifier or scores.

Those streams must not be joined by timestamp or by a prize snapshot.  A loss
is only a loss here when terminal metadata says so.
"""

from __future__ import annotations

import glob
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from ptcg_agent.env.adapter import SELECT_CONTEXT_NAMES


_TERMINAL_KINDS = {"game_end", "terminal", "episode_end"}
_KNOWN_OUTCOMES = {"win", "loss", "draw", "runner_error"}
_BAD_STATUSES = {"INVALID", "TIMEOUT", "ERROR"}


@dataclass
class _GroupEvidence:
    """Evidence linked by an explicit game_id or episode_id only."""

    group_key: str
    id_kind: str
    identifier: str
    decisions: int = 0
    agent_decisions: int = 0
    scored_decisions: int = 0
    legal_option_payload_decisions: int = 0
    scored_legal_option_decisions: int = 0
    terminals: list[dict[str, Any]] = field(default_factory=list)


def discover_jsonl_paths(inputs: Sequence[str | Path]) -> list[Path]:
    """Resolve files, directories, and shell-style globs without writing.

    Directories are searched recursively for ``*.jsonl``.  Missing explicit
    paths raise ``FileNotFoundError`` so an empty audit cannot look successful.
    """

    discovered: list[Path] = []
    for raw_input in inputs:
        token = str(raw_input)
        if any(char in token for char in "*?["):
            matches = [Path(match) for match in glob.glob(token, recursive=True)]
            if not matches:
                raise FileNotFoundError(f"JSONL pattern matched nothing: {token}")
            discovered.extend(path for path in matches if path.is_file())
            continue

        path = Path(token)
        if path.is_dir():
            discovered.extend(sorted(path.rglob("*.jsonl")))
        elif path.is_file():
            discovered.append(path)
        else:
            raise FileNotFoundError(f"JSONL input does not exist: {path}")

    unique: dict[str, Path] = {}
    for path in discovered:
        resolved = path.resolve()
        unique[str(resolved).casefold()] = resolved
    return sorted(unique.values(), key=lambda path: str(path).casefold())


def _iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                yield line_number, None, f"{type(exc).__name__}: {exc}"
                continue
            if not isinstance(value, dict):
                yield line_number, None, "record is not a JSON object"
                continue
            yield line_number, value, None


def _record_kind(record: dict[str, Any]) -> str:
    kind = record.get("kind")
    if isinstance(kind, str) and kind:
        return kind
    if "chosen_indices" in record:
        return "legacy_decision_options"
    if "chosen" in record:
        return "policy_decision_scores"
    if record.get("terminal") is True:
        return "terminal"
    return "unknown"


def _is_decision(record: dict[str, Any], kind: str) -> bool:
    return kind == "decision" or kind in {
        "legacy_decision_options",
        "policy_decision_scores",
    }


def _is_terminal(record: dict[str, Any], kind: str) -> bool:
    return kind in _TERMINAL_KINDS or record.get("terminal") is True


def _group_identity(record: dict[str, Any]) -> tuple[str, str, str] | None:
    game_id = record.get("game_id")
    if isinstance(game_id, str) and game_id:
        return f"game:{game_id}", "game_id", game_id
    episode_id = record.get("episode_id")
    if isinstance(episode_id, str) and episode_id:
        return f"episode:{episode_id}", "episode_id", episode_id
    return None


def _context(record: dict[str, Any]) -> str:
    direct = record.get("context")
    if isinstance(direct, str) and direct:
        return direct
    if isinstance(direct, int) and not isinstance(direct, bool):
        return SELECT_CONTEXT_NAMES.get(direct, f"UNKNOWN_{direct}")

    observation = record.get("observation")
    if not isinstance(observation, dict):
        return "UNKNOWN"
    select = observation.get("select")
    if select is None:
        return "DECK"
    if not isinstance(select, dict):
        return "UNKNOWN"
    context_id = select.get("context")
    if isinstance(context_id, int) and not isinstance(context_id, bool):
        return SELECT_CONTEXT_NAMES.get(context_id, f"UNKNOWN_{context_id}")
    if isinstance(context_id, str) and context_id:
        return context_id
    return "UNKNOWN"


def _scores(record: dict[str, Any]) -> list[float] | None:
    raw_scores = record.get("scores")
    if not isinstance(raw_scores, list):
        return None
    scores: list[float] = []
    for value in raw_scores:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        converted = float(value)
        if not math.isfinite(converted):
            return None
        scores.append(converted)
    return scores


def _legal_options(record: dict[str, Any]) -> list[Any] | None:
    direct = record.get("legal_options")
    if isinstance(direct, list):
        return direct
    legacy = record.get("options")
    if isinstance(legacy, list):
        return legacy
    observation = record.get("observation")
    if not isinstance(observation, dict):
        return None
    select = observation.get("select")
    if not isinstance(select, dict):
        return None
    options = select.get("option")
    return options if isinstance(options, list) else None


def _chosen_indices(record: dict[str, Any], context: str) -> list[int] | None:
    if "chosen" in record:
        raw = record.get("chosen")
    elif "chosen_indices" in record:
        raw = record.get("chosen_indices")
    elif context != "DECK":
        raw = record.get("action")
    else:
        return None
    if not isinstance(raw, list):
        return None
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in raw):
        return None
    return raw


def _expected_count(record: dict[str, Any]) -> int | None:
    direct = record.get("maxCount")
    if isinstance(direct, int) and not isinstance(direct, bool):
        return direct
    contract = record.get("contract")
    if isinstance(contract, dict):
        expected = contract.get("expected_count")
        if isinstance(expected, int) and not isinstance(expected, bool):
            return expected
    observation = record.get("observation")
    if isinstance(observation, dict) and isinstance(observation.get("select"), dict):
        expected = observation["select"].get("maxCount")
        if isinstance(expected, int) and not isinstance(expected, bool):
            return expected
    return None


def _all_feature_values_zero(record: dict[str, Any]) -> bool | None:
    rows = record.get("features")
    if not isinstance(rows, list) or not rows:
        return None
    saw_number = False
    for row in rows:
        if not isinstance(row, dict):
            return None
        for value in row.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            saw_number = True
            if float(value) != 0.0:
                return False
    return True if saw_number else None


def _visible_base_damage_lethal_signal(
    record: dict[str, Any],
    options: list[Any] | None,
    chosen: list[int] | None,
) -> tuple[bool, bool]:
    """Return ``(opportunity, missed)`` for a narrow, observable Lucario KO.

    This is intentionally a pathology signal rather than a causal loss label.
    It uses only the verified printed base damage of Aura Jab (982) and Mega
    Brave (983), visible Active HP, and exactly one prize remaining.  It does
    not infer Weakness, Resistance, buffs, prevention effects, or hidden state.
    """
    if record.get("role") != "agent" or options is None or chosen is None:
        return False, False
    observation = record.get("observation")
    if not isinstance(observation, dict):
        return False, False
    select = observation.get("select")
    current = observation.get("current")
    if not isinstance(select, dict) or not isinstance(current, dict):
        return False, False
    if select.get("context") != 0 or select.get("maxCount") != 1:
        return False, False
    your_index = current.get("yourIndex")
    players = current.get("players")
    if (
        not isinstance(your_index, int)
        or isinstance(your_index, bool)
        or your_index not in (0, 1)
        or not isinstance(players, list)
        or len(players) != 2
        or not all(isinstance(player, dict) for player in players)
    ):
        return False, False
    prizes = players[your_index].get("prize")
    opponent_active = players[1 - your_index].get("active")
    if not isinstance(prizes, list) or len(prizes) != 1:
        return False, False
    if not isinstance(opponent_active, list) or not opponent_active:
        return False, False
    active = opponent_active[0]
    if not isinstance(active, dict):
        return False, False
    hp = active.get("hp")
    if isinstance(hp, bool) or not isinstance(hp, (int, float)):
        return False, False

    verified_damage = {982: 130, 983: 270}
    lethal_indices = {
        index
        for index, option in enumerate(options)
        if isinstance(option, dict)
        and option.get("type") == 13
        and verified_damage.get(option.get("attackId"), 0) >= hp
    }
    if not lethal_indices:
        return False, False
    return True, not any(index in lethal_indices for index in chosen)


def _explicit_outcome(terminal: dict[str, Any]) -> str | None:
    outcome = terminal.get("outcome")
    if isinstance(outcome, str) and outcome.casefold() in _KNOWN_OUTCOMES:
        return outcome.casefold()

    reward = terminal.get("reward")
    if isinstance(reward, (int, float)) and not isinstance(reward, bool):
        if reward == 1:
            return "win"
        if reward == -1:
            return "loss"
        if reward == 0:
            return "draw"

    rewards = terminal.get("rewards")
    seat = terminal.get("agent_seat")
    if (
        isinstance(rewards, list)
        and isinstance(seat, int)
        and not isinstance(seat, bool)
        and 0 <= seat < len(rewards)
    ):
        seat_reward = rewards[seat]
        if seat_reward == 1:
            return "win"
        if seat_reward == -1:
            return "loss"
        if seat_reward == 0:
            return "draw"

    agent_status = str(terminal.get("agent_status", "")).upper()
    opponent_status = str(terminal.get("opponent_status", "")).upper()
    if agent_status in _BAD_STATUSES:
        return "loss"
    if opponent_status in _BAD_STATUSES:
        return "win"
    if terminal.get("runner_error") is not None:
        return "runner_error"
    return None


def _failure_bucket(terminal: dict[str, Any], outcome: str | None) -> str | None:
    agent_status = str(terminal.get("agent_status", "")).upper()
    runner_error = terminal.get("runner_error")
    if runner_error is not None or outcome == "runner_error":
        return "runner error (explicit terminal metadata)"
    if agent_status == "INVALID":
        return "illegal action (engine status INVALID)"
    if agent_status == "TIMEOUT":
        return "timeout / overage exhaustion (engine status TIMEOUT)"
    if agent_status == "ERROR":
        return "agent or engine error (engine status ERROR)"
    if outcome != "loss":
        return None

    explicit = terminal.get("failure_category", terminal.get("failure_bucket"))
    if isinstance(explicit, str) and explicit.strip():
        return f"explicitly tagged gameplay loss: {explicit.strip()}"
    return "gameplay loss; decision cause unclassifiable"


def _explicit_causal_reference(terminal: dict[str, Any]) -> bool:
    return any(
        key in terminal and terminal.get(key) is not None
        for key in ("causal_decision_index", "causal_decision_id", "failure_decision")
    )


def _safe_min(values: list[float]) -> float | None:
    return min(values) if values else None


def _safe_max(values: list[float]) -> float | None:
    return max(values) if values else None


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def analyze_jsonl(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Analyze replay JSONL and return a JSON-serializable evidence report.

    This function never interprets prize counts as outcomes and never links two
    records unless they carry the same explicit ``game_id`` or ``episode_id``.
    """

    resolved_paths = [Path(path).resolve() for path in paths]
    if not resolved_paths:
        raise ValueError("at least one replay JSONL path is required")

    totals: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    context_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    groups: dict[str, _GroupEvidence] = {}
    file_reports: list[dict[str, Any]] = []
    parse_error_samples: list[str] = []
    remaining_values: list[float] = []
    duration_values: list[float] = []

    for path in resolved_paths:
        per_file: Counter[str] = Counter()
        per_file_kinds: Counter[str] = Counter()
        for line_number, record, error in _iter_jsonl(path):
            totals["nonblank_lines"] += 1
            per_file["nonblank_lines"] += 1
            if error is not None or record is None:
                totals["malformed_records"] += 1
                per_file["malformed_records"] += 1
                if len(parse_error_samples) < 10:
                    parse_error_samples.append(f"{path}:{line_number}: {error}")
                continue

            totals["json_objects"] += 1
            per_file["json_objects"] += 1
            kind = _record_kind(record)
            kind_counts[kind] += 1
            per_file_kinds[kind] += 1

            identity = _group_identity(record)
            group: _GroupEvidence | None = None
            if identity is not None:
                group_key, id_kind, identifier = identity
                group = groups.setdefault(
                    group_key,
                    _GroupEvidence(group_key, id_kind, identifier),
                )

            if _is_terminal(record, kind):
                totals["terminal_records"] += 1
                per_file["terminal_records"] += 1
                if group is None:
                    totals["terminal_records_without_group_id"] += 1
                else:
                    group.terminals.append(record)

            if not _is_decision(record, kind):
                continue

            totals["decision_records"] += 1
            per_file["decision_records"] += 1
            if group is None:
                totals["decision_records_without_group_id"] += 1
                per_file["decision_records_without_group_id"] += 1
            else:
                group.decisions += 1

            role = record.get("role")
            role_name = role if isinstance(role, str) and role else "unspecified"
            role_counts[role_name] += 1
            if group is not None and role_name == "agent":
                group.agent_decisions += 1

            context = _context(record)
            context_counts[context] += 1
            scores = _scores(record)
            options = _legal_options(record)
            chosen = _chosen_indices(record, context)
            expected_count = _expected_count(record)

            if "scores" in record and scores is None:
                signal_counts["invalid_score_vector"] += 1
            if scores is not None:
                totals["score_vector_decisions"] += 1
                per_file["score_vector_decisions"] += 1
                if group is not None:
                    group.scored_decisions += 1
                if scores and all(score == scores[0] for score in scores):
                    signal_counts["flat_score_vector"] += 1
                if scores and all(score == 0.0 for score in scores):
                    signal_counts["all_zero_score_vector"] += 1

            if options is not None:
                totals["legal_option_payload_decisions"] += 1
                per_file["legal_option_payload_decisions"] += 1
                if group is not None:
                    group.legal_option_payload_decisions += 1

            if scores is not None and options is not None:
                totals["scored_legal_option_decisions"] += 1
                per_file["scored_legal_option_decisions"] += 1
                if group is not None:
                    group.scored_legal_option_decisions += 1
                if len(scores) != len(options):
                    signal_counts["score_option_length_mismatch"] += 1

            if scores is not None and chosen is not None:
                if any(index < 0 or index >= len(scores) for index in chosen):
                    signal_counts["chosen_index_outside_score_vector"] += 1
                elif chosen:
                    pick_count = len(chosen)
                    cutoff = sorted(scores, reverse=True)[pick_count - 1]
                    if any(scores[index] < cutoff for index in chosen):
                        signal_counts["chosen_below_top_ranked_score"] += 1

            if chosen is not None:
                if len(chosen) != len(set(chosen)):
                    signal_counts["duplicate_chosen_indices"] += 1
                if expected_count is not None and len(chosen) != expected_count:
                    signal_counts["selection_count_mismatch"] += 1

            lethal_opportunity, lethal_missed = _visible_base_damage_lethal_signal(
                record, options, chosen
            )
            if lethal_opportunity:
                signal_counts["visible_base_damage_game_lethal_opportunity"] += 1
            if lethal_missed:
                signal_counts["visible_base_damage_game_lethal_missed"] += 1

            contract = record.get("contract")
            if isinstance(contract, dict):
                totals["explicit_contract_checks"] += 1
                if contract.get("ok") is False:
                    signal_counts["explicit_contract_failure"] += 1
            if record.get("exception") is not None:
                signal_counts["explicit_decision_exception"] += 1
            if record.get("fallback") or record.get("policy_fallback"):
                signal_counts["explicit_policy_fallback"] += 1
            feature_zero = _all_feature_values_zero(record)
            if feature_zero is True:
                signal_counts["all_zero_feature_vector"] += 1

            remaining = record.get(
                "remaining_overage_before_s", record.get("remaining_overage_time")
            )
            if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
                remaining_value = float(remaining)
                if math.isfinite(remaining_value):
                    remaining_values.append(remaining_value)
                    if remaining_value < 60.0:
                        signal_counts["remaining_overage_below_60s"] += 1
            duration = record.get("duration_ms")
            if isinstance(duration, (int, float)) and not isinstance(duration, bool):
                duration_value = float(duration)
                if math.isfinite(duration_value):
                    duration_values.append(duration_value)

        file_reports.append({
            "path": str(path),
            "nonblank_lines": per_file["nonblank_lines"],
            "json_objects": per_file["json_objects"],
            "malformed_records": per_file["malformed_records"],
            "record_kinds": dict(sorted(per_file_kinds.items())),
            "decision_records": per_file["decision_records"],
            "terminal_records": per_file["terminal_records"],
            "score_vector_decisions": per_file["score_vector_decisions"],
            "legal_option_payload_decisions": per_file["legal_option_payload_decisions"],
            "scored_legal_option_decisions": per_file["scored_legal_option_decisions"],
            "decision_records_without_group_id": per_file[
                "decision_records_without_group_id"
            ],
        })

    outcome_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    unclassifiable_counts: Counter[str] = Counter()
    group_reports: list[dict[str, Any]] = []
    loss_coverage: Counter[str] = Counter()

    for group in sorted(groups.values(), key=lambda item: item.group_key):
        terminal = group.terminals[-1] if group.terminals else None
        outcome: str | None = None
        bucket: str | None = None
        classification: str
        explicit_causal_reference = False
        if terminal is None:
            classification = "unclassifiable: no terminal metadata linked by explicit ID"
            if group.decisions:
                unclassifiable_counts[
                    "no terminal metadata linked by explicit ID"
                ] += 1
        else:
            outcome = _explicit_outcome(terminal)
            if outcome is None:
                classification = (
                    "unclassifiable: terminal metadata has no explicit outcome/reward"
                )
                unclassifiable_counts[
                    "terminal metadata has no explicit outcome/reward"
                ] += 1
            else:
                outcome_counts[outcome] += 1
                bucket = _failure_bucket(terminal, outcome)
                if bucket is None:
                    classification = f"terminal {outcome}; not a failure bucket"
                else:
                    classification = bucket
                    failure_counts[bucket] += 1
                explicit_causal_reference = _explicit_causal_reference(terminal)

            if outcome == "loss":
                loss_coverage["terminal_losses"] += 1
                if group.decisions:
                    loss_coverage["with_linked_decisions"] += 1
                if group.scored_decisions:
                    loss_coverage["with_score_vectors"] += 1
                if group.legal_option_payload_decisions:
                    loss_coverage["with_legal_option_payloads"] += 1
                if group.scored_legal_option_decisions:
                    loss_coverage["with_scores_and_options_same_decision"] += 1
                if bucket and bucket.startswith("explicitly tagged"):
                    loss_coverage["with_explicit_failure_category"] += 1
                if explicit_causal_reference:
                    loss_coverage["with_explicit_causal_decision_reference"] += 1

        group_reports.append({
            "group_id": group.identifier,
            "id_kind": group.id_kind,
            "decisions": group.decisions,
            "agent_decisions": group.agent_decisions,
            "terminal_records": len(group.terminals),
            "outcome": outcome,
            "failure_bucket": bucket,
            "classification": classification,
            "scored_decisions": group.scored_decisions,
            "legal_option_payload_decisions": group.legal_option_payload_decisions,
            "scored_legal_option_decisions": group.scored_legal_option_decisions,
            "explicit_causal_decision_reference": explicit_causal_reference,
        })

    game_groups = sum(group.id_kind == "game_id" for group in groups.values())
    episode_groups = sum(group.id_kind == "episode_id" for group in groups.values())
    groups_with_decisions = sum(group.decisions > 0 for group in groups.values())
    groups_with_terminal = sum(bool(group.terminals) for group in groups.values())
    linked_groups = sum(
        group.decisions > 0 and bool(group.terminals) for group in groups.values()
    )

    terminal_losses = loss_coverage["terminal_losses"]
    attribution_ready = sum(
        report["outcome"] == "loss"
        and report["scored_legal_option_decisions"] > 0
        and report["explicit_causal_decision_reference"]
        for report in group_reports
    )
    loss_coverage["attribution_ready_losses"] = attribution_ready

    limitations: list[str] = []
    if episode_groups and game_groups:
        limitations.append(
            "game_id and episode_id streams have no shared identifier; their group "
            "counts may describe the same live games and must not be added as a "
            "deduplicated episode count."
        )
    if totals["decision_records_without_group_id"]:
        limitations.append(
            "Some legacy decisions have no game_id/episode_id, so no episode or "
            "terminal outcome can be attached to them."
        )
    if totals["score_vector_decisions"] and not totals["scored_legal_option_decisions"]:
        limitations.append(
            "Score vectors and raw legal-option payloads never coexist in one "
            "decision record; score indices cannot be translated into action semantics."
        )
    if terminal_losses and not loss_coverage["with_score_vectors"]:
        limitations.append(
            "No terminal loss group contains a score vector, so current losses cannot "
            "be linked to the policy's ranked choices."
        )
    if terminal_losses and not attribution_ready:
        limitations.append(
            "No loss has both an explicit causal decision reference and a decision "
            "containing scores plus legal options; gameplay failure labels would be guesses."
        )
    limitations.append(
        "Prize snapshots are descriptive state only and are never used as terminal outcomes."
    )

    return {
        "schema_version": 1,
        "files": file_reports,
        "records": {
            "nonblank_lines": totals["nonblank_lines"],
            "json_objects": totals["json_objects"],
            "malformed_records": totals["malformed_records"],
            "parse_error_samples": parse_error_samples,
            "record_kinds": dict(sorted(kind_counts.items())),
        },
        "grouping": {
            "game_id_groups": game_groups,
            "episode_id_groups": episode_groups,
            "groups_with_decisions": groups_with_decisions,
            "groups_with_terminal_metadata": groups_with_terminal,
            "groups_with_decisions_and_terminal_metadata": linked_groups,
            "decision_records_without_group_id": totals[
                "decision_records_without_group_id"
            ],
            "terminal_records_without_group_id": totals[
                "terminal_records_without_group_id"
            ],
            "confirmed_terminal_games": len({
                group.identifier
                for group in groups.values()
                if group.id_kind == "game_id" and group.terminals
            }),
        },
        "decisions": {
            "total": totals["decision_records"],
            "roles": dict(sorted(role_counts.items())),
            "contexts": dict(
                sorted(context_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            "score_vector_decisions": totals["score_vector_decisions"],
            "legal_option_payload_decisions": totals[
                "legal_option_payload_decisions"
            ],
            "scored_legal_option_decisions": totals[
                "scored_legal_option_decisions"
            ],
            "explicit_contract_checks": totals["explicit_contract_checks"],
            "signals_not_causal_labels": dict(sorted(signal_counts.items())),
            "remaining_overage_s": {
                "observations": len(remaining_values),
                "minimum": _round_or_none(_safe_min(remaining_values)),
                "maximum": _round_or_none(_safe_max(remaining_values)),
            },
            "duration_ms": {
                "observations": len(duration_values),
                "minimum": _round_or_none(_safe_min(duration_values)),
                "maximum": _round_or_none(_safe_max(duration_values)),
            },
        },
        "terminal": {
            "records": totals["terminal_records"],
            "outcomes": dict(sorted(outcome_counts.items())),
            "failure_buckets": dict(sorted(failure_counts.items())),
            "unclassifiable_groups": dict(sorted(unclassifiable_counts.items())),
        },
        "loss_attribution_coverage": {
            key: loss_coverage[key]
            for key in (
                "terminal_losses",
                "with_linked_decisions",
                "with_score_vectors",
                "with_legal_option_payloads",
                "with_scores_and_options_same_decision",
                "with_explicit_failure_category",
                "with_explicit_causal_decision_reference",
                "attribution_ready_losses",
            )
        },
        "groups": group_reports,
        "limitations": limitations,
    }


def render_plain_text(report: dict[str, Any]) -> str:
    """Render the report as a concise, plain-language audit."""

    records = report["records"]
    grouping = report["grouping"]
    decisions = report["decisions"]
    terminal = report["terminal"]
    coverage = report["loss_attribution_coverage"]
    lines = [
        "Replay diagnostics (read-only; outcomes require terminal metadata)",
        "",
        (
            f"Read {records['json_objects']} JSON objects from {len(report['files'])} "
            f"file(s); malformed records: {records['malformed_records']}."
        ),
        (
            f"Confirmed terminal games: {grouping['confirmed_terminal_games']}; "
            f"game_id groups: {grouping['game_id_groups']}; episode_id groups: "
            f"{grouping['episode_id_groups']}; ungrouped decisions: "
            f"{grouping['decision_records_without_group_id']}."
        ),
        (
            f"Decisions: {decisions['total']}; with score vectors: "
            f"{decisions['score_vector_decisions']}; with raw legal options: "
            f"{decisions['legal_option_payload_decisions']}; with both in the same "
            f"record: {decisions['scored_legal_option_decisions']}."
        ),
        "",
        "Terminal outcomes:",
    ]
    if terminal["outcomes"]:
        lines.extend(
            f"- {name}: {count}" for name, count in terminal["outcomes"].items()
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Failure buckets (terminal evidence only):")
    if terminal["failure_buckets"]:
        lines.extend(
            f"- {name}: {count}"
            for name, count in terminal["failure_buckets"].items()
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Loss-attribution coverage:")
    lines.extend([
        f"- terminal losses: {coverage['terminal_losses']}",
        f"- losses linked to decisions: {coverage['with_linked_decisions']}",
        f"- losses linked to any score vector: {coverage['with_score_vectors']}",
        (
            "- losses with scores and legal options in the same decision: "
            f"{coverage['with_scores_and_options_same_decision']}"
        ),
        (
            "- attribution-ready losses (also require explicit causal decision): "
            f"{coverage['attribution_ready_losses']}"
        ),
    ])

    lines.append("")
    lines.append("Decision contexts:")
    lines.extend(
        f"- {name}: {count}" for name, count in decisions["contexts"].items()
    )

    lines.append("")
    lines.append("Pathology/fallback signals (counts, not causal labels):")
    signals = decisions["signals_not_causal_labels"]
    if signals:
        lines.extend(f"- {name}: {count}" for name, count in signals.items())
    else:
        lines.append("- none explicitly observable")

    lines.append("")
    lines.append("Unclassifiable reasons:")
    if terminal["unclassifiable_groups"]:
        lines.extend(
            f"- {name}: {count} group(s)"
            for name, count in terminal["unclassifiable_groups"].items()
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Evidence limits:")
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines)
