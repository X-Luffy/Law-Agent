# Agent System

一个完整的智能Agent系统，包含工具系统、记忆系统、上下文管理、意图识别、RAG检索和Self-reflection功能。

## 快速开始

### 1. 环境准备

```bash
# 激活conda环境
conda activate /home/mnt/xieqinghongbing/env/open_manus

# 设置环境变量
export DASHSCOPE_API_KEY="sk-5d4975fe68f24d83809ac3c7bf7468ba"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 2. 安装依赖

```bash
cd /home/mnt/xieqinghongbing/code/xiazhaoyuan/Agent
pip install -r requirements.txt
```

### 3. 运行系统

#### 方式1：使用Streamlit前端（推荐）

```bash
streamlit run app.py
```

然后在浏览器中打开显示的URL（通常是 http://localhost:8501）

#### 方式2：命令行交互

```bash
python main.py
```

#### 方式3：运行测试

```bash
cd /home/mnt/xieqinghongbing/code/xiazhaoyuan
python Agent/test_system.py
```

## 项目结构

```
Agent/
├── agent/          # Agent核心模块（层次化结构）
│   ├── base.py     # BaseAgent基类
│   ├── react.py    # ReActAgent（思考-行动循环）
│   ├── toolcall.py # ToolCallAgent（工具调用）
│   └── agent.py    # 最终Agent类
├── tools/          # 工具系统（Web检索、Python执行等）
├── memory/          # 记忆系统（短期记忆session、长期记忆向量数据库）
├── embedding/       # Embedding模型和工具选择
├── context/         # 上下文管理（窗口裁剪、上下文精炼）
├── intent/          # 用户意图识别和状态管理
├── rag/             # RAG模块（向量存储、检索器、管理器）
├── reflection/      # Self-reflection功能
├── config/          # 配置文件
├── schema.py        # 数据模式定义
├── app.py           # Streamlit前端应用
├── main.py          # 命令行入口
└── test_system.py  # 系统测试脚本
```

## 功能特性

### 核心功能

- **层次化Agent架构**: BaseAgent → ReActAgent → ToolCallAgent → Agent
- **LLM模块**: 使用OpenAI接口连接到DashScope兼容端点（qwen3-max模型）
- **Embedding模型**: 使用DashScope embedding API（text-embedding-v4，1024维）
- **向量数据库**: 默认使用ChromaDB，支持持久化存储

### 工具系统

- Web搜索工具（Google搜索）
- Python执行工具
- 计算器工具
- 文件读取工具
- 日期时间工具

### 记忆系统

- **短期记忆（session）**: 存储当前会话的对话历史
- **长期记忆（向量数据库）**: 统一存储对话记录、工具描述、精炼上下文等
- **自动降级**: 如果ChromaDB未安装，自动使用内存占位符实现

### RAG模块

- **法律专业信息库RAG**: 从法律专业信息库检索相关片段，使用LLM整合生成答案
- **Web检索RAG**: 使用Google搜索工具检索网络信息，使用LLM整合生成答案
- **自动选择**: 根据查询自动选择RAG类型或混合使用

### 上下文管理

- **窗口裁剪**: 保留最近N轮对话作为上下文
- **上下文精炼**: 使用embedding对往期对话进行聚类和摘要，并持久化到向量数据库

### 意图识别

- **混合识别**: 结合LLM和规则匹配进行意图识别
- **支持类型**: query（查询）、task（任务）、clarification（澄清）、follow_up（跟进）、correction（纠正）、greeting（问候）、goodbye（告别）
- **状态追踪**: 维护当前意图和意图历史，提取关键信息

### Self-reflection

- **多角色反思**: critic、improver、validator三个角色
- **自动改进**: 自动判断是否需要改进回复，提供具体的改进建议

## 配置说明

### 环境变量

```bash
# DashScope API Key（LLM和Embedding共用）
export DASHSCOPE_API_KEY="sk-5d4975fe68f24d83809ac3c7bf7468ba"

# LLM配置（可选，使用默认值）
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 配置文件

主要配置在 `config/config.py` 中：

- **LLM配置**: `llm_model="qwen3-max"`, `llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"`
- **Embedding配置**: `embedding_model="text-embedding-v4"`, `embedding_dim=1024`
- **向量数据库配置**: `vector_db_path="./data/vector_db"`, `vector_db_collection="long_term_memory"`

## 使用示例

### 基本对话

```python
from Agent.config.config import Config
from Agent.agent.agent import Agent
import asyncio

# 初始化配置
config = Config()

# 创建Agent实例
agent = Agent(
    name="legal_assistant",
    description="法律对话助手",
    system_prompt="你是一个专业的法律助手。",
    config=config
)

# 处理用户消息
user_message = "我想了解合同法的相关规定"
response = asyncio.run(agent.process_message(user_message))
print(response)
```

### 添加法律文档到知识库

```python
from Agent.rag.rag_manager import RAGManager

rag_manager = RAGManager(config)

# 添加法律文档
documents = [
    "《合同法》第一条：为了保护合同当事人的合法权益...",
    "《合同法》第二条：本法所称合同是平等主体的自然人...",
]

metadatas = [
    {"law_type": "合同法", "chapter": "第一章"},
    {"law_type": "合同法", "chapter": "第一章"},
]

rag_manager.add_knowledge_base(
    documents=documents,
    metadatas=metadatas
)
```

## 系统状态

✅ **系统框架完整** - 所有核心模块已实现  
✅ **功能完整** - 所有主要功能已实现  
✅ **测试通过** - 系统测试全部通过  
✅ **前端界面** - Streamlit前端已实现

系统已准备就绪，可以开始使用！
