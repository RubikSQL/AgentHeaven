"""\
Chat CLI for AgentHeaven.
"""

import click
import os
from typing import List, Optional
from pathlib import Path

from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)
from ..llm import LLM, gather_assistant_message
from ..cache import DiskCache
from ..utils.basic.color_utils import color_error, color_grey
from ..utils.basic.debug_utils import error_str
from ..utils.basic.config_utils import HEAVEN_CM, hpj
from ..utils.basic.serialize_utils import load_txt
import re

# Use prompt_toolkit for extensions input
from ..utils.deps import deps

prompt_toolkit_available = deps.check("prompt_toolkit")

if prompt_toolkit_available:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.shortcuts import print_formatted_text
    from prompt_toolkit.formatted_text import HTML as HTML_print
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.styles import Style

    # Define a custom style to support <ansigrey>
    custom_style = Style.from_dict(
        {
            "ansigreen": "ansigreen",
            "ansiblue": "ansiblue",
            "ansigrey": "ansibrightblack",  # bright black is usually grey
        }
    )
else:
    pt_prompt = None
    PromptSession = None
    InMemoryHistory = None
    print_formatted_text = None
    HTML_print = None
    KeyBindings = None
    Keys = None
    custom_style = None


def create_chat_session():
    """\
    Create a PromptSession for interactive chat.
    """
    if not prompt_toolkit_available:
        return None

    # Create key bindings for better UX
    bindings = KeyBindings()

    @bindings.add(Keys.ControlC)
    def _(event):
        """\
        Handle Ctrl+C gracefully.
        """
        event.app.exit(result="/quit")

    @bindings.add(Keys.ControlD)
    def _(event):
        """\
        Handle Ctrl+D (EOF) gracefully.
        """
        event.app.exit(result="/quit")

    # Create session with history and enhanced features
    session = PromptSession(
        history=InMemoryHistory(),
        key_bindings=bindings,
        multiline=False,
        wrap_lines=True,
        complete_style="column",
        mouse_support=True,
        enable_history_search=True,
    )

    return session


def get_user_input_with_session(session=None):
    """\
    Get user input using PromptSession if available, fallback to basic input.
    """
    prompt_str = ">>> "
    placeholder = "Type your message... (/exit, /quit, /bye to exit, /help for help)"
    try:
        if session:
            user_input = session.prompt(
                HTML_print("<ansiblue>>>> </ansiblue>"),
                placeholder=HTML_print("<ansigrey>" + placeholder + "</ansigrey>"),
                complete_style="column",
                style=custom_style,
            ).strip()
        elif pt_prompt:
            user_input = pt_prompt(prompt_str, placeholder=HTML_print("<ansigrey>" + placeholder + "</ansigrey>"), style=custom_style).strip()
        else:
            user_input = input(prompt_str).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return user_input


def show_help_message():
    """\
    Display help message for the session commands.
    """
    help_text = """\
<ansiblue><b>Available Commands:</b></ansiblue>
    <ansigreen>/exit, /quit, /bye, /e, /q, /b</ansigreen>   - Exit the session
    <ansigreen>/help, /h, /?, /commands</ansigreen>         - Show this help message
    <ansigreen>/save [file]</ansigreen>                     - Save current session messages to a file (default: session.json)
    <ansigreen>/load [file]</ansigreen>                     - Load session messages from a file (default: session.json)
    <ansigreen>/clear, /c</ansigreen>                       - Clear the current session context and start fresh
    <ansigreen>Ctrl+C or Ctrl+D</ansigreen>                 - Exit the session

<ansiblue><b>Tips:</b></ansiblue>
    • Use <ansigreen>Up/Down arrows</ansigreen> to navigate command history
    • Type your message and press <ansigreen>Enter</ansigreen> to send
    • Multi-line input is supported in some terminals
"""
    if prompt_toolkit_available and print_formatted_text and HTML_print:
        print_formatted_text(HTML_print(help_text), style=custom_style)
    else:
        clean_text = re.sub(r"<[^>]+>", "", help_text)
        click.echo(clean_text)


def get_user_input_loop(messages, session=None):
    """\
    Continuously get user input until an exit command is received.
    """
    while True:
        user_input = get_user_input_with_session(session)
        if user_input.lower() in ["/exit", "/quit", "/bye", "/e", "/q", "/b"]:
            return "", True
        if user_input.lower() in ["/help", "/h", "/?", "/commands"]:
            show_help_message()
            continue
        if user_input.lower() == "/s" or user_input.lower().startswith("/s ") or user_input.lower().startswith("/save "):
            path = user_input[6:].strip() if user_input.lower().startswith("/save ") else user_input[3:].strip()
            path = path or "session.json"
            from ..utils.basic.serialize_utils import save_json

            save_json(messages, path)
            continue
        if user_input.lower().startswith("/l ") or user_input.lower().startswith("/load "):
            path = user_input[6:].strip() if user_input.lower().startswith("/load ") else user_input[3:].strip()
            path = path or "session.json"
            from ..utils.basic.serialize_utils import load_json

            try:
                messages.clear()
                messages.extend(load_json(path))
            except FileNotFoundError:
                click.echo(color_error(f"File not found: {path}"), err=True)
            finally:
                continue
        if user_input.lower() == "/c" or user_input.lower() == "/clear":
            messages.clear()
            click.echo(color_grey("Session context cleared. Starting fresh."))
            continue
        if not user_input:
            continue
        return user_input, False


def register_chat_commands(cli: click.Group):
    """\
    Register chat commands with the main CLI group.
    """

    @cli.command(
        help="""\
Chat with an LLM using AgentHeaven.

Examples:
  ahvn chat "Hello, world!"
  ahvn chat --system "You are a helpful assistant" "What is Python?"
  ahvn chat -i file1.txt -i file2.txt "Summarize these files"
  ahvn chat --no-cache --no-stream "Quick question"
"""
    )
    @click.argument("prompt", required=False)
    @click.option("--prompt", help="The main prompt text. Can also be provided as a positional argument.")
    @click.option("--system", "-s", help="System prompt to set the behavior of the assistant.")
    @click.option(
        "--input-files",
        "-i",
        multiple=True,
        type=click.Path(exists=True, readable=True),
        help="Input files to read and include in the conversation. Can be used multiple times.",
    )
    @click.option("--cache/--no-cache", default=True, help="Enable or disable caching of responses. Default: enabled.")
    @click.option("--stream/--no-stream", default=True, help="Enable streaming mode for real-time response. Default: enabled.")
    @click.option("--preset", "-p", help="LLM preset to use.")
    @click.option("--model", "-m", help="LLM model to use.")
    @click.option("--provider", "-b", help="LLM provider to use.")
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed configuration and debug information.")
    def chat(
        prompt: Optional[str],
        system: Optional[str],
        input_files: List[str],
        cache: bool,
        stream: bool,
        preset: Optional[str],
        model: Optional[str],
        provider: Optional[str],
        verbose: bool,
    ):
        """\
        Chat with an LLM using AgentHeaven.
        """

        llm = LLM(
            cache=(None if not cache else DiskCache(hpj(HEAVEN_CM.get("core.cache_path", "~/.ahvn/cache/"), "chat_cli", abs=True))),
            preset=preset,
            model=model,
            provider=provider,
        )

        user_contents = list()
        if input_files:
            for file_path in input_files:
                try:
                    content = load_txt(file_path)
                    user_contents.append(f"=== Content from {file_path} Start ===\n{content.strip()}\n=== Content from {file_path} End ===")
                    if verbose:
                        click.echo(color_grey(f"Read {len(content)} characters from {file_path}"))
                except Exception as e:
                    click.echo(f"Error reading file {file_path}: {error_str(e)}", err=True)
                    click.get_current_context().exit(1)
        user_contents.append("" if prompt is None else prompt.strip())
        user_content = "\n\n".join(user_contents)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_content})

        try:
            if stream:
                for response in llm.stream(messages, include=["content"], verbose=verbose):
                    if response:
                        click.echo(response, nl=False)
                click.echo()
            else:
                response = llm.oracle(messages, include=["content"], verbose=verbose)
                if response:
                    click.echo(response)
        except KeyboardInterrupt:
            click.echo("\nChat interrupted by user.", err=True)
            click.get_current_context().exit(1)
        except Exception as e:
            click.echo(f"Error during chat: {error_str(e)}", err=True)
            click.get_current_context().exit(1)

    @cli.command(
        help="""\
Embed text or a file using AgentHeaven's LLM embedding API.

Examples:
  ahvn embed --prompt "Embed this sentence."
  ahvn embed -i file.txt
"""
    )
    @click.option(
        "--input-file",
        "-i",
        type=click.Path(exists=True, readable=True),
        help="Input file to embed. Cannot be used with --prompt or positional prompt.",
    )
    @click.argument("prompt", required=False)
    @click.option("--prompt", help="The prompt text to embed. Cannot be used with -i.")
    @click.option("--cache/--no-cache", default=True, help="Enable or disable caching of embeddings. Default: enabled.")
    @click.option("--preset", "-p", help="LLM preset to use.")
    @click.option("--model", "-m", help="LLM model to use.")
    @click.option("--provider", "-b", help="LLM provider to use.")
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed configuration and debug information.")
    def embed(
        input_file: Optional[str],
        prompt: Optional[str],
        cache: bool,
        preset: Optional[str],
        model: Optional[str],
        provider: Optional[str],
        verbose: bool,
    ):
        """\
        Embed text or a file using AgentHeaven's LLM embedding API.
        """

        if input_file and (prompt or click.get_current_context().params.get("prompt")):
            click.echo("Error: --input-file/-i and --prompt/positional prompt are mutually exclusive.", err=True)
            click.get_current_context().exit(1)

        llm = LLM(
            cache=(None if not cache else DiskCache(hpj(HEAVEN_CM.get("core.cache_path", "~/.ahvn/cache/"), "embed_cli", abs=True))),
            preset="embedder" if preset is None else preset,
            model=model,
            provider=provider,
        )

        user_content = "" if prompt is None else prompt.strip()
        if input_file:
            try:
                user_content = load_txt(input_file).strip()
                if verbose:
                    click.echo(color_grey(f"Read {len(user_content)} characters from {input_file}"))
            except Exception as e:
                click.echo(f"Error reading file {input_file}: {error_str(e)}", err=True)
                click.get_current_context().exit(1)

        try:
            click.echo(llm.embed(user_content, verbose=verbose))
        except Exception as e:
            click.echo(f"Error during embedding: {error_str(e)}", err=True)
            click.get_current_context().exit(1)

    @cli.command(
        help="""\
Start an interactive chat session with an LLM using AgentHeaven.

Examples:
  ahvn session
  ahvn session --system "You are a helpful assistant"
  ahvn session -i file1.txt -i file2.txt
  ahvn session --preset gpt4 --no-cache
"""
    )
    @click.argument("prompt", required=False)
    @click.option("--prompt", help="The main prompt text. Can also be provided as a positional argument.")
    @click.option("--system", "-s", help="System prompt to set the behavior of the assistant.")
    @click.option(
        "--input-files",
        "-i",
        multiple=True,
        type=click.Path(exists=True, readable=True),
        help="Input files to read and include in the conversation. Can be used multiple times.",
    )
    @click.option("--cache/--no-cache", default=True, help="Enable or disable caching of responses. Default: enabled.")
    @click.option("--stream/--no-stream", default=True, help="Enable streaming mode for real-time response. Default: enabled.")
    @click.option("--preset", "-p", help="LLM preset to use.")
    @click.option("--model", "-m", help="LLM model to use.")
    @click.option("--provider", "-b", help="LLM provider to use.")
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed configuration and debug information.")
    def session(
        prompt: Optional[str],
        system: Optional[str],
        input_files: List[str],
        cache: bool,
        stream: bool,
        preset: Optional[str],
        model: Optional[str],
        provider: Optional[str],
        verbose: bool,
    ):
        """\
        Start an interactive chat session with an LLM using AgentHeaven. Uses PromptSession for enhanced input.
        """

        # Initialize PromptSession if available
        chat_session = create_chat_session()

        if not prompt_toolkit_available:
            click.echo(
                color_grey(
                    "[Warning] prompt_toolkit is not installed. Falling back to standard input(). "
                    f"For best experience, run: {deps.info('prompt_toolkit')['install']}"
                )
            )

        llm = LLM(
            cache=(None if not cache else DiskCache(hpj(HEAVEN_CM.get("core.cache_path", "~/.ahvn/cache/"), "session_cli", abs=True))),
            preset=preset,
            model=model,
            provider=provider,
        )

        user_contents = list()
        if input_files:
            for file_path in input_files:
                try:
                    content = load_txt(file_path)
                    user_contents.append(f"=== Content from {file_path} Start ===\n{content.strip()}\n=== Content from {file_path} End ===")
                    if verbose:
                        click.echo(color_grey(f"Read {len(content)} characters from {file_path}"))
                except Exception as e:
                    click.echo(f"Error reading file {file_path}: {error_str(e)}", err=True)
                    click.get_current_context().exit(1)
        user_contents.append("" if prompt is None else prompt.strip())

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user_exit = False
        if prompt is None:
            user_input, user_exit = get_user_input_loop(messages=messages, session=chat_session)
            user_contents.append(user_input)
        user_content = "\n\n".join([user_content for user_content in user_contents if user_content])

        while not user_exit:
            try:
                messages.append({"role": "user", "content": user_content})
                if stream:
                    responses = list()
                    for message in llm.stream(messages, include=["message"], verbose=verbose):
                        click.echo(message.get("content", ""), nl=False)
                        responses.append(message)
                    assistant_message = gather_assistant_message(responses)
                    click.echo()
                else:
                    assistant_message = llm.oracle(messages, include=["message"], verbose=verbose)
                    click.echo(assistant_message.get("content", ""))
                messages.append(assistant_message)
                user_content, user_exit = get_user_input_loop(messages=messages, session=chat_session)
            except KeyboardInterrupt:
                break
            except Exception as e:
                click.echo(color_error(f"\n❌ Error getting response: {error_str(e)}"), err=True)
