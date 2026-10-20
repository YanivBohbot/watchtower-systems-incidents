"""Every process entry point named in compose.yaml and the Dockerfile imports, and Celery task names are stable."""

import importlib

import pytest


@pytest.mark.parametrize("name", ["app.main", "app.cli", "app.workers.job_queue", "app.workers.camera_process"])
def test_entry_points_import(app_env, name):
    importlib.import_module(name)


def test_celery_task_names_are_stable(app_env):
    from app.workers.job_queue import celery

    assert {"watchtower.run", "watchtower.sweep"} <= set(celery.tasks)
