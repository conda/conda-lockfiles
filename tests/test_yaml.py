from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

import pytest

from conda_lockfiles import _yaml as yaml
from conda_lockfiles.load_yaml import load_yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("build_number", [0, 7])
@pytest.mark.filterwarnings("error::PendingDeprecationWarning")
def test_yaml_round_trip(tmp_path: Path, build_number: int) -> None:
    data = {
        "build_number": build_number,
        "version": "1.0",
        "date": "2026-09-23",
        "enabled": "true",
        "dependencies": ["python >=3.10", "numpy"],
    }
    text = yaml.dumps(data)
    assert yaml.loads(text) == data
    assert yaml.load(StringIO(text)) == data

    path = tmp_path / "lock.yaml"
    path.write_text(text)
    assert load_yaml(path) == data
