"""Integration tests for the `unslug_city_business.metrics` module.

These tests exercise the public API of the external dependency where
possible and ensure that informative errors are raised when mandatory
runtime dependencies are missing.  The external package is optional in
this development environment, so the tests skip gracefully if the
module cannot be imported at all.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from types import ModuleType
from typing import Iterable

import pytest

MODULE_NAME = "unslug_city_business.metrics"


def _load_metrics_module() -> ModuleType:
    """Import the metrics module or skip the test if it is unavailable."""
    try:
        spec = importlib.util.find_spec(MODULE_NAME)
    except ModuleNotFoundError:
        spec = None

    if spec is None:
        pytest.skip(f"{MODULE_NAME!r} is not installed in the test environment")
    return importlib.import_module(MODULE_NAME)


def _iter_public_api(module: ModuleType) -> Iterable[str]:
    """Yield the public API exported by the module."""
    exported = getattr(module, "__all__", None)
    if exported:
        return tuple(exported)
    return tuple(name for name in dir(module) if not name.startswith("_"))


def _call_with_minimal_arguments(obj):
    """Attempt to call the callable with minimal placeholder arguments."""
    signature = inspect.signature(obj)
    positional_args = []
    keyword_args = {}

    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            if parameter.default is inspect._empty:
                positional_args.append(None)
            else:
                positional_args.append(parameter.default)
        elif parameter.kind is parameter.VAR_POSITIONAL:
            continue
        elif parameter.kind is parameter.KEYWORD_ONLY:
            if parameter.default is inspect._empty:
                keyword_args[parameter.name] = None
            else:
                keyword_args[parameter.name] = parameter.default
        elif parameter.kind is parameter.VAR_KEYWORD:
            continue

    try:
        obj(*positional_args, **keyword_args)
    except Exception as exc:  # pragma: no cover - defensive
        # Validate that the callable rejects the placeholder types using a
        # well-understood exception class instead of failing unexpectedly.
        assert isinstance(exc, (TypeError, ValueError, NotImplementedError)), exc


def test_metrics_imports():
    """Run the scripted verification steps requested by the user."""

    # Step 1: import the metrics module and enumerate its public API.
    metrics = _load_metrics_module()
    public_api = _iter_public_api(metrics)
    assert public_api, "The metrics module should expose a public API"

    # Step 2: import representative callables and call them with minimal
    # placeholder arguments to exercise their type validations.  The test
    # dynamically imports each public attribute to avoid hard-coding
    # symbol names.
    reimported_module = importlib.import_module(MODULE_NAME)
    for name in public_api:
        attribute = getattr(metrics, name)
        imported_attribute = getattr(reimported_module, name)
        assert attribute is imported_attribute

        if callable(attribute):
            _call_with_minimal_arguments(attribute)

    # Step 3: ensure the module provides helpful feedback when critical
    # dependencies are missing by simulating absent third-party modules.
    dependencies = ["numpy", "pandas", "sqlalchemy"]
    original_modules = {dep: sys.modules.get(dep) for dep in dependencies}

    for dep in dependencies:
        sys.modules.pop(dep, None)

    # Remove the cached module so the import is re-attempted with missing deps.
    sys.modules.pop(MODULE_NAME, None)
    importlib.invalidate_caches()

    try:
        with pytest.raises(ModuleNotFoundError):
            _load_metrics_module()
    finally:
        # Restore the dependency modules to avoid contaminating later tests.
        for dep, module in original_modules.items():
            if module is None:
                sys.modules.pop(dep, None)
            else:
                sys.modules[dep] = module

        # Reload the metrics module if it was previously available so the
        # test suite can continue interacting with it.
        importlib.invalidate_caches()
        try:
            spec = importlib.util.find_spec(MODULE_NAME)
        except ModuleNotFoundError:
            spec = None
        if spec is not None:
            importlib.import_module(MODULE_NAME)
