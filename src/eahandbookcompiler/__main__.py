"""Entry point for ``python -m eahandbookcompiler``."""

import sys

from eahandbookcompiler.main import cli

if __name__ == "__main__":
    sys.exit(cli())
