"""The package layout documented in docs/GUIDE.md: new modules import, old module paths are gone."""

import importlib

import pytest

NEW_MODULES = [
    "app.core.config",
    "app.core.security",
    "app.database.models",
    "app.database.session",
    "app.domain.dwell_rule",
    "app.domain.text_chunking",
    "app.domain.interfaces",
    "app.integrations.local_storage",
    "app.integrations.yolo_detector",
    "app.integrations.qdrant_index",
    "app.integrations.mcp_tickets",
    "app.integrations.looped_video_source",
    "app.integrations.live_hub",
    "app.services.video_analysis",
    "app.services.knowledge_base",
    "app.services.camera_monitor",
    "app.services.frame_annotation",
    "app.services.site_seeding",
    "app.investigation.investigator",
    "app.investigation.workflow",
    "app.investigation.schemas",
    "app.investigation.checkpoints",
    "app.workers.job_queue",
    "app.workers.job_handlers",
    "app.workers.camera_process",
    "app.api.application",
    "app.api.dependencies",
    "app.api.schemas",
    "app.api.uploads",
    "app.api.routes.health",
    "app.api.routes.auth",
    "app.api.routes.videos",
    "app.api.routes.jobs",
    "app.api.routes.documents",
    "app.api.routes.incidents",
    "app.api.routes.investigations",
    "app.api.routes.cameras",
    "app.api.routes.alerts",
    "app.api.routes.live_events",
]
OLD_MODULES = [
    "app.config",
    "app.auth",
    "app.db",
    "app.domain.rules",
    "app.domain.text",
    "app.domain.ports",
    "app.adapters",
    "app.agent",
    "app.services.video",
    "app.services.knowledge",
    "app.services.live",
    "app.services.annotate",
    "app.services.sites",
    "app.tasks",
    "app.runtime",
    "app.live",
]


@pytest.mark.parametrize("name", NEW_MODULES)
def test_new_module_imports(app_env, name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", OLD_MODULES)
def test_old_module_is_gone(app_env, name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


# Which application packages each package may import (docs/GUIDE.md, section 0).
ALLOWED_IMPORTS = {
    "core": set(),
    "database": set(),
    "domain": set(),
    "integrations": set(),
    "services": {"database", "domain", "integrations"},
    "investigation": {"database", "domain", "integrations"},
    "workers": {"core", "database", "domain", "integrations", "investigation", "services"},
    "api": {"core", "database", "domain", "integrations", "workers"},
}


@pytest.mark.parametrize("package", sorted(ALLOWED_IMPORTS))
def test_package_imports_follow_the_layers(package):
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app" / package
    imported = {
        node.module.split(".")[1]
        for path in root.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.")
    }
    assert imported - {package} <= ALLOWED_IMPORTS[package]
