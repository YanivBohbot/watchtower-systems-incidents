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
]
OLD_MODULES = ["app.config", "app.auth", "app.db", "app.domain.rules", "app.domain.text", "app.domain.ports"]


@pytest.mark.parametrize("name", NEW_MODULES)
def test_new_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", OLD_MODULES)
def test_old_module_is_gone(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)
