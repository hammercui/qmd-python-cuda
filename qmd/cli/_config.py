"""Config command group."""

import click

from qmd.cli import console


@click.group(name="config")
def config_group():
    """Manage configuration"""
    pass


@config_group.command(name="show")
@click.pass_obj
def config_show(ctx_obj):
    """Show current configuration"""
    console.print(f"Config path: [cyan]{ctx_obj.config.db_path}[/cyan]")

    from rich.table import Table

    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("db_path", ctx_obj.config.db_path)
    table.add_row("Collections count", str(len(ctx_obj.config.collections)))

    console.print(table)


@config_group.command(name="set")
@click.argument("key")
@click.argument("value")
@click.pass_obj
def config_set(ctx_obj, key, value):
    """Set a configuration value"""
    if key == "db_path":
        ctx_obj.config.db_path = value
        ctx_obj.config.save()
        console.print(f"[green]Set db_path to:[/green] {value}")
    else:
        console.print(f"[red]Error:[/red] Unknown key '{key}'")
