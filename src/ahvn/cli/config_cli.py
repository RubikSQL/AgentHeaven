"""\
Configuration management commands for AgentHeaven CLI.
"""

import click
from ahvn.cli.utils import AliasedGroup

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ahvn.utils.basic.config_utils import ConfigManager


def register_config_commands(cli, cm: Optional["ConfigManager"] = None, name: str = "ahvn"):
    """\
    Register all configuration management commands to the CLI.
    """
    if cm is None:
        from ahvn.utils.basic.config_utils import HEAVEN_CM

        cm = HEAVEN_CM

    @cli.group("config", cls=AliasedGroup, help="Config operations: show, set, unset configuration values.")
    def config():
        """\
        Config operations (show, set, unset).
        """
        pass

    @config.command("show", help="Show config values for a given level.")
    @click.argument("key", metavar="KEY", nargs=1, required=False, default=None)
    @click.option("--global", "-g", "is_global", is_flag=True, help="Show global config (default: local)")
    @click.option("--system", "-s", "is_system", is_flag=True, help="Show system config")
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def show_config(key, is_global, is_system, cwd):
        """\
        Show config values.
        """
        from ahvn.utils.basic.serialize_utils import dumps_yaml
        from ahvn.utils.basic.config_utils import dget

        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

        if is_system:
            cfg = cm.get(None, level="system")
        elif is_global:
            cfg = cm.get(None, level="global")
        else:
            cfg = cm.get(None, level="local")

        # If key specified, show subconfig for that key path
        if key:
            subcfg = dget(cfg, key)
            click.echo(dumps_yaml(subcfg))
        else:
            click.echo(dumps_yaml(cfg))

    @config.command("set", help=f"Set a config value. Example: {name} config set [--global] [--json] KEY VALUE")
    @click.argument("key", metavar="KEY", nargs=1, required=True)
    @click.argument("value", metavar="VALUE", nargs=1, required=True)
    @click.option("--global", "-g", "is_global", is_flag=True, help="Set global config (default: local)")
    @click.option("--json", "-j", "is_json", is_flag=True, help="Parse value as JSON")
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def set_config(key, value, is_global, is_json, cwd):
        """\
        Set a config value. Usage: {name} config set [--global] [--json] key value
        """
        from ahvn.utils.basic.type_utils import autotype

        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

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
        changed = cm.set(key, value, level=level)
        if not changed:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to set {key}."), err=True)

    @config.command("unset", help=f"Unset a config value. Example: {name} config unset [--global] KEY")
    @click.argument("key", metavar="KEY", nargs=1, required=True)
    @click.option("--global", "-g", "is_global", is_flag=True, help="Unset global config (default: local)")
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def unset_config(key, is_global, cwd):
        """\
        Unset a config value. Usage: {name} config unset [--global] key
        """
        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

        level = "global" if is_global else "local"
        changed = cm.unset(key, level=level)
        if not changed:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to unset {key}."), err=True)

    @config.command("copy", help=f"Copy a config value to local config. Example: {name} config copy [-g] [KEY]")
    @click.argument("key", metavar="KEY", nargs=1, required=False, default=None)
    @click.option("--global", "-g", "from_default", is_flag=True, help="Copy from system (default) config instead of global config")
    @click.option("--yes", "-y", "skip_confirm", is_flag=True, help="Skip confirmation prompt when copying all configs")
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def copy_config(key, from_default, skip_confirm, cwd):
        """\
        Copy a config value from global or system config to local config.
        By default, copies from global config. Use -g to copy from system (default) config.
        If no key is specified, copies all configs (requires confirmation).
        """
        from ahvn.utils.basic.config_utils import dget

        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

        source_level = "system" if from_default else "global"
        source_config = cm.get(None, level=source_level)

        # If no key specified, copy all configs
        if not key:
            if not skip_confirm:
                from ahvn.utils.basic.color_utils import color_warning

                click.echo(color_warning(f"This will replace ALL local config with {source_level} config."))
                if not click.confirm("Are you sure you want to continue?"):
                    click.echo("Aborted.")
                    return
            # Replace entire local config with source config
            cm._local_config = dict(source_config)
            cm.save(level="local")
            from ahvn.utils.basic.color_utils import color_success

            click.echo(color_success(f"Successfully copied all configs from {source_level} to local."))
            return

        value = dget(source_config, key)
        if value is None:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Key '{key}' not found in {source_level} config."), err=True)
            return
        changed = cm.set(key, value, level="local")
        if not changed:
            from ahvn.utils.basic.color_utils import color_error

            click.echo(color_error(f"Failed to copy {key} to local config."), err=True)

    @config.command("edit", help="Edit config file for a given level in your editor.")
    @click.option("--global", "-g", "is_global", is_flag=True, help="Edit global config (default: local)")
    @click.option("--system", "-s", "is_system", is_flag=True, help="Edit system config")
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def edit_config(is_global, is_system, cwd):
        """\
        Edit config file in your default editor.
        """
        import os
        import sys
        import subprocess

        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

        # Determine config level
        if is_system:
            level = "system"
        elif is_global:
            level = "global"
        else:
            level = "local"

        cfg_path = cm.config_path(level=level)
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
    @click.option(
        "--cwd", "-c", "cwd", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True), help="Set working directory for local config"
    )
    def open_config(is_global, is_system, cwd):
        """\
        Open config file with system open.
        """
        from ahvn.utils.basic.cmd_utils import browse
        import os
        import sys

        # Set cwd if provided
        if cwd:
            cm.set_cwd(cwd)

        # Determine config level
        if is_system:
            level = "system"
        elif is_global:
            level = "global"
        else:
            level = "local"

        cfg_path = cm.config_path(level=level)
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
