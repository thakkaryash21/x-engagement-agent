"""Plan 4 — PathResolver safety guards + RunLauncher validation/state."""

from __future__ import annotations

import pytest

from dashboard.run_launcher import RunLauncher


# --- PathResolver ------------------------------------------------------------

def test_data_path_blocks_traversal(temp_store):
    with pytest.raises(ValueError):
        temp_store.paths.data_path("..", "..", "secret")


def test_config_path_blocks_traversal(temp_store):
    with pytest.raises(ValueError):
        temp_store.paths.config_path("../AGENTS.md")


def test_safe_md_path_rejects_non_editable_area(temp_store):
    with pytest.raises(ValueError):
        temp_store.paths.read_md_file("AGENTS.md")


def test_safe_md_path_rejects_non_md(temp_store):
    with pytest.raises(ValueError):
        temp_store.paths.read_md_file("data/personas/founder-template.txt")


def test_list_personas(temp_store):
    assert temp_store.paths.list_personas() == ["founder-template", "shubham"]


def test_write_md_file_bumps_last_updated(temp_store):
    rel = "data/personas/founder-template.md"
    result = temp_store.paths.write_md_file(rel, "# persona\nlast_updated: 2000-01-01\nbody\n")
    text = temp_store.paths.read_md_file(rel)
    assert f"last_updated: {result['last_updated']}" in text
    assert "2000-01-01" not in text


# --- RunLauncher -------------------------------------------------------------

def test_launch_run_rejects_unknown_mode(temp_store):
    with pytest.raises(ValueError):
        temp_store.runner.launch_run("nonsense")


def test_launch_run_rejects_tagging_outside_scroll(temp_store):
    with pytest.raises(ValueError):
        temp_store.runner.launch_run("compose", tagging=True)


def test_read_run_state_default_when_absent(temp_store):
    # temp repo has no run-state.json
    assert temp_store.runner.read_run_state() == {"last_launch": None}


def test_run_launcher_is_constructed_from_paths(temp_store):
    launcher = RunLauncher(temp_store.paths)
    assert launcher.run_state_path().name == "run-state.json"
