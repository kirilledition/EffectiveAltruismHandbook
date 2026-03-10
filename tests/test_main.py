"""Tests for the main CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from eahandbookcompiler.main import build, cli, convert, scrape
from eahandbookcompiler.scraper import Handbook, Post


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "cli, version" in result.output


@patch("eahandbookcompiler.main.convert_to_pdf")
@patch("eahandbookcompiler.main.convert_to_epub")
@patch("eahandbookcompiler.main.handbook_to_markdown")
@patch("eahandbookcompiler.main.scrape_all")
def test_build_success(mock_scrape_all, mock_handbook_to_markdown, mock_convert_to_epub, mock_convert_to_pdf):
    mock_scrape_all.return_value = Handbook(posts=[Post("T", "U")])
    mock_handbook_to_markdown.return_value = Path("custom-dist/eahandbookcompiler.md")
    mock_convert_to_epub.return_value = Path("custom-dist/eahandbookcompiler.epub")
    mock_convert_to_pdf.return_value = Path("custom-dist/eahandbookcompiler.pdf")

    runner = CliRunner()
    result = runner.invoke(
        build,
        [
            "--output-dir",
            "custom-dist",
            "--commit-hash",
            "abc1234",
            "--repo-url",
            "https://github.com/test/repo",
        ],
    )

    assert result.exit_code == 0
    assert "Output files:" in result.output
    assert "markdown: custom-dist/eahandbookcompiler.md" in result.output
    assert "epub: custom-dist/eahandbookcompiler.epub" in result.output
    assert "pdf: custom-dist/eahandbookcompiler.pdf" in result.output

    mock_scrape_all.assert_called_once()
    mock_handbook_to_markdown.assert_called_once()
    mock_convert_to_epub.assert_called_once()
    mock_convert_to_pdf.assert_called_once()

    _, kwargs = mock_handbook_to_markdown.call_args
    assert kwargs["commit_hash"] == "abc1234"
    assert kwargs["repo_url"] == "https://github.com/test/repo"


@patch("eahandbookcompiler.main.scrape_all")
def test_build_no_posts(mock_scrape_all):
    mock_scrape_all.return_value = Handbook(posts=[])

    runner = CliRunner()
    result = runner.invoke(build)

    assert result.exit_code != 0
    assert "No posts were found. Aborting." in result.output
    mock_scrape_all.assert_called_once()


@patch("eahandbookcompiler.main.handbook_to_markdown")
@patch("eahandbookcompiler.main.scrape_all")
def test_scrape_success(mock_scrape_all, mock_handbook_to_markdown):
    mock_scrape_all.return_value = Handbook(posts=[Post("T", "U")])
    mock_handbook_to_markdown.return_value = Path("dist/eahandbookcompiler.md")

    runner = CliRunner()
    result = runner.invoke(
        scrape,
        [
            "--output-dir",
            "custom-dist",
            "--commit-hash",
            "def5678",
            "--repo-url",
            "https://github.com/test/repo2",
        ],
    )

    assert result.exit_code == 0
    assert "Markdown written to: dist/eahandbookcompiler.md" in result.output
    mock_scrape_all.assert_called_once()
    mock_handbook_to_markdown.assert_called_once()
    _, kwargs = mock_handbook_to_markdown.call_args
    assert kwargs["commit_hash"] == "def5678"
    assert kwargs["repo_url"] == "https://github.com/test/repo2"


@patch("eahandbookcompiler.main.scrape_all")
def test_scrape_no_posts(mock_scrape_all):
    mock_scrape_all.return_value = Handbook(posts=[])

    runner = CliRunner()
    result = runner.invoke(scrape)

    assert result.exit_code != 0
    assert "No posts were found. Aborting." in result.output
    mock_scrape_all.assert_called_once()


@patch("eahandbookcompiler.main.convert_to_pdf")
@patch("eahandbookcompiler.main.convert_to_epub")
def test_convert_success(mock_convert_to_epub, mock_convert_to_pdf):
    mock_convert_to_epub.return_value = Path("dist/eahandbookcompiler.epub")
    mock_convert_to_pdf.return_value = Path("dist/eahandbookcompiler.pdf")

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("input.md").write_text("# Hello")

        result = runner.invoke(convert, ["input.md", "--output-dir", "dist"])

        assert result.exit_code == 0
        assert "epub: dist/eahandbookcompiler.epub" in result.output
        assert "pdf:  dist/eahandbookcompiler.pdf" in result.output

        mock_convert_to_epub.assert_called_once()
        mock_convert_to_pdf.assert_called_once()


def test_convert_file_not_found():
    runner = CliRunner()
    result = runner.invoke(convert, ["does-not-exist.md"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
