"""QMD CLI - Entry point for command line interface.

This module provides the main CLI entry point and imports all command groups
from the modular cli subpackage.
"""

import click

from qmd.cli import check_virtual_env
from qmd.cli._config import config_group
from qmd.cli._collection import collection
from qmd.cli._context import context
from qmd.cli._server import server
from qmd.cli._index import index, update
from qmd.cli._search import search, vsearch, query
from qmd.cli._doc import ls, get, multi_get
from qmd.cli._embed import embed
from qmd.cli._system import status, check
from qmd.cli import Context


@click.group()
@click.pass_context
def cli(ctx):
    """QMD - Query Markup Documents"""
    check_virtual_env()
    ctx.obj = Context()


# Register command groups
cli.add_command(config_group)
cli.add_command(collection)
cli.add_command(context)
cli.add_command(server)
cli.add_command(index)
cli.add_command(search)
cli.add_command(ls)
cli.add_command(update)
cli.add_command(get)
cli.add_command(multi_get)
cli.add_command(status)
cli.add_command(embed)
cli.add_command(vsearch)
cli.add_command(query)
cli.add_command(check)


if __name__ == "__main__":
    cli()
