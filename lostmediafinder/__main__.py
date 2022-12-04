"""
The CLI interface of LostMediaFinder.
"""

import click
from switch import Switch

from . import YouTubeResponse

@click.command
@click.option("--format", default="text", help="Selects which format to output to stdout.", type=click.Choice(["json", "text"]))
@click.argument("id")
@click.pass_context
def main(ctx, id: str, format: str) -> int:
    """
    Parses CLI arguments and returns the Response for the video ID <IDENT>.

    Error codes:
        - 0: All operations (seem) successful.
        - 1: A fatal error was thrown.
        - 2: One or more operations failed.
    """
    click.echo("\033[1m\033[4m\033[1;31mUsing LostMediaFinder from the command-line is unstable!\033[0m", err=True)
    click.echo("Generating report, this could take some time...", err=True)
    response = YouTubeResponse.generate(id)
    with Switch(format) as case:
        if case("json"):
            click.echo(response.json())
        elif case("text"):
            click.echo(str(response).strip())
        else:
            raise AssertionError("This should never occur!")
    errors = [service for service in response.keys if service.error]
    code = 2 if errors else 0
    ctx.exit(code)

main() # pylint: disable=no-value-for-parameter
