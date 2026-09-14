import runpy
from unittest.mock import patch


def test_python_module_entrypoint_calls_main() -> None:
    with patch("library_tracker.main.main") as mock_main:
        runpy.run_module(
            "library_tracker.__main__",
            run_name="__main__",
        )

    mock_main.assert_called_once_with()
