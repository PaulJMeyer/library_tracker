from unittest.mock import patch

from library_tracker.cli import main


def test_default_command_runs_scrape() -> None:
    result = {
        "total_entries": 0,
        "removed_count": 0,
        "removal_success": True,
        "items": [],
        "loans": [],
    }
    with (
        patch("library_tracker.cli.scrape_library", return_value=result) as scrape,
        patch("library_tracker.cli.print_scrape_result") as output,
    ):
        assert main([]) == 0
    scrape.assert_called_once_with()
    output.assert_called_once_with(result)


def test_reado_sync_routes_headless() -> None:
    with patch("library_tracker.cli._run_reado", return_value=0) as command:
        assert main(["reado-sync", "--headless"]) == 0
    command.assert_called_once_with(headless=True, wishlist_only=False)


def test_library_commands_route_arguments() -> None:
    with patch("library_tracker.cli._run_library_search", return_value=0) as command:
        assert main(["library-search", "9783406727788"]) == 0
    command.assert_called_once_with("9783406727788")

    with patch("library_tracker.cli._run_library_match", return_value=0) as command:
        assert main(["library-match", "9783257261370"]) == 0
    command.assert_called_once_with("9783257261370")


def test_expected_errors_return_one(capsys) -> None:  # type: ignore[no-untyped-def]
    from library_tracker.config import ConfigurationError

    with patch("library_tracker.cli.scrape_library", side_effect=ConfigurationError("missing")):
        assert main(["scrape"]) == 1
    assert "missing" in capsys.readouterr().out
