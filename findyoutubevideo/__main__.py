import asyncio

import click

from . import YouTubeResponse

@click.group(help="CLI tool to search for archived YouTube content")
def main():
    """
    Error codes:
        - 0: All operations (seem) successful.
        - 1: A fatal error was thrown.
        - 2: One or more operations failed.
    """

@click.command
@click.option("--format", default="text", help="Selects which format to output to stdout.", type=click.Choice(["json", "text"]))
@click.argument("id")
@click.pass_context
def youtube(ctx, id: str, format: str) -> int:
    """
    Parses CLI arguments and returns the Response for the video ID <IDENT>.
    """
    click.echo("\033[1m\033[4m\033[1;31m* The command-line interface is unstable and does not include all features.\033[0m", err=True)
    click.echo("Generating report, this could take some time...", err=True)
    response = asyncio.run(YouTubeResponse.generate(id))
    if response.status == "bad.id":
        raise ValueError("Bad video ID - does not match regex")
    if format == "json":
        click.echo(response.json())
    elif format == "text":
        click.echo(str(response).strip())
    else:
        raise AssertionError("This should never occur!")
    errors = [service for service in response.keys if service.error]
    code = 2 if errors else 0
    ctx.exit(code)

main.add_command(youtube)
main() # pylint: disable=no-value-for-parameter
