"""Drift gate: the mypy target must match the package's Python floor.

Defect-register ``APD-CCLIENT-007``: ``[tool.mypy] python_version`` sat at
``"3.11"`` while ``requires-python`` demanded ``>=3.12`` — the strict gate
type-checked a Python this package refuses to install on, so 3.12-only
typing constructs would have been rejected and 3.12-specific behavior
unchecked. The two values drift independently; this pins them together.
"""

import pathlib
import re
import tomllib


def _pyproject():
    root = pathlib.Path(__file__).resolve().parent.parent
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))


def test_mypy_python_version_matches_requires_python_floor():
    data = _pyproject()
    requires = data["project"]["requires-python"]
    m = re.match(r">=\s*(\d+\.\d+)", requires)
    assert m, f"unexpected requires-python format: {requires!r}"
    floor = m.group(1)
    mypy_target = data["tool"]["mypy"]["python_version"]
    assert mypy_target == floor, f"[tool.mypy] python_version ({mypy_target!r}) must equal the requires-python floor ({floor!r}); they drift independently otherwise (APD-CCLIENT-007)"
