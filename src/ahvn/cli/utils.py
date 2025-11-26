"""\
CLI utilities for AgentHeaven (Click helpers).
"""

import click


class AliasedGroup(click.Group):
    """\
    Click group that supports command aliases.
    """

    def get_command(self, ctx, cmd_name):
        """\
        Resolve a command, supporting short aliases like 'ls' -> 'list'.
    """
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # Handle command aliases
        cmd_aliases = {
            "ls": "list",
            "rm": "remove",
            "rn": "rename",
            "cp": "copy",
        }
        if cmd_name in cmd_aliases:
            return click.Group.get_command(self, ctx, cmd_aliases[cmd_name])
        return None
