"""\
Main CLI module for AgentHeaven.
"""

import click

from ..version import __version__
from ..utils.basic.config_utils import HEAVEN_CM
from .utils import AliasedGroup
from .repo_cli import register_repo_commands
from .config_cli import register_config_commands
from .chat_cli import register_chat_commands
from .babel_cli import register_babel_commands


@click.group(
    cls=AliasedGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    help="""\
AgentHeaven CLI

Manage AgentHeaven configurations and projects with a familiar interface inspired by conda and git.

Use --help on any command for detailed usage and options.
""",
)
@click.version_option(__version__, "-v", "--version", message="v%(version)s", help="Show the AgentHeaven version and exit.")
def cli():
    """\
    AgentHeaven CLI: manage configs and projects with ease.
    """
    pass


@cli.command(
    help="""\
Initialize or reset the global AgentHeaven configuration.

This command sets up AgentHeaven for all projects on your system, similar to 'conda init'.
Use --reset to restore default configuration values.
"""
)
@click.option("--reset", "-r", is_flag=True, help="Reset the global AgentHeaven configuration to default values.")
def setup(reset):
    """\
    Initialize or reset the global AgentHeaven configuration.
    """
    from ..utils.basic.color_utils import color_success, color_error

    try:
        if HEAVEN_CM.setup(reset=reset):
            click.echo(color_success(f"AgentHeaven globally initialized{' (reset)' if reset else ''}."))
        else:
            click.echo(color_error("Failed to initialize AgentHeaven globally."), err=True)
    except Exception as e:
        click.echo(color_error(f"Error: {e}"), err=True)


@cli.command(
    help="""\
Clear AgentHeaven cache and temporary directories.

This command removes all cached data and temporary files stored in the configured
cache_path and tmp_path directories. This can help resolve issues caused by
corrupted cache or free up disk space.
"""
)
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be deleted without actually deleting anything.")
def clean(dry_run):
    """\
    Clear AgentHeaven cache and temporary directories.
    """
    from ..utils.basic.file_utils import touch_dir, exists_dir
    from ..utils.basic.color_utils import color_success, color_error

    paths_to_clean = [
        p
        for p in [
            ("Cache", HEAVEN_CM.get("core.cache_path")),
            ("Temporary", HEAVEN_CM.get("core.tmp_path")),
        ]
        if p[1]
    ]
    for path_type, path in paths_to_clean:
        if exists_dir(path):
            if dry_run:
                click.echo(f"Would clean {path_type.lower()}: {path}")
            else:
                if touch_dir(path, clear=True):
                    click.echo(color_success(f"Cleaned {path_type.lower()}: {path}"))
                else:
                    click.echo(color_error(f"Failed to clean {path_type.lower()}: {path}"), err=True)


@cli.command(
    help="""\
Join path strings using AgentHeaven's path utility.

This command uses the hpj() function to join path components with proper
handling of special characters like ~, &, >, and forward slashes.
The result is returned as an absolute path.
"""
)
@click.argument("string", metavar="STRING", nargs=-1, required=True)
def pj(string):
    """\
    Join path strings using hpj utility.
    """
    from ..utils.basic.config_utils import hpj
    from ..utils.basic.color_utils import color_error

    try:
        # Join all arguments into a single string
        path_str = " ".join(string)
        result = hpj(path_str, abs=True)
        click.echo(result)
    except Exception as e:
        click.echo(color_error(f"Error: {e}"), err=True)


# Register commands from other modules with improved help descriptions

register_repo_commands(cli)
register_config_commands(cli, cm=HEAVEN_CM, name="ahvn")
register_chat_commands(cli)
register_babel_commands(cli)


def main():
    """\
    Entry point for the AgentHeaven CLI.
    """
    cli()
