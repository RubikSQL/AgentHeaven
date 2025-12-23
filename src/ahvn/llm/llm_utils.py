from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.debug_utils import raise_mismatch
from ..utils.basic.serialize_utils import dumps_json
from ..utils.basic.cmd_utils import cmd

_core = HEAVEN_CM.get("core", dict())
_debug = _core.get("debug", False)
_litellm_debug = bool(HEAVEN_CM.get("llm.litellm_debug", False) and _debug)

import os
from typing import Dict, Any, Union, List
from copy import deepcopy

# Set up LiteLLM environment variables
_http_proxy = _core.get("http_proxy", None)
_https_proxy = _core.get("https_proxy", None)
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
if _https_proxy:
    os.environ["HTTPS_PROXY"] = _https_proxy
if not _litellm_debug:
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["DISABLE_SCHEMA_UPDATE"] = "True"
    os.environ["LITELLM_MODE"] = "PRODUCTION"
    os.environ["LITELLM_LOG"] = "ERROR"

from ..utils.deps import deps

_litellm = None


def get_litellm():
    """Lazy load litellm with configuration."""
    global _litellm
    if _litellm is None:
        _litellm = deps.load("litellm")

        _litellm.drop_params = True
        _litellm.ssl_verify = False
        _litellm.disable_end_user_cost_tracking = True
        if not _litellm_debug:
            _litellm._logging._disable_debugging()
            _litellm.suppress_debug_info = True
            _litellm.set_verbose = False
        else:
            _litellm._turn_on_debug()
    return _litellm


def get_litellm_retryable_exceptions():
    """Get retryable exceptions from litellm."""
    litellm = get_litellm()
    return [
        litellm.Timeout,
        litellm.RateLimitError,
        litellm.ServiceUnavailableError,
        litellm.APIConnectionError,
        litellm.InternalServerError,
        litellm.APIError,
    ]


def _resolve_llm_aliases(model_alias: str = None) -> Dict[str, str]:
    """\
    Get the standardized LLM name mapping from a model alias.
    An empty string in the mapping indicates the standard model name used by the config file.
    For example, alias "dsr1" may lead to: {"": "DeepSeek-R1", "deepseek": ""deepseek-reasoner", "openrouter": "deepseek/deepseek-r1-0528"}.

    Args:
        model_alias (str, optional): The alias of the model to resolve. If None, returns all aliases.

    Returns:
        Dict[str, str]: A dictionary, with key being an LLM provider and value being the name of the model on that provider.
    """
    models_config = HEAVEN_CM.get("llm", dict()).get("models", dict())
    aliases = dict(
        sorted(
            {
                alias: {"": model} | model_config.get("identifiers", dict())
                for model, model_config in models_config.items()
                for alias in [model] + model_config.get("aliases", list())
            }.items()
        )
    )
    return aliases if not model_alias else aliases.get(model_alias, {"": model_alias})


def resolve_llm_config(preset: str = None, model: str = None, provider: str = None, **kwargs) -> Dict[str, Any]:
    """\
    Compile an LLM configuration dictionary based on the following order of priority:
    1. kwargs
    2. preset
    3. provider
    4. model
    5. global configuration
    When a parameter is specified in multiple places, the one with the highest priority is used. For example, if a parameter is specified in both `kwargs` and `preset`, the value from `kwargs` will be used.
    When missing, the preset falls back to the default preset, the model falls back to the default model, and the provider falls back to the default provider of the model.

    Args:
        preset (str, optional): The preset name to use.
        model (str, optional): The model name to use.
        provider (str, optional): The provider name to use.
        encrypt (bool, optional): Whether to encrypt the configuration. Defaults to False.
        **kwargs: Additional parameters to override in the configuration.

    Returns:
        Dict[str, Any]: The resolved LLM configuration dictionary.
    """
    llms_config = HEAVEN_CM.get("llm", dict())
    presets_config = llms_config.get("presets", dict())
    providers_config = llms_config.get("providers", dict())
    models_config = llms_config.get("models", dict())
    default_preset = llms_config.get("default_preset", "sys")
    default_provider = llms_config.get("default_provider", None)
    default_model = llms_config.get("default_model", None)
    default_args = llms_config.get("default_args", dict())
    handle_model_mismatch = llms_config.get("handle_model_mismatch", "ignore")

    args = dict()
    args.update(deepcopy(default_args))

    # Resolve preset parameters
    if not preset:
        preset = default_preset
    if preset and (preset not in presets_config):
        raise_mismatch(presets_config, got=preset, name="preset")
    preset_config = presets_config.get(preset, dict())
    args.update(preset_config.get("default_args", dict()))

    # Resolve model parameters
    if not model:
        model = preset_config.get("model", default_model)
    model_mapping = _resolve_llm_aliases(model)
    std_model = model_mapping.get("")
    if std_model and (std_model not in models_config):
        choice = raise_mismatch(models_config, got=model, name="model", mode=handle_model_mismatch)
        if (handle_model_mismatch == "warn") and choice:
            std_model = choice
    model_config = models_config.get(std_model, dict())
    args.update(model_config.get("default_args", dict()))

    # Resolve provider parameters
    if not provider:
        provider = preset_config.get("provider", None)
    if not provider:
        provider = model_config.get("default_provider", None)
    if not provider:
        model_providers = list(model_config.get("identifiers", dict()))
        provider = model_providers[0] if model_providers else default_provider
    if provider and (provider not in providers_config):
        raise_mismatch(providers_config, got=provider, name="provider")
    provider_args = deepcopy(providers_config.get(provider, dict()))
    provider_model_args = provider_args.pop("model_args", dict())
    args.update(provider_args)

    # Resolve model identifiers with specified provider
    provider_model = model_config.get("identifiers", dict()).get(provider, std_model)
    args.update(provider_model_args.get(provider_model, dict()))
    args.update({"model": provider_model})

    # Prioritize preset args
    args.update(preset_config.get("default_args", dict()))

    # Resolve custom kwargs
    args.update(deepcopy(kwargs))

    # Resolve backend
    backend = args.pop("backend", None)
    if backend and ("model" in args):
        args.update({"model": f"{backend}/{args['model']}"})

    # Resolve environment variables (e.g., <USER_NAME>)
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("<") and v.endswith(">"):
            env_var = v[1:-1]
            if env_var in os.environ:
                args[k] = os.environ[env_var]

    # Resolve environment commands (e.g., ${whoami})
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_cmd = v[2:-1]
            popen = cmd(env_cmd)
            env_val = popen.stdout.read().strip().decode("utf-8") if popen.stdout else ""
            if env_val:
                args[k] = env_val

    # Remove None values
    args = {k: v for k, v in args.items() if (v is not None)}

    return args


Message = Union[str, Dict[str, Any], Any]  # litellm.Message is Any when lazy loaded
Messages = Union[Message, List[Message]]


def format_messages(messages: Messages) -> List[Dict]:
    """\
    Unify messages for LLM in diverse formats to OpenAI message format.

    1. If messages is a single string, it is treated as a single user message.
    2. If messages is a list, each item is processed as follows:

        - If the item is a litellm.Message object, it is converted to dict using its json() method.
        - If the item is a string, it is treated as a user message.
        - If the item is a dict, it is used as is, but must contain a "role" field.
        - If the item is of any other type, a TypeError is raised.

    3. If a message dict contains "tool_calls", its "function.arguments" field is converted to a JSON string if it is not already a string.

    Args:
        messages: List of messages that can be either dict or Message objects

    Returns:
        List[dict]: List of formatted messages in OpenAI format

    Raises:
        ValueError: If messages are invalid or missing required fields
        TypeError: If an unsupported message type is encountered
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    formatted_messages = []
    litellm = get_litellm()
    for message in messages:
        if isinstance(message, str):
            formatted_messages.append({"role": "user", "content": message})
            continue
        if isinstance(message, litellm.Message):
            message = message.json()
        if isinstance(message, dict):
            if "role" not in message:
                logger.error("Message dict must contain 'role' field")
                raise ValueError("Message dict must contain 'role' field")
            if message.get("tool_calls"):
                copied_message = deepcopy(message)
                for i, tool_call in enumerate(copied_message["tool_calls"]):
                    if not isinstance(tool_call["function"]["arguments"], str):
                        tool_call["function"]["arguments"] = dumps_json(tool_call["function"]["arguments"], indent=None)
                formatted_messages.append(copied_message)
            else:
                formatted_messages.append(deepcopy(message))
            continue
        raise TypeError(f"Unsupported message type: {type(message)}")
    return formatted_messages
