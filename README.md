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

> *Note: Currently AgentHeaven is not released, please install from source.*

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
pip install "agent-heaven[exp,gui,dev]"

# uv
uv pip install "agent-heaven[exp,gui,dev]"

# poetry
poetry add agent-heaven --extras "exp gui dev"

# conda
conda install -c conda-forge agent-heaven[exp,gui,dev]
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

Set up your LLM providers:

**OpenAI (Optional):**
```bash
ahvn config set --global llm.providers.openai.api_key <YOUR_OPENAI_API_KEY>
```

**Ollama Models (Optional):**
```bash
# Requires Ollama to be installed
ollama pull gpt-oss:20b       # General local model (relatively large)
ollama pull qwen3:8b          # General local model (relatively small)
ollama pull embeddinggemma    # For text embedding
ollama pull qwen3-coder:30b   # For code generation
```

<br/>

## Documentation

📖 **[Complete Documentation](./docs/en/build/html/index.html)**

### Quick Links

- 🚀 [Introduction](./docs/en/build/html/introduction/index.html)
- 📋 [Getting Started](./docs/en/build/html/getting-started/index.html)
- 💻 [CLI Guide](./docs/en/build/html/cli-guide/index.html)
- 🐍 [Python API](./docs/en/build/html/python-guide/index.html)
- 🎯 [Example Applications](./docs/en/build/html/example-applications/index.html)
- 📚 [API Reference](./docs/en/build/html/api_index.html)

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

We welcome contributions! Please see our [Contributing Guide](./docs/en/source/contribution/index.md) for details on how to get started.

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
