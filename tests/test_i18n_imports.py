"""Smoke tests for the ``unslug_city_business.i18n`` package."""

import importlib
import importlib.resources as resources


def test_i18n_imports():
    module = importlib.import_module("unslug_city_business.i18n")
    exported = {name for name in dir(module) if not name.startswith("_")}
    assert "Translator" in exported

    from unslug_city_business.i18n import Translator

    translator = Translator()
    assert translator.translate("greeting") == "Hello"

    locales_dir = resources.files("unslug_city_business.i18n").joinpath("locales")
    assert locales_dir.is_dir()
    assert locales_dir.joinpath("en.json").is_file()
