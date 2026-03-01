"""Command-line interface for the EA Handbook builder."""

from pathlib import Path

import click

from ea_handbook.converter import (
    build_all,
    convert_to_epub,
    convert_to_pdf,
    handbook_to_markdown,
)
from ea_handbook.scraper import scrape_all


@click.group()
@click.version_option()
def cli() -> None:
    """Build the EA Handbook ebook from forum.effectivealtruism.org/handbook."""


@cli.command()
@click.option(
    "--output-dir",
    "-o",
    default="dist",
    show_default=True,
    type=click.Path(file_okay=False, writable=True),
    help="Directory where output files are written.",
)
@click.option(
    "--delay",
    "-d",
    default=1.0,
    show_default=True,
    type=float,
    help="Seconds to wait between HTTP requests.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print progress.")
def build(output_dir: str, delay: float, verbose: bool) -> None:
    """Scrape the handbook and build markdown, epub, and pdf."""
    handbook = scrape_all(delay=delay, verbose=verbose)

    if not handbook.posts:
        raise click.ClickException("No posts were found. Aborting.")

    paths = build_all(handbook, Path(output_dir))

    click.echo("Output files:")
    for fmt, path in paths.items():
        click.echo(f"  {fmt}: {path}")


@cli.command()
@click.option(
    "--output-dir",
    "-o",
    default="dist",
    show_default=True,
    type=click.Path(file_okay=False, writable=True),
    help="Directory where output files are written.",
)
@click.option(
    "--delay",
    "-d",
    default=1.0,
    show_default=True,
    type=float,
    help="Seconds to wait between HTTP requests.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print progress.")
def scrape(output_dir: str, delay: float, verbose: bool) -> None:
    """Scrape the handbook and write only the combined markdown file."""
    handbook = scrape_all(delay=delay, verbose=verbose)

    if not handbook.posts:
        raise click.ClickException("No posts were found. Aborting.")

    path = handbook_to_markdown(handbook, Path(output_dir) / "ea-handbook.md")
    click.echo(f"Markdown written to: {path}")


@cli.command()
@click.argument("markdown_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output-dir",
    "-o",
    default="dist",
    show_default=True,
    type=click.Path(file_okay=False, writable=True),
    help="Directory where output files are written.",
)
def convert(markdown_file: str, output_dir: str) -> None:
    """Convert an existing markdown file to epub and pdf (requires pandoc)."""
    md = Path(markdown_file)
    out = Path(output_dir)

    epub_path = convert_to_epub(md, out / "ea-handbook.epub")
    pdf_path = convert_to_pdf(md, out / "ea-handbook.pdf")

    click.echo(f"epub: {epub_path}")
    click.echo(f"pdf:  {pdf_path}")
