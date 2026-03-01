# TJ Agent

基于 ReAct 架构的自主 AI 助手，支持多种 LLM 提供商。

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# LLM 配置
MODEL=qwen3.5-plus
TEMPERATURE=0.7
API_KEY=your_api_key
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 服务配置
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# 目录配置
AGENTS_DIR=agents
SKILLS_DIR=skills
```

### 3. 运行 CLI

```bash
uv run python -m src.tj_agent chat --agent-id assistant
```

### 4. 运行 API 服务

```bash
uv run python -m src.tj_agent serve
```

## 项目结构

```
tj-agent/
├── agents/              # Agent 模板 (YAML)
├── skills/             # 技能模块
├── src/tj_agent/
│   ├── react/          # ReAct 循环
│   ├── skills/         # 技能系统
│   ├── tools/         # 工具
│   ├── memory/         # 记忆存储 (SQLite)
│   ├── models.py      # 数据模型
│   └── llm_config.py  # LLM 配置
└── .env               # 环境变量
```

## 可用命令

```bash
# 交互式对话
uv run python -m src.tj_agent chat --agent-id assistant

# 单次请求
uv run python -m src.tj_agent run --agent-id assistant --message "你好"

# 列出所有 Agent
uv run python -m src.tj_agent list

# 查看会话
uv run python -m src.tj_agent sessions

# 启动 API 服务
uv run python -m src.tj_agent serve
```

## 添加新 Agent

在 `agents/` 目录下创建 YAML 文件：

```yaml
id: "my-agent"
name: "我的助手"
description: "描述"

system_prompt: |
  你的系统提示词

tools:
  - bash
  - read_file
  - write_file
  - list_directory

skills:
  - file-organizer
```

## 添加新技能

在 `skills/` 目录下创建文件夹，包含 `SKILL.md` 文件：

```
skills/my-skill/
└── SKILL.md
```
