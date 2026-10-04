"""Build a small, self-contained cabt agent bundle without native libraries.

The bundle intentionally relies on ``kaggle-environments`` for cabt.  It does
not include the buddy reference implementation, a rules clone, or any native
library.  Run the emitted ``main.py`` directly with ``env.run`` to verify it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "cabt-agent"
WORKER_LIMIT_BYTES = int(197.7 * 1024 * 1024)
RUNTIME_SOURCE_FILES = (
    Path("ptcg_agent/__init__.py"),
    Path("ptcg_agent/env/__init__.py"),
    Path("ptcg_agent/env/adapter.py"),
    Path("ptcg_agent/env/types.py"),
    Path("ptcg_agent/policies/__init__.py"),
    Path("ptcg_agent/policies/planned_candidate.py"),
)


def _copy_runtime_source(destination: Path) -> None:
    """Copy only modules imported by the frozen player."""
    source_root = ROOT / "src"
    destination_root = destination / "src"
    for relative_path in RUNTIME_SOURCE_FILES:
        target = destination_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative_path, target)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(destination: Path) -> tuple[Path, Path, dict]:
    destination = destination.resolve()
    expected_parent = (ROOT / "dist").resolve()
    if destination.exists():
        # Recursive replacement is allowed only for the script's dedicated
        # workspace dist children. Tests may use a fresh temporary path, but
        # an existing arbitrary path is never removed.
        if destination.parent != expected_parent:
            raise ValueError(
                f"refusing to replace existing path outside {expected_parent}"
            )
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    shutil.copy2(ROOT / "submission" / "main.py", destination / "main.py")
    shutil.copy2(ROOT / "submission" / "deck.csv", destination / "deck.csv")
    shutil.copy2(ROOT / "submission" / "deck.json", destination / "deck.json")
    _copy_runtime_source(destination)

    # The planned policy's optional metadata source is official, unchanged,
    # and small.  Including it keeps the bundle deterministic without copying
    # the buddy's Python/native implementation.
    official_csv = ROOT / "data" / "official" / "EN Card Data.csv"
    if official_csv.exists():
        csv_target = destination / "data" / "official" / official_csv.name
        csv_target.parent.mkdir(parents=True)
        shutil.copy2(official_csv, csv_target)

    files = []
    total_bytes = 0
    for path in sorted(p for p in destination.rglob("*") if p.is_file()):
        size = path.stat().st_size
        total_bytes += size
        files.append(
            {
                "path": path.relative_to(destination).as_posix(),
                "bytes": size,
                "sha256": _sha256(path),
            }
        )

    manifest = {
        "schema_version": 1,
        "engine_dependency": "kaggle-environments==1.32.7",
        "native_libraries_included": False,
        "files": files,
        "payload_uncompressed_bytes": total_bytes,
        "total_uncompressed_bytes": 0,
        "worker_limit_bytes": WORKER_LIMIT_BYTES,
        "within_worker_limit": True,
    }

    manifest_path = destination / "manifest.json"
    # The manifest does not hash itself, but its bytes do count toward the
    # worker limit. Iterate because adding the total can change digit count.
    while True:
        payload = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        inclusive_total = total_bytes + len(payload)
        within_limit = inclusive_total <= WORKER_LIMIT_BYTES
        if (
            manifest["total_uncompressed_bytes"] == inclusive_total
            and manifest["within_worker_limit"] == within_limit
        ):
            break
        manifest["total_uncompressed_bytes"] = inclusive_total
        manifest["within_worker_limit"] = within_limit
    if not manifest["within_worker_limit"]:
        raise RuntimeError("bundle exceeds the 197.7 MiB worker limit")
    manifest_path.write_bytes(payload)

    zip_path = destination.with_suffix(".zip")
    if zip_path.exists():
        if zip_path.parent != expected_parent:
            raise ValueError(
                f"refusing to replace existing archive outside {expected_parent}"
            )
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in destination.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(destination).as_posix())

    return destination, zip_path, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"bundle directory (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    destination, zip_path, manifest = build(args.out)
    print(f"bundle: {destination}")
    print(f"zip: {zip_path}")
    print(f"uncompressed bytes: {manifest['total_uncompressed_bytes']}")
    print(f"within 197.7 MiB limit: {manifest['within_worker_limit']}")


if __name__ == "__main__":
    main()
