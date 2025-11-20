"""\
Babel localization commands for AgentHeaven CLI.
"""

import click


def register_babel_commands(cli):
    """\
    Register all Babel localization commands to the CLI.
    """

    @cli.group(help="Babel localization operations: init, compile, translate, reg.")
    def babel():
        """\
        Babel localization operations (init, compile, translate, reg).
        """
        pass

    @babel.command("init", help="Initialize Babel localization files.")
    @click.argument("path", required=False, default=".")
    @click.option("--langs", "-l", multiple=True, help="Target languages (e.g., -l en -l fr -l zh).")
    @click.option("--main", "-m", help="Main/source language (default: from config).")
    @click.option("--overwrite", "-o", is_flag=True, help="Clear existing translations and create new .po files.")
    @click.option("--encoding", "-e", help="Encoding for Babel config (default: from config).")
    def init_babel(path, langs, main, overwrite, encoding):
        """\
        Initialize Babel localization files.
        """
        from ahvn.utils.basic.jinja_utils import babel_init
        from ahvn.utils.basic.color_utils import color_success, color_error

        try:
            kwargs = {}
            if langs:
                kwargs["langs"] = list(langs)
            if main:
                kwargs["main"] = main
            if encoding:
                kwargs["encoding"] = encoding

            babel_init(path, overwrite=overwrite, **kwargs)
            click.echo(color_success(f"Babel initialized in '{path}'."))
        except Exception as e:
            click.echo(color_error(f"Error initializing Babel: {e}"), err=True)

    @babel.command("compile", help="Compile Babel .po files to .mo files.")
    @click.argument("path", required=False, default=".")
    @click.option("--langs", "-l", multiple=True, help="Target languages to compile (e.g., -l en -l fr).")
    @click.option("--main", "-m", help="Main/source language (default: from config).")
    def compile_babel(path, langs, main):
        """\
        Compile Babel .po files to .mo files.
        """
        from ahvn.utils.basic.jinja_utils import babel_compile
        from ahvn.utils.basic.color_utils import color_success, color_error

        try:
            kwargs = {}
            if langs:
                kwargs["langs"] = list(langs)
            if main:
                kwargs["main"] = main

            babel_compile(path, **kwargs)
            click.echo(color_success(f"Babel compiled in '{path}'."))
        except Exception as e:
            click.echo(color_error(f"Error compiling Babel: {e}"), err=True)

    @babel.command("translate", help="Translate .po files using LLM.")
    @click.argument("path", required=False, default=".")
    @click.option("--src-lang", "-s", help="Source language (default: from config).")
    @click.option("--tgt-lang", "-t", help="Target language (default: from config).")
    @click.option("--overwrite", "-o", is_flag=True, help="Overwrite existing translations.")
    @click.option("--batch-size", "-b", default=20, type=int, help="Number of entries per batch (default: 10).")
    @click.option("--hint", "-h", "hints", multiple=True, help="Translation hints (e.g., -h 'Use formal tone').")
    @click.option("--llm-preset", "-p", default="translator", help="LLM preset to use (default: translator).")
    def translate_babel(path, src_lang, tgt_lang, overwrite, batch_size, hints, llm_preset):
        """\
        Translate .po files using LLM.
        """
        from ahvn.utils.exts.autoi18n import autoi18n
        from ahvn.utils.basic.color_utils import color_error

        try:
            kwargs = {}
            if src_lang:
                kwargs["src_lang"] = src_lang
            if tgt_lang:
                kwargs["tgt_lang"] = tgt_lang
            if hints:
                kwargs["hints"] = list(hints)

            llm_args = {"preset": llm_preset}
            autoi18n(path, overwrite=overwrite, batch_size=batch_size, llm_args=llm_args, **kwargs)
        except Exception as e:
            click.echo(color_error(f"Error translating with Babel: {e}"), err=True)

    @babel.command("reg", help="Register a new string to be translated in _locales.jinja.")
    @click.argument("path", required=False, default=".")
    @click.argument("string", required=True)
    @click.option("--no-init", "-n", is_flag=True, help="Skip automatic init after registering.")
    def reg_babel(path, string, no_init):
        """\
        Register a new string to be translated in _locales.jinja.
        """
        from ahvn.utils.basic.path_utils import pj
        from ahvn.utils.basic.file_utils import touch_file, exists_file
        from ahvn.utils.basic.serialize_utils import append_txt
        from ahvn.utils.basic.jinja_utils import babel_init
        from ahvn.utils.basic.color_utils import color_success, color_error

        try:
            locales_path = pj(path, "_locales.jinja", abs=True)

            # Ensure _locales.jinja exists
            if not exists_file(locales_path):
                touch_file(locales_path, content="")

            # Append the new translatable string
            trans_string = f"{{% trans %}}{string}{{% endtrans %}}"
            append_txt(trans_string, locales_path)
            click.echo(color_success(f"Registered string in '{locales_path}'."))

            # Automatically trigger init unless --no-init is specified
            if not no_init:
                babel_init(path)
                click.echo(color_success(f"Babel initialized in '{path}'."))
        except Exception as e:
            click.echo(color_error(f"Error registering string: {e}"), err=True)
