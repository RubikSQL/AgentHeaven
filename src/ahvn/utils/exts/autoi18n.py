__all__ = [
    "autoi18n",
]

from ..basic.log_utils import get_logger
from ..basic.config_utils import HEAVEN_CM, hpj
from ..basic.path_utils import *
from ..basic.file_utils import *
from ..basic.serialize_utils import load_txt
from ..basic.parser_utils import parse_md
from ...llm import LLM
from ...ukf.templates.basic.prompt import PromptUKFT

logger = get_logger(__name__)
_src_lang = HEAVEN_CM.get("prompts.main", "en")
_tgt_lang = HEAVEN_CM.get("prompts.lang", "en")

from typing import Optional, List, Dict
import polib
import re


def autoi18n(
    path,
    src_lang: Optional[str] = None,
    tgt_lang: Optional[str] = None,
    overwrite: bool = False,
    batch_size: int = 20,
    hints: Optional[List[str]] = None,
    llm_args: Optional[Dict] = None,
    **kwargs,
):
    """\
    Translate Babel `.po` files with an LLM.

    Args:
        path (str): The root directory containing the 'locale' folder.
        src_lang (Optional[str]): The main language of the POT file. Defaults to None, which will use the encoding in the config file ("prompts.main").
        tgt_lang (Optional[str]): The target language to translate to. Defaults to None, which will use the encoding in the config file ("prompts.lang").
        overwrite (bool): Overwrite existing translations. Defaults to False.
        batch_size (int): Number of entries to process in each batch. Defaults to 10.
        llm_args (Optional[Dict]): Arguments for the LLM model. Defaults to None, which will resolve to {"preset": "translator"}
        **kwargs: Additional keyword arguments passed to `cmd` (`subprocess.Popen`).
    """
    if src_lang is None:
        src_lang = _src_lang
    if tgt_lang is None:
        tgt_lang = _tgt_lang

    if llm_args is None:
        llm_args = {"preset": "translator"}

    path = hpj(path, abs=True)
    locale_path = hpj(path, "locale")
    touch_dir(locale_path)
    cfg_path = hpj(locale_path, "babel.cfg")
    if not exists_file(cfg_path):
        logger.warning(f"Babel configuration file not found at {cfg_path}. Please run `babel_init` first.")
        return

    lang_po_path = hpj(locale_path, tgt_lang, "LC_MESSAGES", "messages.po")
    if not exists_file(lang_po_path):
        logger.warning(f"PO file not found at {lang_po_path}. Please run `babel_init` first.")
        return

    # Load pofile
    pofile = polib.pofile(lang_po_path)

    # Find untranslated or empty entries
    entries = [entry for entry in pofile if not entry.msgstr or overwrite]
    if not entries:
        logger.info(f"No untranslated entries found in {lang_po_path}.")
        return

    logger.info(f"Found {len(entries)} entries to translate in {lang_po_path}.")

    files = sorted(list_files(path, ext="jinja;jinja2;j2;txt"))
    contents = [load_txt(pj(path, file)) for file in files]

    # Construct file context description
    file_context_desc = "## Original Files\n===== FILE CONTENTS START =====\n"
    for file_path, content in zip(files, contents):
        file_context_desc += f"\n### File: `{file_path}`\n```jinja\n{content}\n```\n"
    file_context_desc += "===== FILE CONTENTS END ====="

    # Build the system prompt
    system_prompt = f"""\
You are a professional translator working with Babel PO files. Your task is to translate the `msgid` strings from source language ({src_lang}) into the `msgstr` in target language ({tgt_lang}).

Example:
## Source Language: en
## Input:
```pot
msgid_0: "Inputs:"
msgid_1: "Output:"
```
## Target Language: zh
## Output:
```pot
msgstr_0: "输入:"
msgstr_1: "输出:"
```

Now, given new `msgid` lines, produce the translated PO entries in the same format.
Output only the translated PO entries without any additional text. Your output should be wrapped in markdown code block with `pot` syntax highlighting."""

    llm = LLM(**llm_args)

    for i in range(0, len(entries), batch_size):
        batch_entries = entries[i : i + batch_size]
        strings = [entry.msgid for entry in batch_entries]

        # Build descriptions
        desc_list = [file_context_desc]

        # Build input section
        input_pot = "## Input\n```pot\n"
        for j, string in enumerate(strings):
            input_pot += f'msgid_{j}: "{string}"\n'
        input_pot += "```"
        desc_list.append(input_pot)

        # Build instructions
        instr_list = [
            f"Translate from {src_lang} to {tgt_lang}.",
            "Output only the translated PO entries in the format shown in the example.",
            "Wrap the output in a markdown `pot` code block.",
        ]
        if hints:
            instr_list.extend(hints)

        # Create prompt using PromptUKFT
        prompt = PromptUKFT.from_path(
            "& prompts/system",
            default_entry="prompt.jinja",
            binds={
                "system": system_prompt,
                "descriptions": desc_list,
                "instructions": instr_list,
            },
        )

        try:
            prompt_str = prompt.text(lang="en").rstrip()
        except Exception as e:
            logger.error(f"Failed to render prompt for batch {i // batch_size + 1}: {e}")
            continue

        logger.debug(f"Prompt:\n{prompt_str}")

        try:
            response = llm.oracle(prompt_str)
        except Exception as e:
            logger.error(f"LLM failed for batch {i // batch_size + 1}: {e}")
            continue

        logger.debug(f"LLM response:\n{response}")

        try:
            parsed = parse_md(response)
            pot_response = parsed.get("pot", "").strip()
            for j, entry in enumerate(batch_entries):
                pattern = rf'msgstr_{j}:\s*"((?:[^"\\]|\\.)*)"'
                match = re.search(pattern, pot_response, re.DOTALL)
                if match:
                    translation = match.group(1)
                    translation = eval(f'"{translation}"')
                    entry.msgstr = translation
                    logger.info(f"Translated: {entry.msgid} -> {entry.msgstr}")
                else:
                    logger.warning(f"Failed to extract translation for: {entry.msgid}")
        except Exception as e:
            logger.error(f"Error processing batch {i // batch_size + 1}: {e}")
            continue
    pofile.save(lang_po_path)
    logger.info(f"Translations saved to {lang_po_path}.")
    return
