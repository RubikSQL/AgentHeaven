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
from ..utils.basic.color_utils import color_error, color_grey, color_warning
from ..utils.basic.debug_utils import error_str
from ..utils.basic.config_utils import HEAVEN_CM, hpj
from ..utils.basic.serialize_utils import load_txt
import re
import html

# Use prompt_toolkit for extensions input
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.formatted_text import HTML as HTML_print
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter


# Define a custom style to support <ansigrey>
custom_style = Style.from_dict(
    {
        "ansigreen": "ansigreen",
        "ansiblue": "ansiblue",
        "ansigrey": "ansibrightblack",  # bright black is usually grey
    }
)


def create_chat_session():
    """\
    Create a PromptSession for interactive chat.
    """
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

    # Command completer
    commands = ["/exit", "/quit", "/bye", "/help", "/save", "/load", "/clear", "/regen", "/back"]
    command_completer = WordCompleter(commands, ignore_case=True)

    # Create session with history and enhanced features
    session = PromptSession(
        history=InMemoryHistory(),
        key_bindings=bindings,
        multiline=False,
        wrap_lines=True,
        complete_style="column",
        mouse_support=True,
        enable_history_search=True,
        completer=command_completer,
        complete_while_typing=True,
    )

    return session


def get_user_input_with_session(session=None):
    """\
    Get user input using PromptSession if available, fallback to basic input.
    """
    prompt_str = ">>> "
    placeholder = "Type your message... (/bye or /exit to exit, /help for more commands)"
    try:
        if session:
            user_input = session.prompt(
                HTML_print("<ansiblue>>>> </ansiblue>"),
                placeholder=HTML_print("<ansigrey>" + html.escape(placeholder) + "</ansigrey>"),
                complete_style="column",
                style=custom_style,
            ).strip()
        else:
            user_input = pt_prompt(prompt_str, placeholder=HTML_print("<ansigrey>" + html.escape(placeholder) + "</ansigrey>"), style=custom_style).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return user_input


def show_help_message():
    """\
    Display help message for the session commands.
    """
    help_text = """\
<ansiblue><b>Available Commands:</b></ansiblue>
    <ansigreen>/exit, /quit, /bye, /e, /q</ansigreen>       - Exit the session
    <ansigreen>/help, /h, /?, /commands</ansigreen>         - Show this help message
    <ansigreen>/save [path], /s [path]</ansigreen>          - Save current session messages to a file (default: session.json)
    <ansigreen>/load [path], /l [path]</ansigreen>          - Load session messages from a file (default: session.json)
    <ansigreen>/clear, /c</ansigreen>                       - Clear the current session context and start fresh
    <ansigreen>/regen [seed], /r [seed]</ansigreen>         - Regenerate the last assistant response (optional seed, default to hash from last response)
    <ansigreen>/back, /b</ansigreen>                        - Remove the last interaction (user message + assistant response)
    <ansigreen>Ctrl+C or Ctrl+D</ansigreen>                 - Exit the session

<ansiblue><b>Tips:</b></ansiblue>
    • Use <ansigreen>Up/Down arrows</ansigreen> to navigate command history
    • Type your message and press <ansigreen>Enter</ansigreen> to send
    • Multi-line input is supported in some terminals
"""
    print_formatted_text(HTML_print(help_text), style=custom_style)


def get_user_input_loop(messages, session=None):
    """\
    Continuously get user input until an exit command is received.
    """
    while True:
        user_input = get_user_input_with_session(session)
        if user_input.lower() in ["/exit", "/quit", "/bye", "/e", "/q"]:
            return "", True, dict()
        if user_input.lower() in ["/help", "/h", "/?", "/commands"]:
            show_help_message()
            continue
        if user_input.lower() in ["/s", "/save"] or user_input.lower().startswith("/s ") or user_input.lower().startswith("/save "):
            path = ""
            if user_input.lower().startswith("/save "):
                path = user_input[6:].strip()
            elif user_input.lower().startswith("/s "):
                path = user_input[3:].strip()
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
        if user_input.lower() in ["/c", "/clear"]:
            messages.clear()
            click.echo(color_grey("Session context cleared. Starting fresh."))
            continue
        if user_input.lower().startswith("/r") or user_input.lower().startswith("/regen"):
            cmd_parts = user_input.split()
            cmd = cmd_parts[0].lower()
            if cmd in ["/r", "/regen"]:
                if len(messages) > 1 and messages[-1]["role"] == "assistant":
                    last_message = messages.pop()

                    seed = None
                    if len(cmd_parts) > 1:
                        try:
                            seed = int(cmd_parts[1])
                        except ValueError:
                            click.echo(color_warning(f"Invalid seed: {cmd_parts[1]}. Using default."))

                    if seed is None:
                        from ..utils.basic.hash_utils import md5hash

                        seed = md5hash(last_message["content"]) % 1000000

                    click.echo(color_grey(f"Regenerating last response... (New seed: {seed})"))
                    return None, False, {"seed": seed}
                else:
                    click.echo(color_warning("Nothing to regenerate."))
                    continue
        if user_input.lower() in ["/b", "/back"]:
            if len(messages) >= 2:
                messages.pop()
                messages.pop()
                click.echo(color_grey("Back one step (removed last interaction)."))
            else:
                click.echo(color_warning("Cannot go back further."))
            continue
        if user_input.startswith("/"):
            click.echo(color_warning(f"Unrecognized command: {user_input}. Type /help for available commands."))
            continue
        if not user_input:
            continue
        return user_input, False, dict()


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
    @click.option("--preset", "-p", help="LLM preset to use. Default to 'chat'.")
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

        try:
            llm = LLM(
                cache=(None if not cache else DiskCache(hpj(HEAVEN_CM.get("core.cache_path", "~/.ahvn/cache/"), "session_cli", abs=True))),
                preset="chat" if preset is None else preset,
                model=model,
                provider=provider,
            )
        except Exception as e:
            click.echo(color_error(f"Error initializing LLM: {error_str(e)}"), err=True)
            click.get_current_context().exit(1)

        user_contents = list()
        if input_files:
            for file_path in input_files:
                try:
                    content = load_txt(file_path)
                    user_contents.append(f"=== Content from {file_path} Start ===\n{content.strip()}\n=== Content from {file_path} End ===")
                    if verbose:
                        click.echo(color_grey(f"Read {len(content)} characters from {file_path}"))
                except Exception as e:
                    click.echo(f"Error reading file {file_path}: {e}", err=True)
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
            click.echo(f"Error during chat: {e}", err=True)
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
    @click.option("--preset", "-p", help="LLM preset to use. Default to 'embedder'.")
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
                click.echo(f"Error reading file {input_file}: {e}", err=True)
                click.get_current_context().exit(1)

        try:
            click.echo(llm.embed(user_content, verbose=verbose))
        except Exception as e:
            click.echo(f"Error during embedding: {e}", err=True)
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
    @click.option("--preset", "-p", help="LLM preset to use. Default to 'chat'.")
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

        click.echo(color_grey("Session started. Type /help for commands, /bye or /exit to quit."))

        try:
            llm = LLM(
                cache=(None if not cache else DiskCache(hpj(HEAVEN_CM.get("core.cache_path", "~/.ahvn/cache/"), "session_cli", abs=True))),
                preset="chat" if preset is None else preset,
                model=model,
                provider=provider,
            )
        except Exception as e:
            click.echo(color_error(f"Error initializing LLM: {e}"), err=True)
            click.get_current_context().exit(1)

        user_contents = list()
        if input_files:
            for file_path in input_files:
                try:
                    content = load_txt(file_path)
                    user_contents.append(f"=== Content from {file_path} Start ===\n{content.strip()}\n=== Content from {file_path} End ===")
                    if verbose:
                        click.echo(color_grey(f"Read {len(content)} characters from {file_path}"))
                except Exception as e:
                    click.echo(f"Error reading file {file_path}: {e}", err=True)
                    click.get_current_context().exit(1)
        user_contents.append("" if prompt is None else prompt.strip())

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user_exit = False
        gen_kwrags = dict()
        if prompt is None:
            user_input, user_exit, user_kwargs = get_user_input_loop(messages=messages, session=chat_session)
            user_contents.append(user_input)
            gen_kwrags = dict() | user_kwargs
        user_content = "\n\n".join([user_content for user_content in user_contents if user_content])

        while not user_exit:
            try:
                if user_content is not None:
                    messages.append({"role": "user", "content": user_content})
                if stream:
                    responses = list()
                    for message in llm.stream(messages, include=["message"], verbose=verbose, **gen_kwrags):
                        click.echo(message.get("content", ""), nl=False)
                        responses.append(message)
                    assistant_message = gather_assistant_message(responses)
                    click.echo()
                else:
                    assistant_message = llm.oracle(messages, include=["message"], verbose=verbose, **gen_kwrags)
                    click.echo(assistant_message.get("content", ""))
                messages.append(assistant_message)
                user_content, user_exit, user_kwargs = get_user_input_loop(messages=messages, session=chat_session)
                gen_kwrags = dict() | user_kwargs
            except KeyboardInterrupt:
                break
            except Exception as e:
                if messages and messages[-1]["role"] == "user":
                    messages.pop()
                click.echo(color_error(f"\n❌ Error getting response: {e}"), err=True)
                user_content, user_exit = get_user_input_loop(messages=messages, session=chat_session)
