# Project Specification: TJ Agent System

## 1. Project Overview
**TJ Agent** is a customized, Python-based AI Agent system driven by the ReAct (Reason + Act) architecture. It is designed to act as an autonomous assistant capable of executing complex tasks by integrating standard Tool Calling, the Model Context Protocol (MCP), and specifically, Anthropic's Agent Skills specification (e.g., bash execution, text editing).

The system prioritizes modularity, exact pattern matching over probabilistic retrieval for context, and clear API boundaries.

## 2. Core Technical Stack
* **Language:** Python 3.10+
* **Environment Management:** `uv`
* **Data Validation & Schema:** `pydantic` (v2)
* **API Framework:** `fastapi` (for exposing the agent as a service)
* **HTTP Client:** `httpx` (async)
* **External Integration:** Official `mcp` Python SDK
* **Memory/Search Engine:** SQLite FTS5 or PostgreSQL (Strictly traditional full-text search; **DO NOT** use vector databases or embeddings).

## 3. System Architecture & Modules

### 3.1. The ReAct Controller (Core Engine)
The central loop orchestrating the Agent's behavior.
* **Mechanism:** Implements a robust Thought -> Action -> Observation loop.
* **Responsibility:** Parses user input, maintains context, and decides whether to trigger an atomic Tool, fetch data via MCP, or activate a complex Agent Skill.

### 3.2. Agent Skills Implementation (agentskills.io Standard)
Implement support for the open Agent Skills directory format to give the agent domain expertise.
* **Format Structure:** The system must parse directories containing a `SKILL.md` file (YAML frontmatter + Markdown content) and handle optional `scripts/` and `assets/` subdirectories.
* **Progressive Disclosure Mechanism:**
    1. **Discovery:** On startup, parse the YAML frontmatter of all available skills. Inject **only** the `name` and `description` into the Agent's system prompt (to conserve tokens).
    2. **Activation:** Create a specific internal tool (e.g., `load_skill_instructions`) that the Agent can call when it matches a task to a skill's description. This tool reads the full `SKILL.md` Markdown into the context window.
    3. **Execution:** The agent follows the loaded instructions, optionally using base tools (like bash) to execute bundled scripts.

### 3.3. Base Tools & MCP Client Layer
* **Base Environment Tools:** Implement essential tools needed for the Agent to interact with the system and execute skills. This includes a `bash` execution tool (to run skill scripts) and file system read/write tools.
* **MCP Integration:** An MCP Client layer to dynamically discover and attach tools/resources from external MCP servers.

### 3.4. Context & Memory Management (Traditional Search)
* **Long-term Memory:** Implement a retrieval system for historical facts or past conversations using **Traditional Search only** (SQLite FTS5). 
* **Constraint:** The architecture must explicitly avoid Vector Databases, Embeddings, or semantic search libraries.

## 4. Implementation Phases (For AI Coder)

* Samples are provided in the `Samples/` directory, including: Pydantic 数据结构 (核心大脑的记忆载体), 工具注册装饰器 (Tool Registry Decorator), SQLite FTS5 传统搜索 (Prompt 记忆检索核心), Skill Structure and SKILL.md. 
* Samples are only for reference, and the actual implementation should follow the project specification and your judgment.
* You may discuss with the user about the implementation details if you are unsure about the specifics.
* Please act as the lead developer and follow these phases sequentially. Ask for my approval before moving to the next phase.
    * **Phase 1: Foundation & Data Structures.** Setup the project. Define the Pydantic models for the ReAct state, standard Tool calls, and Message history.
    * **Phase 2: Base Tools & MCP.** Implement the tool registry decorator, the core filesystem/bash tools, and the MCP client connection logic.
    * **Phase 3: The Agent Skills Engine.** Build the parser for `agentskills.io` formatted directories. Implement the "Discovery" logic (extracting YAML) and the "Activation" tool (loading full Markdown).
    * **Phase 4: The ReAct Loop.** Build the core asynchronous `run_agent` loop that interacts with the LLM. Ensure it can organically decide when to read a skill's full instructions vs. when to execute a base tool.
    * **Phase 5: Memory & Service Wrapper.** Implement the SQLite FTS5 memory module and wrap the entire agent engine in a FastAPI streaming endpoint.