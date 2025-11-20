"""\
Repo management commands for AgentHeaven CLI.
"""

import click
from ahvn.cli.utils import AliasedGroup


def register_repo_commands(cli):
    """\
    Register all repo management commands to the CLI.
    """

    @cli.group("repo", cls=AliasedGroup, help="Manage registered repos.")
    def repo():
        pass

    @repo.command("list", help="List all registered repos.")
    def list_repos():
        """\
        List all registered repos from global config, prettified.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.path_utils import pj
        from ahvn.utils.basic.file_utils import exists_dir
        from ahvn.utils.basic.color_utils import color_success, color_error, color_warning, color_grey

        repos = HEAVEN_CM.get("repos", level="global") or {}
        if not repos:
            click.echo(color_warning("No repos registered."))
            return
        click.echo("Registered repos:")
        maxlen = max((len(str(name)) for name in repos), default=0)
        for name, path in repos.items():
            exists = exists_dir(pj(path, ".ahvn", abs=True))
            status = color_success("✓") if exists else color_error("✗")
            name_str = name.ljust(maxlen)
            path_str = color_grey(path)
            click.echo(f"  {status} {name_str}  {path_str}")

    @repo.command("remove", help="Remove a registered repo by name.")
    @click.argument("name", required=True)
    def remove_repo(name):
        """\
        Remove a registered repo from global config.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.color_utils import color_success, color_error

        repos = HEAVEN_CM.get("repos", level="global") or {}
        if name not in repos:
            click.echo(color_error(f"Repo '{name}' not found in global config."), err=True)
            return
        del repos[name]
        HEAVEN_CM.set("repos", repos, level="global")
        click.echo(color_success(f"Removed repo '{name}' from global config."))

    @repo.command("rename", help="Rename a registered repo.")
    @click.argument("old_name", required=True)
    @click.argument("new_name", required=True)
    def rename_repo(old_name, new_name):
        """\
        Rename a registered repo in global config.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.color_utils import color_success, color_error

        repos = HEAVEN_CM.get("repos", level="global") or {}
        if old_name not in repos:
            click.echo(color_error(f"Repo '{old_name}' not found in global config."), err=True)
            return
        if new_name in repos:
            click.echo(color_error(f"Repo '{new_name}' already exists."), err=True)
            return
        repos[new_name] = repos.pop(old_name)
        HEAVEN_CM.set("repos", repos, level="global")
        click.echo(color_success(f"Renamed repo '{old_name}' to '{new_name}'."))

    @repo.command("info", help="Show details about a registered repo.")
    @click.argument("name", required=True)
    def repo_info(name):
        """\
        Show details about a registered repo.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.path_utils import pj
        from ahvn.utils.basic.file_utils import exists_dir
        from ahvn.utils.basic.color_utils import color_success, color_error
        import os
        import datetime

        repos = HEAVEN_CM.get("repos", level="global") or {}
        path = repos.get(name)
        if not path:
            click.echo(color_error(f"Repo '{name}' not found in global config."), err=True)
            return
        exists = exists_dir(pj(path, ".ahvn", abs=True))
        click.echo(f"Repo: {name}")
        click.echo(f"  Path: {path}")
        click.echo(f"  Exists: {color_success('Yes') if exists else color_error('No')}")
        if exists:
            try:
                stat = os.stat(path)
                ctime = datetime.datetime.fromtimestamp(stat.st_ctime)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                click.echo(f"  Created: {ctime.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo(f"  Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception:
                pass

    @repo.command("init", help="Initialize repo config in current directory (like git init). Optionally specify a repo name.")
    @click.argument("name", required=False)
    @click.option("--reset", "-r", is_flag=True, help="Reset local config to default values.")
    def repo_init(name, reset):
        """\
        Initialize repo config in current directory (like git init). Optionally specify a repo name.
        """
        from ahvn.utils.basic.config_utils import HEAVEN_CM
        from ahvn.utils.basic.file_utils import get_file_dir
        from ahvn.utils.basic.color_utils import color_success

        if HEAVEN_CM.init(reset=reset):
            click.echo(color_success(f"Heaven repo initialized{' (reset)' if reset else ''}."))
            repo_path = get_file_dir(HEAVEN_CM.local)
            if name:
                repos = HEAVEN_CM.get("repos", level="global") or {}
                repos[name] = repo_path
                HEAVEN_CM.set("repos", repos, level="global")
                click.echo(color_success(f"Repo '{name}' registered in global config."))
            else:
                click.echo("Unnamed repo initialized (not registered globally).")
