"""\
Top-level AgentHeaven package.

This package re-exports commonly used utilities and LLM helpers for convenience.

Note: Public API is defined primarily via subpackages. Import submodules directly
when you need fine-grained control.
"""

# Suppress deprecation warnings from third-party LLM dependencies
# These are internal warnings from litellm/llama_index that users shouldn't see
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"litellm.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"llama_index.*")

from .version import __version__

from . import utils
from .utils.klop import *
from .utils import exts


import importlib

_basic_utils_map = {
    "AhvnJsonDecoder": ".serialize_utils",
    "AhvnJsonEncoder": ".serialize_utils",
    "AutoFuncError": ".debug_utils",
    "ConfigManager": ".config_utils",
    "DatabaseError": ".debug_utils",
    "DependencyError": ".debug_utils",
    "FunctionDeserializationError": ".debug_utils",
    "HEAVEN_CM": ".config_utils",
    "LLMError": ".debug_utils",
    "NetworkProxy": ".request_utils",
    "Parallelized": ".parallel_utils",
    "ToolError": ".debug_utils",
    "append_jsonl": ".serialize_utils",
    "append_txt": ".serialize_utils",
    "asymmetric_jaccard_score": ".str_utils",
    "autotype": ".type_utils",
    "babel_compile": ".jinja_utils",
    "babel_init": ".jinja_utils",
    "browse": ".cmd_utils",
    "cmd": ".cmd_utils",
    "code2func": ".func_utils",
    "color_black": ".color_utils",
    "color_blue": ".color_utils",
    "color_cyan": ".color_utils",
    "color_debug": ".color_utils",
    "color_error": ".color_utils",
    "color_green": ".color_utils",
    "color_grey": ".color_utils",
    "color_info": ".color_utils",
    "color_info1": ".color_utils",
    "color_info2": ".color_utils",
    "color_info3": ".color_utils",
    "color_magenta": ".color_utils",
    "color_red": ".color_utils",
    "color_success": ".color_utils",
    "color_warning": ".color_utils",
    "color_white": ".color_utils",
    "color_yellow": ".color_utils",
    "copy_dir": ".file_utils",
    "copy_file": ".file_utils",
    "copy_path": ".file_utils",
    "counter_percentiles": ".misc_utils",
    "create_jinja": ".jinja_utils",
    "delete_dir": ".file_utils",
    "delete_file": ".file_utils",
    "delete_path": ".file_utils",
    "deserialize_func": ".serialize_utils",
    "deserialize_path": ".serialize_utils",
    "dflat": ".config_utils",
    "dget": ".config_utils",
    "dmerge": ".config_utils",
    "dset": ".config_utils",
    "dsetdef": ".config_utils",
    "dump_b64": ".serialize_utils",
    "dump_hex": ".serialize_utils",
    "dump_json": ".serialize_utils",
    "dump_jsonl": ".serialize_utils",
    "dump_pkl": ".serialize_utils",
    "dump_yaml": ".serialize_utils",
    "dumps_json": ".serialize_utils",
    "dumps_jsonl": ".serialize_utils",
    "dumps_yaml": ".serialize_utils",
    "dunflat": ".config_utils",
    "dunset": ".config_utils",
    "empty_dir": ".file_utils",
    "encrypt_config": ".config_utils",
    "enum_dirs": ".file_utils",
    "enum_files": ".file_utils",
    "enum_paths": ".file_utils",
    "error_str": ".debug_utils",
    "exists_dir": ".file_utils",
    "exists_file": ".file_utils",
    "exists_path": ".file_utils",
    "fmt_hash": ".hash_utils",
    "fmt_short_hash": ".hash_utils",
    "folder_diagram": ".file_utils",
    "generate_ngrams": ".str_utils",
    "get_file_basename": ".path_utils",
    "get_file_dir": ".path_utils",
    "get_file_ext": ".path_utils",
    "get_file_name": ".path_utils",
    "get_logger": ".log_utils",
    "google_download": ".request_utils",
    "has_file_ext": ".path_utils",
    "hpj": ".config_utils",
    "indent": ".str_utils",
    "is_delimiter": ".str_utils",
    "is_linux": ".cmd_utils",
    "is_macos": ".cmd_utils",
    "is_windows": ".cmd_utils",
    "iter_jsonl": ".serialize_utils",
    "iter_txt": ".serialize_utils",
    "jsonschema_type": ".type_utils",
    "lflat": ".misc_utils",
    "line_numbered": ".str_utils",
    "list_dirs": ".file_utils",
    "list_files": ".file_utils",
    "list_paths": ".file_utils",
    "load_b64": ".serialize_utils",
    "load_hex": ".serialize_utils",
    "load_jinja_env": ".jinja_utils",
    "load_json": ".serialize_utils",
    "load_jsonl": ".serialize_utils",
    "load_pkl": ".serialize_utils",
    "load_txt": ".serialize_utils",
    "load_yaml": ".serialize_utils",
    "loads_json": ".serialize_utils",
    "loads_jsonl": ".serialize_utils",
    "loads_yaml": ".serialize_utils",
    "markdown_symbol": ".str_utils",
    "md5hash": ".hash_utils",
    "no_color": ".color_utils",
    "nonempty_dir": ".file_utils",
    "normalize_text": ".str_utils",
    "omission_list": ".str_utils",
    "parse_docstring": ".func_utils",
    "parse_function_signature": ".type_utils",
    "parse_keys": ".parser_utils",
    "parse_md": ".parser_utils",
    "pj": ".path_utils",
    "print_debug": ".color_utils",
    "print_error": ".color_utils",
    "print_info": ".color_utils",
    "print_success": ".color_utils",
    "print_warning": ".color_utils",
    "raise_mismatch": ".debug_utils",
    "resolve_match_conflicts": ".str_utils",
    "save_b64": ".serialize_utils",
    "save_hex": ".serialize_utils",
    "save_json": ".serialize_utils",
    "save_jsonl": ".serialize_utils",
    "save_pkl": ".serialize_utils",
    "save_txt": ".serialize_utils",
    "save_yaml": ".serialize_utils",
    "serialize_func": ".serialize_utils",
    "serialize_path": ".serialize_utils",
    "stable_rnd": ".rnd_utils",
    "stable_rnd_vector": ".rnd_utils",
    "stable_rndint": ".rnd_utils",
    "stable_sample": ".rnd_utils",
    "stable_shuffle": ".rnd_utils",
    "stable_split": ".rnd_utils",
    "synthesize_def": ".func_utils",
    "synthesize_docstring": ".func_utils",
    "synthesize_signature": ".func_utils",
    "touch_dir": ".file_utils",
    "touch_file": ".file_utils",
    "unique": ".misc_utils",
    "value_repr": ".str_utils",
}

from .utils.basic import lazy_getattr, collect_exports, lazy_import_submodules

_AUTO_PKGS = [
    "klstore",
    "klengine",
    "cache",
    "tool",
    "llm",
    "ukf",
    "klbase",
    "adapter",
    "utils.db",
    "utils.vdb",
    "utils.mdb",
]
_ahvn_lazy_map = collect_exports(_AUTO_PKGS, __name__)

_ahvn_lazy_map.update(
    {
        # Resources
        "AhvnKLBase": ".resources.ahvn_klbase",
        "HEAVEN_KB": ".resources.ahvn_klbase",
        "_rebuild_heaven_kb": ".resources.ahvn_klbase",
        # UKF Templates
        "KnowledgeUKFT": ".ukf.templates.basic",
        "ExperienceUKFT": ".ukf.templates.basic",
        "ResourceUKFT": ".ukf.templates.basic",
        "DocumentUKFT": ".ukf.templates.basic",
        "TemplateUKFT": ".ukf.templates.basic",
        "PromptUKFT": ".ukf.templates.basic",
        "ToolUKFT": ".ukf.templates.basic",
        # Exts
        "autoi18n": ".utils.exts",
        "autotask": ".utils.exts",
        "autofunc": ".utils.exts",
        "autocode": ".utils.exts",
    }
)

_SUBMODULES = ["klstore", "cache", "tool", "llm", "ukf", "klengine", "klbase", "utils", "adapter"]


def __getattr__(name):
    if name in _basic_utils_map:
        module = importlib.import_module(_basic_utils_map[name], "ahvn.utils.basic")
        return getattr(module, name)

    mod = lazy_import_submodules(name, _SUBMODULES, __name__)
    if mod:
        return mod

    return lazy_getattr(name, _ahvn_lazy_map, __name__)
