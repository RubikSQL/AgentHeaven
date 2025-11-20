# AgentHeaven

[![English](https://img.shields.io/badge/Language-English-blue.svg)](./README.en.md)
[![简体中文](https://img.shields.io/badge/语言-简体中文-blue.svg)](./README.zh.md)

![PyPI](https://img.shields.io/pypi/v/agent-heaven)
![License](https://img.shields.io/github/license/RubikSQL/AgentHeaven)
![Python Version](https://img.shields.io/pypi/pyversions/agent-heaven)

*不要问你的智能体能为你做什么，要问你能为你的智能体做什么。*

AgentHeaven 是专为 AI 智能体项目设计的综合管理系统，提供环境隔离、依赖管理和流水线工作流，类似于 conda 但专门为智能体定制。

📖 [English Documentation](https://rubiksql.github.io/AgentHeaven-docs/en/)
📖 [中文文档](https://rubiksql.github.io/AgentHeaven-docs/zh/)
💻 [文档 GitHub](https://github.com/RubikSQL/AgentHeaven-docs)

> 🚧 AgentHeaven 正处于积极的实验性开发阶段。功能可能会发生变化，尚未准备好进行稳定部署。

<br/>

## 安装

AgentHeaven 支持多种包管理器以便灵活安装。请选择最适合您工作流的方式：

可选依赖：
- `exp`：实验性功能与集成（包括数据库集成、向量引擎等），推荐安装。
- `gui`：用于智能体管理和监控的图形界面工具。
- `dev`：开发工具，包括文档生成、代码格式化、测试等。

<br/>

### 快速安装

最小安装（仅核心组件，不包含可选依赖）：

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

完整安装（包含所有可选依赖）：

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

### 从源码安装

最小安装（仅核心组件，不包含可选依赖）：

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

完整安装（包含所有可选依赖）：

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

## 快速开始

### 前置要求

除了 Python 要求外，我们建议安装 [Git](https://git-scm.com/) 以支持版本控制功能。

<br/>

### 初始设置

全局初始化 AgentHeaven 环境。使用 `-r` 强制重新初始化：

```bash
ahvn setup --reset
```

<br/>

### 配置

设置你的 LLM 提供商：

**OpenAI（可选）：**
```bash
ahvn config set --global llm.providers.openai.api_key <YOUR_OPENAI_API_KEY>
```

**Ollama 模型（可选）：**
```bash
# 需要先安装 Ollama
ollama pull gpt-oss:20b       # 通用本地模型（较大）
ollama pull qwen3:8b          # 通用本地模型（较小）
ollama pull embeddinggemma    # 用于文本嵌入
ollama pull qwen3-coder:30b   # 用于代码生成
```

<br/>

## 文档

📖 **[完整文档](./docs/zh/build/html/index.html)**

### 快速链接

- 🚀 [介绍](./docs/zh/build/html/introduction/index.html)
- 📋 [入门指南](./docs/zh/build/html/getting-started/index.html)
- 💻 [CLI 指南](./docs/zh/build/html/cli-guide/index.html)
- 🐍 [Python API](./docs/zh/build/html/python-guide/index.html)
- 🎯 [示例应用](./docs/zh/build/html/example-applications/index.html)
- 📚 [API 参考](./docs/zh/build/html/api_index.html)

### 本地构建文档

你可以直接访问已编译的文档：`docs/zh/build/html/index.html`。

如果要重新构建文档并启动文档服务器，可以克隆仓库，从源完整安装并通过如下脚本构建文档：

```bash
bash scripts/docs.bash en zh -s
```

想要启动文档服务器但不重新构建，运行：

```bash
bash scripts/docs.bash en zh -s --no-build
```

- 英文文档：`http://localhost:8000/`
- 中文文档：`http://localhost:8001/`

<br/>

## 贡献

我们欢迎贡献！请查看我们的[贡献指南](./docs/zh/source/contribution/index.md)了解如何开始。

<br/>

## 引用

如果你在研究或项目中使用了 AgentHeaven，请按如下方式引用：

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

## 许可协议

本项目采用可持续使用许可协议。详见 [LICENSE](./LICENSE) 文件。

<br/>
