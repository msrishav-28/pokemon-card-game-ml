"""
Runner: wrap kaggle_environments make("cabt") for local matches.
"""
from __future__ import annotations
from typing import Callable
import json


def run_match(
    agent_a,
    agent_b,
    debug: bool = True,
) -> dict:
    """
    Run a single cabt match between two agents.

    agent_a / agent_b: anything kaggle_environments accepts —
        a callable, a string like "random", "first", or a file path.

    Returns the env.toJSON() dict.
    """
    from kaggle_environments import make

    env = make("cabt", debug=debug)
    env.run([agent_a, agent_b])
    return env.toJSON()


def smoke_test() -> dict:
    """
    Official smoke test from the Addendum §6.6.
    Returns the JSON dict on success, raises on failure.
    """
    js = run_match("random", "first")
    assert js["statuses"] == ["DONE", "DONE"], (
        f"Expected [DONE, DONE], got {js['statuses']}"
    )
    assert sorted(js["rewards"]) in ([-1, 1], [0, 0]), (
        f"Unexpected rewards: {js['rewards']}"
    )
    return js
