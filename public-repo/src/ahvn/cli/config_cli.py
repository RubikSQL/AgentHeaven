"""\
Configuration management commands for AgentHeaven CLI.
"""

import click


def register_config_commands(cli):
    """\
    Register all configuration management commands to the CLI.
    """

    @cli.group(help="Config operations: show, set, unset configuration values.")
    def config():
        """\
        Config operations (show, set, unset).
        """
        pass

    @config.command("show", help="Show config values for a given level.")
    @click.option("--global", "-g", "is_global", is_flag=True, help="Show global config (default: local)")
    @click.option("--system", "-s", "is_system", is_flag=True, help="Show system config")
    def show_config(is_global, is_system):
        """\
        Show config values.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.serialize_utils import dumps_yaml

        if is_system:
            cfg = HEAVEN_CM.get(None, level="system")
            click.echo(dumps_yaml(cfg))
        elif is_global:
            merged = HEAVEN_CM.get(None, level="global")
            click.echo(dumps_yaml(merged))
        else:
            cfg = HEAVEN_CM.get(None, level="local")
            click.echo(dumps_yaml(cfg))

    @config.command("set", help="Set a config value. Example: ahvn config set [--global] [--json] KEY VALUE")
    @click.argument("key", metavar="KEY", nargs=1, required=True)
    @click.argument("value", metavar="VALUE", nargs=1, required=True)
    @click.option("--global", "-g", "is_global", is_flag=True, help="Set global config (default: local)")
    @click.option("--json", "-j", "is_json", is_flag=True, help="Parse value as JSON")
    def set_config(key, value, is_global, is_json):
        """\
        Set a config value. Usage: ahvn config set [--global] [--json] key value
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.type_utils import autotype

        if is_json:
            from ahvn.utils.basic.serialize_utils import loads_json

            try:
                value = loads_json(value)
            except Exception as e:
                from ahvn.utils.basic.color_utils import color_error

                click.echo(color_error(f"Invalid JSON value: {e}"), err=True)
                return
        level = "global" if is_global else "local"
        value = autotype(value)
        changed = HEAVEN_CM.set(key, value, level=level)
        if not changed:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to set {key}."), err=True)

    @config.command("unset", help="Unset a config value. Example: ahvn config unset [--global] KEY")
    @click.argument("key", metavar="KEY", nargs=1, required=True)
    @click.option("--global", "-g", "is_global", is_flag=True, help="Unset global config (default: local)")
    def unset_config(key, is_global):
        """\
        Unset a config value. Usage: ahvn config unset [--global] key
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM

        level = "global" if is_global else "local"
        changed = HEAVEN_CM.unset(key, level=level)
        if not changed:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to unset {key}."), err=True)

    @config.command("edit", help="Edit config file for a given level in your editor.")
    @click.option("--global", "-g", "is_global", is_flag=True, help="Edit global config (default: local)")
    @click.option("--system", "-s", "is_system", is_flag=True, help="Edit system config")
    def edit_config(is_global, is_system):
        """\
        Edit config file in your editor.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        import os
        import sys
        import subprocess

        # Determine config level
        if is_system:
            level = "system"
        elif is_global:
            level = "global"
        else:
            level = "local"

        cfg_path = HEAVEN_CM.config_path(level=level)
        if not cfg_path or not os.path.exists(cfg_path):
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"No config file found for level '{level}'."), err=True)
            sys.exit(1)

        editor = os.environ.get("EDITOR", "vim")
        try:
            subprocess.run([editor, cfg_path])
        except Exception as e:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to open editor: {e}"), err=True)
            sys.exit(1)

    @config.command("open", help="Open config file for a given level in your file explorer or editor.")
    @click.option("--global", "-g", "is_global", is_flag=True, help="Open global config (default: local)")
    @click.option("--system", "-s", "is_system", is_flag=True, help="Open system config")
    def open_config(is_global, is_system):
        """\
        Open config file in your file explorer or editor.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.cmd_utils import browse
        import os
        import sys

        # Determine config level
        if is_system:
            level = "system"
        elif is_global:
            level = "global"
        else:
            level = "local"

        cfg_path = HEAVEN_CM.config_path(level=level)
        if not cfg_path or not os.path.exists(cfg_path):
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"No config file found for level '{level}'."), err=True)
            sys.exit(1)

        try:
            browse(cfg_path)
        except Exception as e:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to open config file: {e}"), err=True)
            sys.exit(1)
