"""Agent and opponent loading without loading a second ``cabt`` engine.

The frozen buddy bundle ships a Linux native library.  The official
``kaggle-environments`` package is the engine of record and has already loaded
the correct native library for this host.  ``load_buddy`` gives the buddy's
pure-Python API module that existing library rather than importing the bundled
one.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import importlib.util
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterator


AgentCallable = Callable[..., list[int]]


@dataclass(frozen=True)
class AgentSpec:
    """Loaded callable plus stable metadata used in experiment records."""

    name: str
    source: str
    agent: AgentCallable
    deck_name: str
    deck_ids: tuple[int, ...] | None
    module: ModuleType | None = field(default=None, repr=False, compare=False)

    def decision_telemetry(self) -> dict[str, Any] | None:
        """Return opt-in details published by an in-process agent module."""
        if self.module is None:
            return None
        details = getattr(self.module, "_last_decision_telemetry", None)
        return details if isinstance(details, dict) else None

    @property
    def deck_sha256(self) -> str | None:
        if self.deck_ids is None:
            return None
        payload = "\n".join(str(card_id) for card_id in self.deck_ids).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "deck": {
                "name": self.deck_name,
                "cards": len(self.deck_ids) if self.deck_ids is not None else None,
                "sha256": self.deck_sha256,
            },
        }


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _load_module(path: Path, module_prefix: str) -> ModuleType:
    resolved = path.resolve()
    module_name = f"{module_prefix}_{hashlib.sha256(str(resolved).encode()).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create an import spec for {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _deck_tuple(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(card_id, int) and not isinstance(card_id, bool) for card_id in value):
        return None
    return tuple(value)


def load_agent_file(
    path: str | os.PathLike[str],
    *,
    name: str | None = None,
    deck_name: str = "unknown",
) -> AgentSpec:
    """Load a normal Python file exposing ``agent`` and optional ``DECK_IDS``."""

    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Agent file not found: {resolved}")
    module = _load_module(resolved, "_ptcg_eval_agent")
    agent = getattr(module, "agent", None)
    if not callable(agent):
        raise TypeError(f"Agent file does not expose callable agent(...): {resolved}")
    deck_ids = _deck_tuple(getattr(module, "DECK_IDS", None))
    return AgentSpec(
        name=name or resolved.stem,
        source=str(resolved),
        agent=agent,
        deck_name=deck_name,
        deck_ids=deck_ids,
        module=module,
    )


_BUDDY_CACHE: dict[Path, AgentSpec] = {}


def load_buddy(path: str | os.PathLike[str]) -> AgentSpec:
    """Load the untouched buddy policy against the official native library.

    Importing ``refs/buddy-lucario/cg/sim.py`` on Windows would seek a sibling
    ``cg.dll``; on Linux it would initialize a second rules library.  Both are
    wrong.  This loader temporarily aliases the official, already initialized
    ``cg.sim`` module while importing only the buddy's Python API and policy.
    """

    main_path = Path(path).resolve()
    if main_path in _BUDDY_CACHE:
        return _BUDDY_CACHE[main_path]
    if not main_path.is_file():
        raise FileNotFoundError(f"Buddy main.py not found: {main_path}")

    bundle_dir = main_path.parent
    cg_dir = bundle_dir / "cg"
    if not (cg_dir / "api.py").is_file():
        raise FileNotFoundError(f"Buddy Python API not found below: {cg_dir}")

    # Importing this module initializes exactly the native library shipped by
    # kaggle-environments for the current platform.
    official_sim = importlib.import_module("kaggle_environments.envs.cabt.cg.sim")
    official_sim.lib.AllCard.restype = ctypes.c_char_p
    official_sim.lib.AllAttack.restype = ctypes.c_char_p

    alias_names = ("cg", "cg.sim", "cg.api", "cg.utils", "cg.game")
    previous = {key: sys.modules.get(key) for key in alias_names}
    buddy_module_name = (
        f"_ptcg_eval_buddy_{hashlib.sha256(str(main_path).encode()).hexdigest()[:12]}"
    )

    try:
        package_spec = importlib.util.spec_from_file_location(
            "cg",
            cg_dir / "__init__.py",
            submodule_search_locations=[str(cg_dir)],
        )
        if package_spec is None or package_spec.loader is None:
            raise ImportError(f"Could not create package spec for {cg_dir}")
        buddy_cg = importlib.util.module_from_spec(package_spec)
        sys.modules["cg"] = buddy_cg
        sys.modules["cg.sim"] = official_sim
        package_spec.loader.exec_module(buddy_cg)

        main_spec = importlib.util.spec_from_file_location(buddy_module_name, main_path)
        if main_spec is None or main_spec.loader is None:
            raise ImportError(f"Could not create import spec for {main_path}")
        buddy_main = importlib.util.module_from_spec(main_spec)
        sys.modules[buddy_module_name] = buddy_main
        with _working_directory(bundle_dir):
            main_spec.loader.exec_module(buddy_main)
    except BaseException:
        sys.modules.pop(buddy_module_name, None)
        raise
    finally:
        for key, value in previous.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

    agent = getattr(buddy_main, "agent", None)
    if not callable(agent):
        raise TypeError(f"Buddy file does not expose callable agent(...): {main_path}")
    deck_ids = _deck_tuple(getattr(buddy_main, "my_deck", None))
    loaded = AgentSpec(
        name="buddy-lucario",
        source=str(main_path),
        agent=agent,
        deck_name="buddy-lucario-locked",
        deck_ids=deck_ids,
        module=buddy_main,
    )
    _BUDDY_CACHE[main_path] = loaded
    return loaded


def load_agent(
    value: str | os.PathLike[str],
    repo_root: str | os.PathLike[str],
    *,
    name: str = "submission",
    deck_name: str = "buddy-lucario-locked",
) -> AgentSpec:
    """Resolve an evaluated agent file through the correct local loader.

    The frozen buddy must take the same official-library reuse path whether it
    appears on the agent or opponent side of an experiment.  Ordinary files
    retain the caller-supplied metadata defaults used for the submission.
    """

    root = Path(repo_root).resolve()
    key = os.fspath(value).strip().replace("\\", "/").lower()
    buddy_main = (root / "refs" / "buddy-lucario" / "main.py").resolve()
    if key in {"buddy", "buddy-lucario", "refs/buddy-lucario/main.py"}:
        return load_buddy(buddy_main)

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if candidate == buddy_main:
        return load_buddy(candidate)
    return load_agent_file(candidate, name=name, deck_name=deck_name)


def _internal_policy(name: str, repo_root: Path) -> AgentSpec:
    """Compatibility for the pre-existing local ``baseline``/``s3`` options."""

    submission = load_agent_file(
        repo_root / "submission" / "main.py",
        name="submission-deck-source",
        deck_name="buddy-lucario-locked",
    )
    deck = list(submission.deck_ids or ())
    if len(deck) != 60:
        raise ValueError("The local internal opponent needs submission.DECK_IDS (60 cards)")

    from ptcg_agent.env.adapter import to_canonical

    if name == "baseline":
        from ptcg_agent.policies.baseline import get_action

        def policy(obs: dict, _config: dict | None = None) -> list[int]:
            if obs.get("select") is None:
                return list(deck)
            return get_action(to_canonical(obs))
    else:
        from ptcg_agent.policies.heuristic import get_action

        def policy(obs: dict, _config: dict | None = None) -> list[int]:
            if obs.get("select") is None:
                return list(deck)
            return get_action(to_canonical(obs), belief=None)

    return AgentSpec(
        name=name,
        source=f"ptcg_agent.policies.{name}",
        agent=policy,
        deck_name="buddy-lucario-locked",
        deck_ids=tuple(deck),
    )


def load_opponent(value: str, repo_root: str | os.PathLike[str]) -> AgentSpec:
    """Resolve ``random``, ``first``, or the frozen buddy to one callable.

    Existing local ``baseline``/``s3`` names and ordinary Python agent paths
    remain supported for backwards compatibility.  A path resolving to the
    frozen buddy always takes the official-library reuse path above.
    """

    root = Path(repo_root).resolve()
    key = value.strip().lower()
    if key in {"random", "first"}:
        cabt = importlib.import_module("kaggle_environments.envs.cabt.cabt")
        return AgentSpec(
            name=key,
            source=f"kaggle_environments.envs.cabt.cabt.{key}_agent",
            agent=cabt.agents[key],
            deck_name="cabt-builtin-deck",
            deck_ids=tuple(cabt.deck),
        )

    buddy_main = (root / "refs" / "buddy-lucario" / "main.py").resolve()
    if key in {"buddy", "buddy-lucario", "refs/buddy-lucario/main.py"}:
        return load_buddy(buddy_main)
    if key in {"baseline", "s3"}:
        return _internal_policy(key, root)

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if candidate == buddy_main:
        return load_buddy(candidate)
    return load_agent_file(candidate, name=candidate.stem)
