"""Tests for the main CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ea_handbook.main import build, cli, convert, scrape
from ea_handbook.scraper import Handbook, Post


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "cli, version" in result.output


@patch("ea_handbook.main.build_all")
@patch("ea_handbook.main.scrape_all")
def test_build_success(mock_scrape_all, mock_build_all):
    mock_scrape_all.return_value = Handbook(posts=[Post("T", "U")])
    mock_build_all.return_value = {
        "markdown": Path("dist/md"),
        "epub": Path("dist/epub"),
        "pdf": Path("dist/pdf"),
    }

    runner = CliRunner()
    result = runner.invoke(build, ["--output-dir", "custom-dist"])

    assert result.exit_code == 0
    assert "Output files:" in result.output
    assert "markdown: dist/md" in result.output
    assert "epub: dist/epub" in result.output
    assert "pdf: dist/pdf" in result.output

    mock_scrape_all.assert_called_once()
    mock_build_all.assert_called_once()


@patch("ea_handbook.main.scrape_all")
def test_build_no_posts(mock_scrape_all):
    mock_scrape_all.return_value = Handbook(posts=[])

    runner = CliRunner()
    result = runner.invoke(build)

    assert result.exit_code != 0
    assert "No posts were found. Aborting." in result.output
    mock_scrape_all.assert_called_once()


@patch("ea_handbook.main.handbook_to_markdown")
@patch("ea_handbook.main.scrape_all")
def test_scrape_success(mock_scrape_all, mock_handbook_to_markdown):
    mock_scrape_all.return_value = Handbook(posts=[Post("T", "U")])
    mock_handbook_to_markdown.return_value = Path("dist/ea-handbook.md")

    runner = CliRunner()
    result = runner.invoke(scrape, ["--output-dir", "custom-dist"])

    assert result.exit_code == 0
    assert "Markdown written to: dist/ea-handbook.md" in result.output
    mock_scrape_all.assert_called_once()
    mock_handbook_to_markdown.assert_called_once()


@patch("ea_handbook.main.scrape_all")
def test_scrape_no_posts(mock_scrape_all):
    mock_scrape_all.return_value = Handbook(posts=[])

    runner = CliRunner()
    result = runner.invoke(scrape)

    assert result.exit_code != 0
    assert "No posts were found. Aborting." in result.output
    mock_scrape_all.assert_called_once()


@patch("ea_handbook.main.convert_to_pdf")
@patch("ea_handbook.main.convert_to_epub")
def test_convert_success(mock_convert_to_epub, mock_convert_to_pdf):
    mock_convert_to_epub.return_value = Path("dist/ea-handbook.epub")
    mock_convert_to_pdf.return_value = Path("dist/ea-handbook.pdf")

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("input.md", "w") as f:
            f.write("# Hello")

        result = runner.invoke(convert, ["input.md", "--output-dir", "dist"])

        assert result.exit_code == 0
        assert "epub: dist/ea-handbook.epub" in result.output
        assert "pdf:  dist/ea-handbook.pdf" in result.output

        mock_convert_to_epub.assert_called_once()
        mock_convert_to_pdf.assert_called_once()


def test_convert_file_not_found():
    runner = CliRunner()
    result = runner.invoke(convert, ["does-not-exist.md"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
