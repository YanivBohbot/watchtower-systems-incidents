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
]


@pytest.mark.parametrize("name", NEW_MODULES)
def test_new_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", OLD_MODULES)
def test_old_module_is_gone(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)
