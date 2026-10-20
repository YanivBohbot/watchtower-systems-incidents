"""Every process entry point named in compose.yaml and the Dockerfile imports, and Celery task names are stable."""

import importlib

import pytest


@pytest.mark.parametrize("name", ["app.main", "app.cli", "app.workers.job_queue", "app.workers.camera_process"])
def test_entry_points_import(app_env, name):
    importlib.import_module(name)


def test_celery_task_names_are_stable(app_env):
    from app.workers.job_queue import celery

    assert {"watchtower.run", "watchtower.sweep"} <= set(celery.tasks)


def test_scripts_import_existing_modules():
    """Scripts under scripts/ import app modules lazily; every one of those modules must still exist."""
    import ast
    from importlib.util import find_spec
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    imported = {
        node.module
        for script in scripts.glob("*.py")
        for node in ast.walk(ast.parse(script.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.")
    }
    assert imported
    assert [name for name in sorted(imported) if find_spec(name) is None] == []
