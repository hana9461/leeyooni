import os
import subprocess
import sys
import textwrap
from importlib import import_module
from pathlib import Path

import pytest


def _collect_dependency_info() -> str:
    lines = [
        f"python_executable={sys.executable}",
        f"python_version={sys.version.replace(os.linesep, ' ')}",
    ]
    try:
        pip_freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    except Exception as exc:  # pragma: no cover - informational branch
        lines.append(f"pip_freeze_error={exc!r}")
    else:
        lines.append("pip_freeze=\n" + pip_freeze.strip())
    return "\n".join(lines)


def test_signals_imports():
    try:
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        signals = import_module("unslug_city_business.signals")
        module_keys = list(signals.__dict__.keys())
        assert module_keys, "signals module has no attributes"
        assert "SignalPayload" in module_keys, "SignalPayload not exposed by signals module"

        SignalPayload = getattr(signals, "SignalPayload")
        payload = SignalPayload(symbol="AAPL", score=0.7)
        assert isinstance(payload, SignalPayload)

        assemble_signals = getattr(signals, "assemble_signals", None)
        if callable(assemble_signals):
            result = assemble_signals([payload])
            assert result is not None, "assemble_signals returned None"

    except Exception as exc:
        dependency_info = _collect_dependency_info()
        pytest.fail(
            textwrap.dedent(
                f"""\
                Failed to exercise unslug_city_business.signals due to: {exc!r}
                Dependency diagnostics:\n{dependency_info}
                """
            ).strip()
        )
