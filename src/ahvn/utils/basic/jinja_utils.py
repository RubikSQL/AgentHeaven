__all__ = [
    "babel_init",
    "babel_compile",
    "load_jinja_env",
    "create_jinja",
    "get_lang_instruction",
]

from .log_utils import get_logger

logger = get_logger(__name__)
from .config_utils import HEAVEN_CM, dmerge, hpj

_encoding = HEAVEN_CM.get("core.encoding", "utf-8")
_src_lang = HEAVEN_CM.get("prompts.main", "en")
_tgt_lang = HEAVEN_CM.get("prompts.lang", "en")
_langs = HEAVEN_CM.get("prompts.langs", list())
from .path_utils import *
from .file_utils import *
from .cmd_utils import cmd
from .misc_utils import unique
from .serialize_utils import load_txt, save_txt

_babel = load_txt("& configs/default_babel.cfg")

from typing import Dict, Optional, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from jinja2 import Environment

import re


def babel_init(
    path,
    langs: Optional[List[str]] = None,
    main: Optional[str] = None,
    overwrite: bool = False,
    encoding: Optional[str] = None,
    **kwargs,
):
    """\
    Initializes Babel localization files in the specified path.

    Args:
        path (str): The root directory where 'locale' folder will be created. Templates are expected to be in this path or a subfolder.
        langs (Optional[List[str]]): A list of language codes (e.g., ['en', 'fr', 'es', 'zh']). If empty, only the POT file is extracted. Defaults to None, which will use the encoding in the config file ("prompts.langs").
        main (Optional[str]): The main language of the POT file. Defaults to None, which will use the encoding in the config file ("prompts.main").
        overwrite (bool): Clear all existing translations and create new `.po` files. Defaults to False.
        encoding (Optional[str]): The encoding to use for the Babel configuration file. Defaults to None, which will use the encoding in the config file ("prompts.encoding").
        **kwargs: Additional keyword arguments passed to `cmd` (`subprocess.Popen`).
    """
    if main is None:
        main = _src_lang
    if langs is None:
        langs = _langs
    langs = [lang for lang in langs if lang != main]

    path = hpj(path, abs=True)
    locale_path = hpj(path, "locale")
    touch_dir(locale_path)
    cfg_path = hpj(locale_path, "babel.cfg")
    if not exists_file(cfg_path):
        save_txt(_babel.format(encoding=encoding or _encoding), cfg_path)
    locales_path = hpj(path, "_locales.jinja")
    if not exists_file(locales_path):
        touch_file(locales_path, content="")
    pot_path = hpj(locale_path, "messages.pot")

    cmd(f"pybabel extract -F {cfg_path} -o {pot_path} {path}", **kwargs)
    for lang in langs:
        lang_po_path = hpj(locale_path, lang, "LC_MESSAGES", "messages.po")
        command = "init" if overwrite or (not exists_file(lang_po_path)) else "update"
        cmd(f"pybabel {command} -i {pot_path} -d {locale_path} -l {lang}", **kwargs)


def babel_compile(path, langs: Optional[List[str]] = None, main: Optional[str] = None, **kwargs):
    """\
    Compiles Babel `.po` files into `.mo` files.

    Args:
        path (str): The root directory containing the 'locale' folder.
        langs (Optional[List[str]]): A list of language codes (e.g., ['en', 'fr', 'es', 'zh']). If empty, will scan directories under locale path. Defaults to None, which will use the encoding in the config file ("prompts.langs").
        main (Optional[str]): The main language of the POT file. Defaults to None, which will use the encoding in the config file ("prompts.main").
        **kwargs: Additional keyword arguments passed to `cmd` (`subprocess.Popen`).
    """
    if main is None:
        main = _src_lang
    if langs is None:
        langs = _langs
    langs = [lang for lang in langs if lang != main]

    path = hpj(path, abs=True)
    locale_path = hpj(path, "locale")
    touch_dir(locale_path)
    cfg_path = hpj(locale_path, "babel.cfg")
    if not exists_file(cfg_path):
        logger.warning(f"Babel configuration file not found at {cfg_path}. Please run `babel_init` first.")
        return

    if not langs:
        langs = list(list_dirs(locale_path))
    for lang in langs:
        lang_po_path = hpj(locale_path, lang, "LC_MESSAGES", "messages.po")
        if not exists_file(lang_po_path):
            logger.warning(f"PO file not found for language '{lang}' at {lang_po_path}. Skipping compilation.")
            continue
        lang_mo_path = hpj(locale_path, lang, "LC_MESSAGES", "messages.mo")
        cmd(f"pybabel compile -d {locale_path} -l {lang} -f {lang_po_path} -o {lang_mo_path}", **kwargs)


import importlib.util


def _parse_loaders_and_paths(paths):
    from jinja2 import FileSystemLoader, PrefixLoader, ChoiceLoader

    if isinstance(paths, list):
        # return ChoiceLoader(list(filter(lambda x: x is not None, [_parse_loaders(p) for p in paths])))
        loaders, parsed = list(), list()
        for p in paths:
            loader, p = _parse_loaders_and_paths(p)
            if loader is not None:
                loaders.append(loader)
                parsed.extend(p)
        return ChoiceLoader(loaders), parsed
    if isinstance(paths, dict):
        loaders, parsed = dict(), list()
        for k, v in paths.items():
            loader, p = _parse_loaders_and_paths(v)
            if loader is not None:
                loaders[k] = loader
                parsed.extend(p)
        return PrefixLoader(loaders), parsed
    if isinstance(paths, str):
        path = hpj(paths, abs=True)
        loader = None if not exists_dir(path) else FileSystemLoader(path)
        return (None, list()) if loader is None else (loader, [path])
    raise ValueError(f"Invalid path type: {type(paths)}")


def load_jinja_env(
    path: Optional[Union[str, List[str], Dict[str, str]]] = None, lang: Optional[str] = None, env: "Environment" = None, **kwargs
) -> "Environment":
    """\
    Loads a Jinja2 environment with the specified path and language.

    Args:
        path (Optional[Union[str,List[str],Dict[str,str]]]): The root directory where Jinja2 templates are located.
            - If a list, it will be treated as multiple paths to search for templates (ChoiceLoader).
            - If a dictionary, it should map environment names to their respective paths (PrefixLoader).
            - If None, it will load from scan paths defined in the config.
            Defaults to None, which will use the encoding in the config file ("prompts.scan") with PrefixLoader on their subdirectories.
        lang (Optional[str]): The language code for localization. Defaults to None, which will use the encoding in the config file ("prompts.lang").
        env (Optional[Environment]): Pre-loaded Jinja2 Environment to use.
            If provided, it will be used to augment the template loading. Defaults to None.
        **kwargs: Additional keyword arguments for the Jinja2 Environment.
            By default, we use:
            - trim_blocks=True
            - lstrip_blocks=True
            - extensions including 'jinja2.ext.i18n'

    Returns:
        Environment: A Jinja2 Environment instance. Specifically, a `NativeEnvironment` is used to support native python types.
    """
    from jinja2 import ChoiceLoader, StrictUndefined
    from jinja2.nativetypes import NativeEnvironment
    from babel.support import Translations

    if lang is None:
        lang = _tgt_lang

    global_paths: Dict[str, re.Any] = dmerge(
        [
            {k: hpj(scanned, k, abs=True) for k in list_dirs(scanned)}
            for scanned in unique(list(hpj(p, abs=True) for p in HEAVEN_CM.get("prompts.scan", ["& prompts/"])))
        ]
    )
    if path is None:
        paths = [global_paths]
    elif isinstance(path, list):
        paths = [global_paths] + path
    else:
        paths = [global_paths] + [path]
    loader, paths = _parse_loaders_and_paths(paths)

    if env is not None:
        loader = ChoiceLoader([env.loader, loader])
        translations = getattr(env.exts.get("jinja2.ext.i18n", dict()), "translations", Translations())
    else:
        translations = Translations()
    upd_filters = dict() if env is None else env.filters.copy()
    upd_globals = dict() if env is None else env.globals.copy()
    upd_tests = dict() if env is None else env.tests.copy()
    upd_extensions = set() if env is None else set(env.exts.keys())
    for p in paths:
        locale_path = pj(p, "locale")
        try:
            translation = Translations.load(locale_path, lang)
            translations.merge(translation)
        except Exception as e:
            logger.error(f"Failed to load translations for language '{lang}' from {locale_path}: {e}")
        filters_path = pj(p, "filters")
        if exists_dir(filters_path):
            for filter_file in [f for f in list_files(filters_path, ext="py") if not f.startswith("_")]:
                try:
                    filter_path = pj(filters_path, filter_file)
                    filter_name = get_file_basename(filter_path, ext=False)
                    spec = importlib.util.spec_from_file_location(filter_name, filter_path)
                    filter_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(filter_module)
                    filter_func = getattr(filter_module, filter_name, None)
                    upd_filters[filter_name] = filter_func
                except Exception as e:
                    logger.error(f"Failed to load jinja filter from {filter_file}: {e}")
    upd_filters = {k: v for k, v in upd_filters.items() if callable(v)}
    upd_extensions = (
        upd_extensions
        | set(kwargs.get("extensions", []))
        | set(
            [
                "jinja2.ext.i18n",
            ]
        )
    )

    others = {k: v for k, v in kwargs.items() if k != "extensions"}
    others.setdefault("trim_blocks", True)
    others.setdefault("lstrip_blocks", True)
    upd_env = NativeEnvironment(
        loader=loader,
        extensions=list(upd_extensions),
        undefined=StrictUndefined,
        **others,
    )
    # Useful built-in filters and globals
    from ahvn.utils.basic.str_utils import value_repr, omission_list, markdown_symbol, line_numbered
    from ahvn.utils.basic.serialize_utils import dumps_json

    def tr(s):
        """Translate a string, returning empty string for empty input."""
        if not s:  # This is required since when s is empty, gettext returns system info
            return s
        trs = translations.gettext(s)
        if not trs:
            return s
        return trs

    builtin_filters = {
        "zip": zip,
        "value_repr": value_repr,
        "omission_list": omission_list,
        "markdown_symbol": markdown_symbol,
        "line_numbered": line_numbered,
        "dumps_json": dumps_json,
        "tr": tr,
    }
    builtin_tests = {
        "ellipsis": lambda x: x is ...,
        "not_ellipsis": lambda x: x is not ...,
    }
    builtin_globals = {
        "Ellipsis": ...,
        "ellipsis": ...,
    }
    upd_env.filters |= {**builtin_filters, **upd_filters}
    upd_env.tests |= {**builtin_tests, **upd_tests}
    upd_env.globals |= {**builtin_globals, **upd_globals}
    # upd_env.install_gettext_translations(translations)  # Replaced by more advanced babel support
    upd_env.install_gettext_callables(
        gettext=translations.gettext,
        ngettext=translations.ngettext,
        newstyle=True,
    )
    return upd_env


def create_jinja(
    path: str,
    entry: str = "default.jinja",
    content: str = "",
    autojinja: bool = False,
    autoi18n: bool = False,
) -> str:
    """\
    Creates a Jinja2 template from the specified path and entry, and renders it with the provided keyword arguments.

    Args:
        path (str): The root directory where Jinja2 templates are located.
        entry (str): The template filename to render. Defaults to "default.jinja".
        content (str): The content of the template to be created if it does not exist. Defaults to an empty string.
        autojinja (bool): Whether to automatically convert "content" to a standard Jinja2 template. Defaults to False.
            If True, it will call `autojinja` with `jinja` as the LLM preset after creating the template.
        autoi18n (bool): Whether to automatically initialize Babel localization files. Defaults to False.
            If True, it will call `autoi18n` with `translator` as the LLM preset after creating the template.

    Returns:
        str: The path to the created Jinja2 template.
    """
    path = hpj(path, abs=True)
    entry_path = hpj(path, entry)
    touch_file(entry_path, content=content)

    babel_init(path, overwrite=False)
    if autojinja:
        pass  # TODO
    if autoi18n:
        # TODO: fix potential circular import in the future
        from ahvn.utils.exts.autoi18n import autoi18n

        autoi18n(path, llm_preset="translator")
    babel_compile(path)
    return entry_path


def get_lang_instruction(lang: str) -> str:
    """\
    Get instruction string for the specified language.

    Args:
        lang (str): Language code (e.g., 'en', 'fr', 'es', 'zh').

    Returns:
        str: Instruction string for the specified language.
    """
    instructions = {
        "en": "Output in English.",
        "zh": "Output in Simplified Chinese.",
        # TODO: add more languages
    }
    return instructions.get(lang, f"Output in {lang}.")
