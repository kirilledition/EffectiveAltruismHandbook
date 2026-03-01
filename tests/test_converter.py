from unittest.mock import patch, MagicMock
from pathlib import Path
from ea_handbook.converter import convert_to_epub, convert_to_pdf

@patch("ea_handbook.converter.subprocess.run")
@patch("ea_handbook.converter.shutil.which")
def test_convert_to_epub_sandbox(mock_which, mock_run, tmp_path):
    mock_which.return_value = "/usr/bin/pandoc"
    md_path = tmp_path / "test.md"
    out_path = tmp_path / "test.epub"

    convert_to_epub(md_path, out_path)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "--sandbox" in args

@patch("ea_handbook.converter.subprocess.run")
@patch("ea_handbook.converter.shutil.which")
def test_convert_to_pdf_sandbox(mock_which, mock_run, tmp_path):
    # Mocking which: first call is for pandoc, second is for weasyprint
    mock_which.side_effect = ["/usr/bin/pandoc", "/usr/bin/weasyprint"]
    md_path = tmp_path / "test.md"
    out_path = tmp_path / "test.pdf"

    convert_to_pdf(md_path, out_path)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "--sandbox" in args


class TestConvertToEpub:
    @patch("ea_handbook.converter.subprocess.run")
    @patch("ea_handbook.converter._require_pandoc")
    def test_convert_to_epub(self, mock_require_pandoc, mock_subprocess_run, tmp_path):
        from ea_handbook.converter import convert_to_epub

        mock_require_pandoc.return_value = "/usr/bin/pandoc"

        md_path = tmp_path / "input.md"
        out_path = tmp_path / "output.epub"

        result = convert_to_epub(md_path, out_path)

        assert result == out_path
        mock_require_pandoc.assert_called_once()
        mock_subprocess_run.assert_called_once_with(
            [
                "/usr/bin/pandoc",
                str(md_path),
                "--sandbox",
                "--from=markdown",
                "--to=epub3",
                f"--output={out_path}",
                "--toc",
                "--toc-depth=2",
                "--epub-chapter-level=2",
            ],
            check=True,
        )
        assert out_path.parent.exists()
