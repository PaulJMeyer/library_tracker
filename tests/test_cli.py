from unittest.mock import patch

from library_tracker.cli import main


def test_default_command_runs_scrape() -> None:
    result = {
        "total_entries": 0,
        "all_titles": [],
        "entries": [],
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


def test_scrape_with_telegram_sends_overview(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    result = {
        "total_entries": 0,
        "all_titles": [],
        "entries": [],
        "items": [],
        "loans": [],
    }
    with (
        patch("library_tracker.cli.scrape_library", return_value=result),
        patch("library_tracker.cli.print_scrape_result"),
        patch("library_tracker.cli.TelegramClient") as client_class,
    ):
        assert main(["scrape", "--telegram"]) == 0
    client_class.assert_called_once_with("123:secret", "42")
    message = client_class.return_value.send_message.call_args.args[0]
    assert "Merkliste" in message


def test_scrape_with_telegram_fails_before_scraping_without_settings(
    monkeypatch, capsys  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with patch("library_tracker.cli.scrape_library") as scrape:
        assert main(["scrape", "--telegram"]) == 1
    scrape.assert_not_called()
    assert "TELEGRAM_BOT_TOKEN is not configured" in capsys.readouterr().out


def test_telegram_test_sends_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    with patch("library_tracker.cli.TelegramClient") as client_class:
        assert main(["telegram-test"]) == 0
    client_class.return_value.send_message.assert_called_once()


def test_reado_sync_routes_headless() -> None:
    with patch("library_tracker.cli._run_reado", return_value=0) as command:
        assert main(["reado-sync", "--headless"]) == 0
    command.assert_called_once_with(headless=True, wishlist_only=False)


def test_library_commands_route_arguments() -> None:
    with patch("library_tracker.cli._run_library_search", return_value=0) as command:
        assert main(["library-search", "9780000000105"]) == 0
    command.assert_called_once_with("9780000000105")

    with patch("library_tracker.cli._run_library_match", return_value=0) as command:
        assert main(["library-match", "9780000000104"]) == 0
    command.assert_called_once_with("9780000000104")


def test_expected_errors_return_one(capsys) -> None:  # type: ignore[no-untyped-def]
    from library_tracker.config import ConfigurationError

    with patch("library_tracker.cli.scrape_library", side_effect=ConfigurationError("missing")):
        assert main(["scrape"]) == 1
    assert "missing" in capsys.readouterr().out


def test_metadata_and_report_commands_route_flags() -> None:
    with patch("library_tracker.cli._run_openlibrary_editions", return_value=0) as command:
        assert main(["openlibrary-editions", "--refresh"]) == 0
    command.assert_called_once_with(refresh=True)

    with patch("library_tracker.cli._run_match_report", return_value=0) as command:
        assert main(["match-report"]) == 0
    command.assert_called_once_with()

    with patch("library_tracker.cli._run_sync", return_value=0) as command:
        assert main(["sync", "--telegram"]) == 0
    command.assert_called_once_with(telegram=True)

    for name, func in (("match-books", "_run_match_books"), ("merkliste-add", "_run_merkliste_add"), ("merkliste-cleanup", "_run_merkliste_cleanup")):
        with patch(f"library_tracker.cli.{func}", return_value=0) as command:
            assert main([name]) == 0
        command.assert_called_once_with()

    with patch("library_tracker.cli._run_openlibrary_link_titles", return_value=0) as command:
        assert main(["openlibrary-link-titles"]) == 0
    command.assert_called_once_with()


def test_dnb_editions_routes() -> None:
    with patch("library_tracker.cli._run_dnb_editions", return_value=0) as command:
        assert main(["dnb-editions"]) == 0
    command.assert_called_once_with()
