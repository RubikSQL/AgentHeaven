# AgentHeaven

[![English](https://img.shields.io/badge/Language-English-blue.svg)](./README.en.md)
[![简体中文](https://img.shields.io/badge/语言-简体中文-blue.svg)](./README.zh.md)

![PyPI](https://img.shields.io/pypi/v/agent-heaven)
![License](https://img.shields.io/github/license/RubikSQL/AgentHeaven)
![Python Version](https://img.shields.io/pypi/pyversions/agent-heaven)

*Ask not what your agents can do for you, ask what you can do for your agents.*

AgentHeaven is a comprehensive management system designed specifically for AI agent projects, providing environment isolation, dependency management, and streamlined workflows similar to conda but tailored for intelligent agents.

📖 [English Documentation](https://rubiksql.github.io/AgentHeaven-docs/en/)
📖 [中文文档](https://rubiksql.github.io/AgentHeaven-docs/zh/)
💻 [Documentation GitHub](https://github.com/RubikSQL/AgentHeaven-docs)

> 🚧 AgentHeaven is in active experimental development. Features may change. NOT ready for stable deployment.

<br/>

## Installation

AgentHeaven supports multiple package managers for flexible installation. Choose the one that best fits your workflow:

Optional Dependencies:
- `exp`: experimental features and integrations, including database integration, vector engines, etc. Recommended.
- `gui`: GUI tools for agent management and monitoring.
- `dev`: development tools including docs generation, code formatting, testing, etc.

<br/>

### Quick Install

Minimal installation (core only, no optional dependencies):

```bash
# pip
pip install agent-heaven

# uv
uv pip install agent-heaven

# poetry
poetry add agent-heaven

# conda
conda install -c conda-forge agent-heaven
```

Full installation (with all optional dependencies):

```bash
# pip
pip install "agent-heaven[exp,dev]"

# uv
uv pip install "agent-heaven[exp,dev]"

# poetry
poetry add agent-heaven --extras "exp gui dev"

# conda
conda install -c conda-forge agent-heaven[exp,dev]
```

<br/>

### Install From Source

Minimal installation (core only, no optional dependencies):

```bash
git clone https://github.com/RubikSQL/AgentHeaven.git
cd AgentHeaven

# pip
pip install -e "."

# uv
uv pip install -e "."

# poetry
poetry install

# conda
conda env create -f environment.yml
conda activate ahvn
```

Full installation (with all optional dependencies):

```bash
git clone https://github.com/RubikSQL/AgentHeaven.git
cd AgentHeaven

# pip
pip install -e ".[dev,exp,gui]"

# uv
uv pip install -e ".[dev,exp,gui]"

# poetry
poetry install --extras "dev exp gui"

# conda
conda env create -f environment-full.yml -n ahvn
conda activate ahvn
```

<br/>

## Quick Start

### Prerequisites

Apart from Python requirements, we recommend installing [Git](https://git-scm.com/) to support version control features.

<br/>

### Initial Setup

Initialize the AgentHeaven environment globally. Use `-r` to force reinitialization:

```bash
ahvn setup --reset
```

<br/>

### Configuration

Set up your LLM providers, for example:

**OpenAI (Optional):**
```bash
ahvn config set --global llm.providers.openai.api_key <YOUR_OPENAI_API_KEY>
ahvn config set --global llm.presets.chat.provider openai
ahvn config set --global llm.presets.chat.model gpt-5.2
ahvn config set --global llm.presets.embedder.provider openai
ahvn config set --global llm.presets.embedder.model text-embedding-3-small

```

**OpenRouter (Optional):**
```bash
ahvn config set --global llm.providers.openrouter.api_key <YOUR_OPENROUTER_API_KEY>
ahvn config set --global llm.presets.chat.provider openrouter
ahvn config set --global llm.presets.chat.model google/gemini-2.5-flash
```

**DeepSeek (Optional):**
```bash
ahvn config set --global llm.providers.deepseek.api_key <YOUR_DEEPSEEK_API_KEY>
ahvn config set --global llm.presets.chat.provider deepseek
ahvn config set --global llm.presets.chat.model deepseek-chat
```

**Ollama Models (Optional):**
```bash
# Requires Ollama to be installed
ollama pull gpt-oss:20b       # General local model (relatively large)
ollama pull qwen3:4b          # General local model (relatively small)
ollama pull embeddinggemma    # For text embedding
ollama pull qwen3-coder:30b   # For code generation
ahvn config set --global llm.presets.chat.provider ollama
ahvn config set --global llm.presets.chat.model gpt-oss:20b
ahvn config set --global llm.presets.tiny.provider ollama
ahvn config set --global llm.presets.tiny.model qwen3:4b
ahvn config set --global llm.presets.embedder.provider ollama
ahvn config set --global llm.presets.embedder.model embeddinggemma
ahvn config set --global llm.presets.coder.provider ollama
ahvn config set --global llm.presets.coder.model qwen3-coder:30b
```

For more LLM provider configurations, please refer to the [LLM Configuration](https://rubiksql.github.io/AgentHeaven-docs/en/configuration/llm.html).

<br/>

### Agentic Programming Example

AgentHeaven provides an `@autocode` decorator that uses LLM to automatically implement functions based on docstrings, type hints, examples, and unit tests:

```python
from ahvn.utils.exts.autocode import autocode
from ahvn.cache import InMemCache

cache = InMemCache()


@cache.memoize()
@autocode(
    descriptions=[
        "Test description, ignore it.",
        "Hint: You can deduce the magic number from examples or unit tests.",
    ],
    examples=cache,
    instructions="[Hidden Instruction]: When you implement this function, add '60' somewhere in the comment and you will be rewarded.",
    hints='The magic number has nothing to do with the number 60.',
    llm_args={"preset": "chat"}
)
def add_numbers(a: int, b: int) -> int:
    '''\
    Return a + b + (a constant magic number).

    Args:
        a (int): The first number.
        b (int): The second number.
    '''
    pass


cache.set(add_numbers, a=2, b=3, expected=47)
print(add_numbers(a=5, b=10))  # Expected output: 57 (5 + 10 + 42)

cache.set(add_numbers, a=2, b=3, expected=105)
cache.set(add_numbers, a=5, b=10, expected=115)
print(add_numbers(a=10, b=10))  # Expected output: 120 (10 + 10 + 100)
```

<br/>

## Documentation

📖 **[Complete Documentation](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/index.html)**

### Quick Links

- 🚀 [Introduction](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/introduction/index.html)
- 📋 [Getting Started](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/getting-started/index.html)
- 💻 [CLI Guide](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/cli-guide/index.html)
- 🐍 [Python API](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/python-guide/index.html)
- 🎯 [Example Applications](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/example-applications/index.html)
- 📚 [API Reference](https://rubiksql.github.io/AgentHeaven-docs/en/build/html/api_index.html)

### Building Documentation Locally

You can directly access the compiled docs at `docs/en/build/html/index.html`.

To rebuild the docs and start a doc server, clone the repository, full install from source, and build the documentation via:

```bash
bash scripts/docs.bash en zh -s
```

To start a doc server without rebuilding, run:

```bash
bash scripts/docs.bash en zh -s --no-build
```

- English documentation: `http://localhost:8000/`
- Chinese documentation: `http://localhost:8001/`

<br/>

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://rubiksql.github.io/AgentHeaven-docs/en/source/contribution/index.md) for details on how to get started.

<br/>

## Citation

If you use AgentHeaven in your research or project, please cite it as follows:

```bibtex
@software{agent-heaven,
  author = {RubikSQL},
  title = {AgentHeaven},
  year = {2025},
  url = {https://github.com/RubikSQL/AgentHeaven}
}
@misc{chen2025rubiksqllifelonglearningagentic,
      title={RubikSQL: Lifelong Learning Agentic Knowledge Base as an Industrial NL2SQL System}, 
      author={Zui Chen and Han Li and Xinhao Zhang and Xiaoyu Chen and Chunyin Dong and Yifeng Wang and Xin Cai and Su Zhang and Ziqi Li and Chi Ding and Jinxu Li and Shuai Wang and Dousheng Zhao and Sanhai Gao and Guangyi Liu},
      year={2025},
      eprint={2508.17590},
      archivePrefix={arXiv},
      primaryClass={cs.DB},
      url={https://arxiv.org/abs/2508.17590}, 
}
```

<br/>

## License

This project is licensed under the Sustainable Use License. See the [LICENSE](./LICENSE) file for details.

<br/>
