import runpy
from unittest.mock import patch

import pytest


def test_python_module_entrypoint_calls_cli() -> None:
    with (
        patch(
            "library_tracker.cli.main",
            return_value=0,
        ) as mock_main,
        pytest.raises(SystemExit) as exc_info,
    ):
        runpy.run_module(
            "library_tracker.__main__",
            run_name="__main__",
        )

    mock_main.assert_called_once_with()
    assert exc_info.value.code == 0
