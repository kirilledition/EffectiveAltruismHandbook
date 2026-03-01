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
