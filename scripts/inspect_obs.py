"""
scripts/inspect_obs.py

Run one match (random vs first), capture observations at different phases,
and print legal options in plain words.

Usage:
    python scripts/inspect_obs.py
    python scripts/inspect_obs.py --mid-game    # try to find a MAIN context obs
"""
import argparse
import hashlib
import json
import os
import platform
import random
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.env.adapter import describe_option, to_canonical


def _canonical_json_digest(value: object) -> str:
    """Hash JSON content independently of indentation and line endings."""
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _write_json(path: Path, value: object) -> None:
    """Write human-readable JSON with a trailing newline."""
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mid-game", action="store_true",
                        help="Deprecated: MAIN and multi-select observations are always captured")
    parser.add_argument("--max-games", type=int, default=12,
                        help="Maximum live random-vs-first games to search")
    parser.add_argument("--seed", type=int, default=20260904,
                        help="Seed for the built-in random agent")
    args = parser.parse_args()

    from kaggle_environments import make

    random.seed(args.seed)
    captures: dict[str, tuple[dict, dict]] = {}
    episode_results = []
    spec = None

    print("Running live random vs first matches to capture observations...")
    for game_index in range(args.max_games):
        env = make("cabt", debug=True)
        spec = env.specification
        env.run(["random", "first"])
        js = env.toJSON()
        episode_results.append({
            "game": game_index,
            "statuses": js["statuses"],
            "rewards": js["rewards"],
            "steps": len(js.get("steps", [])),
        })

        for step_index, step in enumerate(js.get("steps", [])):
            for player_index, player in enumerate(step):
                obs = player.get("observation") or {}
                location = {
                    "game": game_index,
                    "step": step_index,
                    "player": player_index,
                    "status": player.get("status"),
                }

                if obs.get("select") is None and "deck" not in captures:
                    captures["deck"] = (obs, location)

                # Only ACTIVE entries are observations on which an agent acted.
                if player.get("status") != "ACTIVE" or obs.get("select") is None:
                    continue

                select = obs["select"]
                current = obs.get("current") or {}
                players = current.get("players") or []
                your_index = current.get("yourIndex", -1)
                me = players[your_index] if 0 <= your_index < len(players) else {}

                if (select.get("context") == 0
                        and current.get("turn", 0) >= 1
                        and (me.get("active") or [])
                        and "main" not in captures):
                    captures["main"] = (obs, location)

                if select.get("maxCount", 0) > 1 and "multi" not in captures:
                    captures["multi"] = (obs, location)

                field_pokemon = []
                for player_state in players:
                    field_pokemon.extend(player_state.get("active") or [])
                    field_pokemon.extend(player_state.get("bench") or [])
                if (any(pokemon and pokemon.get("energies") for pokemon in field_pokemon)
                        and "energized" not in captures):
                    captures["energized"] = (obs, location)

        if {"deck", "main", "multi", "energized"}.issubset(captures):
            break

    missing = {"deck", "main", "multi", "energized"} - captures.keys()
    if missing:
        raise SystemExit(
            f"Could not capture {sorted(missing)} in {args.max_games} live games; "
            "no fixtures were written."
        )

    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    output_values = {
        "deck_obs_sample.json": captures["deck"][0],
        "obs_sample.json": captures["main"][0],
        "legal_actions_sample.json": captures["main"][0]["select"],
        "multi_select_obs_sample.json": captures["multi"][0],
        "energized_obs_sample.json": captures["energized"][0],
    }
    fixture_records = {}
    capture_for_file = {
        "deck_obs_sample.json": "deck",
        "obs_sample.json": "main",
        "legal_actions_sample.json": "main",
        "multi_select_obs_sample.json": "multi",
        "energized_obs_sample.json": "energized",
    }
    for filename, value in output_values.items():
        _write_json(fixtures_dir / filename, value)
        fixture_records[filename] = {
            "sha256CanonicalJson": _canonical_json_digest(value),
            "capture": capture_for_file[filename],
            **captures[capture_for_file[filename]][1],
        }

    manifest = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "scripts/inspect_obs.py",
        "source": "make('cabt').run(['random', 'first'])",
        "pythonVersion": platform.python_version(),
        "kaggleEnvironmentsVersion": version("kaggle-environments"),
        "cabtSpecificationVersion": spec.get("version") if spec else None,
        "randomAgentSeed": args.seed,
        "episodeResults": episode_results,
        "fixtures": fixture_records,
    }
    _write_json(fixtures_dir / "live_capture_manifest.json", manifest)

    best_obs = captures["main"][0]
    print(f"Captured all fixture classes in {len(episode_results)} game(s).")
    print(f"Episode results: {episode_results}")
    print(f"Saved live fixtures and provenance to {fixtures_dir}")

    if best_obs:
        print("\n--- MAIN-context observation found ---")

        # Parse with adapter
        state = to_canonical(best_obs)

        ctx_name = state.select_context or "UNKNOWN"
        print(f"\nContext: {ctx_name}")
        print(f"Select type: {state.select_type}")
        print(f"Max count: {state.select_max_count}")
        print(f"Min count: {state.select_min_count}")
        print(f"Your index: {state.your_index}")
        print(f"Turn: {state.turn}")
        print(f"Remaining overage time: {state.remaining_overage_time}")

        print(f"\n--- Legal options ({len(state.legal_options)}) ---")
        for i, opt in enumerate(state.legal_options):
            desc = describe_option(opt)
            print(f"  [{i}] {desc}")

        print(f"\n--- Your board ---")
        if state.me.active:
            a = state.me.active
            print(f"  Active: {a.name} (ID={a.card_id}) HP={a.hp}/{a.max_hp}")
        else:
            print(f"  Active: (none)")
        for i, b in enumerate(state.me.bench):
            print(f"  Bench[{i}]: {b.name} (ID={b.card_id}) HP={b.hp}/{b.max_hp}")
        print(f"  Hand count: {state.me.hand_count}")
        print(f"  Deck count: {state.me.deck_count}")
        print(f"  Prizes remaining: {state.me.prizes_remaining}")
        print(f"  Supporter played: {state.me.supporter_played}")
        print(f"  Energy attached: {state.me.energy_attached}")

        print(f"\n--- Opponent board ---")
        if state.opp.active:
            a = state.opp.active
            print(f"  Active: {a.name} (ID={a.card_id}) HP={a.hp}/{a.max_hp}")
        else:
            print(f"  Active: (none)")
        for i, b in enumerate(state.opp.bench):
            print(f"  Bench[{i}]: {b.name} (ID={b.card_id}) HP={b.hp}/{b.max_hp}")
        print(f"  Hand count: {state.opp.hand_count}")
        print(f"  Deck count: {state.opp.deck_count}")
        print(f"  Prizes remaining: {state.opp.prizes_remaining}")



if __name__ == "__main__":
    main()
