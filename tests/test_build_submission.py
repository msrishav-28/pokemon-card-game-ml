import hashlib
import json
import zipfile

from scripts.build_submission import (
    ROOT,
    RUNTIME_SOURCE_FILES,
    WORKER_LIMIT_BYTES,
    build,
)


def test_bundle_sources_exist_and_do_not_require_vendored_native_engine():
    assert (ROOT / "submission" / "main.py").is_file()
    assert (ROOT / "submission" / "deck.csv").is_file()
    assert (ROOT / "src" / "ptcg_agent" / "env" / "adapter.py").is_file()
    assert WORKER_LIMIT_BYTES == int(197.7 * 1024 * 1024)


def test_locked_deck_has_exactly_60_integer_ids():
    values = [
        int(line)
        for line in (ROOT / "submission" / "deck.csv").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert len(values) == 60


def test_build_emits_hashed_native_free_bundle(tmp_path):
    destination, zip_path, manifest = build(tmp_path / "cabt-agent")

    assert (destination / "main.py").is_file()
    assert (destination / "src" / "ptcg_agent" / "policies" / "planned_candidate.py").is_file()
    assert zip_path.is_file()
    assert manifest["within_worker_limit"]
    assert manifest["total_uncompressed_bytes"] == sum(
        path.stat().st_size for path in destination.rglob("*") if path.is_file()
    )

    forbidden_suffixes = {".dll", ".so", ".dylib"}
    assert not any(
        path.suffix.lower() in forbidden_suffixes
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert not (destination / "refs").exists()
    assert not (destination / "src" / "ptcg_agent" / "eval").exists()
    assert not (destination / "src" / "ptcg_agent" / "search").exists()
    assert {
        path.relative_to(destination / "src")
        for path in (destination / "src").rglob("*")
        if path.is_file()
    } == set(RUNTIME_SOURCE_FILES)

    for item in manifest["files"]:
        path = destination / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]

    disk_manifest = json.loads((destination / "manifest.json").read_text())
    assert disk_manifest == manifest
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "main.py" in names
    assert "manifest.json" in names
    assert not any(name.startswith("refs/") for name in names)
