import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    pass


@cli.command()
def build():
    pass


if __name__ == "__main__":
    cli()
