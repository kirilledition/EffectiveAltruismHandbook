"""Command-line interface for the EA Handbook builder."""

from pathlib import Path

import click

from eahandbookcompiler.converter import (
    build_all,
    convert_to_epub,
    convert_to_pdf,
    handbook_to_markdown,
)
from eahandbookcompiler.scraper import REQUEST_DELAY, scrape_all


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
    default=REQUEST_DELAY,
    show_default=True,
    type=float,
    help="Seconds to wait between HTTP requests.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print progress.")
@click.option("--commit-hash", default="", help="Git commit hash to embed in metadata.")
@click.option("--repo-url", default="", help="Repository URL to embed in metadata.")
@click.option(
    "--cache-dir",
    "-c",
    default=".cache",
    show_default=True,
    type=click.Path(file_okay=False, writable=True),
    help="Directory to cache downloaded posts.",
)
@click.option(
    "--workers",
    "-w",
    default=4,
    show_default=True,
    type=click.IntRange(min=1),
    help="Number of concurrent download threads.",
)
def build(
    output_dir: str,
    delay: float,
    verbose: bool,
    commit_hash: str,
    repo_url: str,
    cache_dir: str,
    workers: int,
) -> None:
    """Scrape the handbook and build markdown, epub, and pdf.

    Args:
        output_dir: Directory where output files are written.
        delay: Seconds to wait between HTTP requests.
        verbose: Emit progress messages during scraping.
        commit_hash: Git commit hash to embed in the metadata page.
        repo_url: Repository URL to embed in the metadata page.
        cache_dir: Directory to cache downloaded posts.
        workers: Number of concurrent download threads.

    Raises:
        click.ClickException: If no posts are found after scraping.
    """
    handbook = scrape_all(session=None, delay=delay, verbose=verbose, cache_dir=Path(cache_dir), max_workers=workers)

    if not handbook.posts:
        raise click.ClickException("No posts were found. Aborting.")

    click.secho("Building markdown, EPUB, and PDF... ", fg="blue", nl=False)
    paths = build_all(handbook, Path(output_dir), commit_hash=commit_hash, repo_url=repo_url)
    click.secho("Done.", fg="green")

    click.echo("\nOutput files:")
    for format_name, path in paths.items():
        click.echo(f"  {format_name}: {path}")


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
    default=REQUEST_DELAY,
    show_default=True,
    type=float,
    help="Seconds to wait between HTTP requests.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print progress.")
@click.option("--commit-hash", default="", help="Git commit hash to embed in metadata.")
@click.option("--repo-url", default="", help="Repository URL to embed in metadata.")
@click.option(
    "--cache-dir",
    "-c",
    default=".cache",
    show_default=True,
    type=click.Path(file_okay=False, writable=True),
    help="Directory to cache downloaded posts.",
)
@click.option(
    "--workers",
    "-w",
    default=4,
    show_default=True,
    type=click.IntRange(min=1),
    help="Number of concurrent download threads.",
)
def scrape(
    output_dir: str,
    delay: float,
    verbose: bool,
    commit_hash: str,
    repo_url: str,
    cache_dir: str,
    workers: int,
) -> None:
    """Scrape the handbook and write only the combined markdown file.

    Args:
        output_dir: Directory where the markdown file is written.
        delay: Seconds to wait between HTTP requests.
        verbose: Emit progress messages during scraping.
        commit_hash: Git commit hash to embed in the metadata page.
        repo_url: Repository URL to embed in the metadata page.
        cache_dir: Directory to cache downloaded posts.
        workers: Number of concurrent download threads.

    Raises:
        click.ClickException: If no posts are found after scraping.
    """
    handbook = scrape_all(session=None, delay=delay, verbose=verbose, cache_dir=Path(cache_dir), max_workers=workers)

    if not handbook.posts:
        raise click.ClickException("No posts were found. Aborting.")

    path = handbook_to_markdown(
        handbook,
        Path(output_dir) / "eahandbookcompiler.md",
        commit_hash=commit_hash,
        repo_url=repo_url,
    )
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
    """Convert an existing markdown file to epub and pdf (requires pandoc).

    Args:
        markdown_file: Path to the source markdown file.
        output_dir: Directory where converted files are written.
    """
    markdown_path = Path(markdown_file)
    output_path = Path(output_dir)

    click.secho("Converting to EPUB... ", fg="blue", nl=False)
    epub_path = convert_to_epub(markdown_path, output_path / "eahandbookcompiler.epub")
    click.secho("Done.", fg="green")

    click.secho("Converting to PDF... ", fg="blue", nl=False)
    pdf_path = convert_to_pdf(markdown_path, output_path / "eahandbookcompiler.pdf")
    click.secho("Done.", fg="green")

    click.echo("\nOutput files:")
    click.echo(f"  epub: {epub_path}")
    click.echo(f"  pdf:  {pdf_path}")
