# Legal Agent System 完整流程示意图

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (app.py)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Streamlit UI: 用户输入 → 实时状态显示 → 结果展示        │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LegalFlow (协调层)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  execute(user_input, status_callback)                    │   │
│  │    ↓                                                      │   │
│  │  core_agent.process_message(user_input, status_callback) │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CoreAgent (路由层)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Phase 1: 意图识别与实体提取                              │   │
│  │    ├─ identify_domain_and_intent()                       │   │
│  │    │   └─ 使用LLM识别: domain, intent                    │   │
│  │    ├─ update_state_memory()                              │   │
│  │    │   └─ 保存到 GlobalMemory                            │   │
│  │    └─ 如果是 Non_Legal → handle_non_legal_query()        │   │
│  │                                                           │   │
│  │  Phase 2: 智能路由                                        │   │
│  │    ├─ get_or_create_sub_agent(domain, intent)            │   │
│  │    │   └─ 创建/获取 SpecializedAgent                     │   │
│  │    └─ 传递 status_callback                               │   │
│  │                                                           │   │
│  │  Phase 3: 专业Agent执行                                   │   │
│  │    └─ sub_agent.execute_task(...)                        │   │
│  │                                                           │   │
│  │  Phase 4: 返回结果                                        │   │
│  │    └─ return result                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              SpecializedAgent (执行层)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  execute_task(user_message, domain, intent, ...)         │   │
│  │                                                           │   │
│  │  Step 1: 制定计划                                         │   │
│  │    └─ _create_plan() → 根据intent生成SOP计划             │   │
│  │                                                           │   │
│  │  Step 2: ReAct循环执行 (run方法)                         │   │
│  │    ├─ think() → 分析问题，决定调用工具                   │   │
│  │    │   └─ LLM + Native Function Calling                  │   │
│  │    ├─ act() → 执行工具调用                               │   │
│  │    │   ├─ web_search (Bocha API)                        │   │
│  │    │   ├─ python_executor                               │   │
│  │    │   └─ ocr, calculator, etc.                         │   │
│  │    └─ observe() → 获取工具结果，继续思考                 │   │
│  │                                                           │   │
│  │  Step 3: 自我评估 (Critic机制)                           │   │
│  │    ├─ _self_evaluate_result()                            │   │
│  │    │   └─ 使用 RESULT_EVALUATION_PROMPT 严格评估         │   │
│  │    │                                                      │   │
│  │    ├─ 如果评估不通过:                                    │   │
│  │    │   ├─ _generate_refined_search_query()              │   │
│  │    │   │   └─ 根据反馈生成改进的搜索关键词               │   │
│  │    │   ├─ 重新执行 web_search                            │   │
│  │    │   └─ 重新生成回答                                   │   │
│  │    │                                                      │   │
│  │    └─ 最多进行 2 轮评估和重新搜索                        │   │
│  │                                                           │   │
│  │  Step 4: 清理资源                                         │   │
│  │    └─ cleanup() → 清理工具资源                           │   │
│  │                                                           │   │
│  │  Step 5: 返回最终结果                                     │   │
│  │    └─ return result                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 详细执行流程

### 1. 用户输入阶段
```
User Input
    ↓
app.py: process_message()
    ↓
保存用户消息到 st.session_state.messages
    ↓
显示用户消息
    ↓
创建 status_callback (实时状态更新)
    ↓
调用 legal_flow.execute(user_input, status_callback)
```

### 2. LegalFlow 协调阶段
```
LegalFlow.execute()
    ↓
core_agent.process_message(user_input, status_callback)
```

### 3. CoreAgent 路由阶段

#### 3.1 意图识别
```
CoreAgent.process_message()
    ↓
获取对话历史 (conversation_history)
    ↓
identify_domain_and_intent(user_message, conversation_history)
    ├─ 使用 LLM 分析用户问题
    ├─ 识别 LegalDomain (Family_Law, Criminal_Law, etc.)
    ├─ 识别 LegalIntent (QA_Retrieval, Case_Analysis, etc.)
    └─ 提取关键实体 (persons, amounts, dates, locations)
    ↓
update_state_memory(domain, intent, entities)
    └─ 保存到 GlobalMemory (State Memory)
    ↓
如果是 Non_Legal
    └─ handle_non_legal_query() → 简单回答 + 引导
```

#### 3.2 智能路由
```
get_or_create_sub_agent(domain, intent)
    ├─ 生成 key = f"{domain}_{intent}"
    ├─ 如果不存在，创建新的 SpecializedAgent
    │   └─ 注入领域特定的 SOP (Standard Operating Procedure)
    └─ 返回 sub_agent
```

#### 3.3 执行任务
```
sub_agent.execute_task(user_message, domain, intent, status_callback)
```

### 4. SpecializedAgent 执行阶段

#### 4.1 制定计划
```
_create_plan(user_message, domain, intent)
    ├─ 根据 intent 选择计划模板
    │   ├─ QA_Retrieval → _create_qa_retrieval_plan()
    │   ├─ Case_Analysis → _create_case_analysis_plan()
    │   ├─ Calculation → _create_calculation_plan()
    │   └─ ...
    └─ 返回执行计划文本
    ↓
将计划添加到 memory
```

#### 4.2 ReAct 循环执行
```
run(user_message)
    ↓
while current_step < max_steps and state != FINISHED:
    ├─ step()
    │   ├─ think()
    │   │   ├─ 获取最近消息 (get_recent_messages)
    │   │   ├─ 调用 LLM.chat_with_tools()
    │   │   │   └─ 提供 tools_schema (Native Function Calling)
    │   │   ├─ 解析 tool_calls (如果有)
    │   │   └─ 添加到 current_tool_calls
    │   │
    │   └─ act() (如果有工具调用)
    │       ├─ 遍历 current_tool_calls
    │       ├─ execute_tool(tool_call)
    │       │   ├─ 从 available_functions 获取工具函数
    │       │   ├─ 解析参数 (JSON)
    │       │   ├─ 执行工具 (同步/异步)
    │       │   └─ 返回结果
    │       └─ 将工具结果添加到 memory
    │
    └─ 检查是否完成
        ├─ 如果有最终回答 → state = FINISHED
        └─ 否则继续循环
    ↓
提取最终回答 (最后一条 assistant 消息)
    ↓
返回 result
```

#### 4.3 自我评估 (Critic机制)
```
_self_evaluate_result(user_message, result, domain, intent)
    ├─ 使用 RESULT_EVALUATION_PROMPT
    ├─ 调用 LLM 评估 (temperature=0.0, 严格模式)
    ├─ 解析 JSON 响应
    │   ├─ is_acceptable: true/false
    │   └─ feedback: 具体反馈
    └─ 返回 (is_acceptable, feedback)
    ↓
如果 is_acceptable == False:
    ├─ critic_round += 1
    ├─ 如果 critic_round < max_critic_rounds (2):
    │   ├─ _generate_refined_search_query()
    │   │   └─ 根据反馈生成改进的搜索关键词
    │   ├─ 执行新的 web_search
    │   ├─ 将搜索结果添加到 memory
    │   ├─ 重新生成回答 (基于新搜索结果)
    │   └─ 再次评估 (回到循环开始)
    └─ 如果达到最大轮数 → 返回当前结果
```

#### 4.4 清理资源
```
cleanup()
    ├─ 遍历所有工具
    ├─ 调用工具的 cleanup() 方法 (如果有)
    └─ 清理完成
```

### 5. 结果返回阶段
```
SpecializedAgent.execute_task() 返回 result
    ↓
CoreAgent.process_message() 返回 result
    ↓
LegalFlow.execute() 返回 result
    ↓
app.py: process_message()
    ├─ 提取 execution_logs
    ├─ 保存助手消息到 st.session_state.messages
    │   └─ 包含: content, logs, error_occurred, timestamp
    └─ st.rerun() → 触发页面刷新
    ↓
display_conversation()
    ├─ 遍历 st.session_state.messages
    ├─ 显示所有消息 (用户 + 助手)
    ├─ 对于助手消息:
    │   ├─ 显示内容
    │   ├─ 显示来源链接 (render_sources)
    │   └─ 显示完整执行流程 (render_execution_timeline)
    └─ 完成显示
```

## 关键组件说明

### 1. State Memory (GlobalMemory)
- **作用**: 存储当前案件的已知事实
- **内容**: domain, intent, entities (persons, amounts, dates, locations)
- **更新时机**: CoreAgent 识别后立即更新
- **用途**: 防止模型遗忘关键信息，前端显示任务识别结果

### 2. Native Function Calling
- **实现**: LLM 原生支持的工具调用机制
- **工具注册**: ToolRegistry 统一管理
- **工具列表**: web_search, python_executor, calculator, ocr, etc.
- **优势**: 无需 embedding 匹配，LLM 直接选择工具

### 3. Critic 机制
- **位置**: SpecializedAgent 内部
- **评估标准**:
  1. 法条引用缺失 → 不通过
  2. 不确定表述 → 不通过
  3. 分析结构缺失 → 不通过
  4. 信息不完整 → 不通过
  5. 格式不规范 → 不通过
- **改进流程**: 评估不通过 → 生成改进搜索词 → 重新搜索 → 重新生成 → 再次评估

### 4. SOP (Standard Operating Procedure)
- **作用**: 为不同领域注入特定的思维模型
- **示例**:
  - Criminal_Law: 犯罪构成分析 → 罪名辨析 → 量刑情节 → 法条依据
  - Family_Law: 法律关系梳理 → 争议焦点 → 请求权基础 → 利益平衡
- **实现**: 通过 prompt 模板注入到 SpecializedAgent 的 system_prompt

### 5. 复合搜索词生成
- **策略**: Query Transformation
- **格式**: `核心法律概念 + 用户具体场景关键词 + 规定/法条`
- **示例**: "离婚登记 材料 女方户口本 娘家 民法典 规定"
- **优势**: 获取实务解读而非仅法条原文

## 数据流

```
User Input
    ↓
CoreAgent (识别 + 路由)
    ↓
SpecializedAgent (执行 + 评估)
    ↓
Tools (web_search, python_executor, etc.)
    ↓
SpecializedAgent (整合结果)
    ↓
Critic (评估)
    ↓ (如果不通过)
重新搜索 + 重新生成
    ↓
最终结果
    ↓
Frontend (显示)
```

## 状态管理

### Agent 状态
- `IDLE`: 空闲状态
- `RUNNING`: 执行中
- `FINISHED`: 完成

### 状态转换
```
IDLE → RUNNING (开始执行)
    ↓
RUNNING → FINISHED (生成最终回答)
    ↓
FINISHED → IDLE (清理完成)
```

## 错误处理

1. **识别失败**: 默认使用 Family_Law + QA_Retrieval
2. **工具执行失败**: 返回错误信息，继续执行
3. **评估失败**: 默认认为结果可接受
4. **达到最大步数**: 强制生成最终答案
5. **达到最大Critic轮数**: 返回当前结果

## 性能优化

1. **状态重置**: 每次执行前确保状态为 IDLE
2. **资源清理**: 执行完成后清理工具资源
3. **上下文窗口**: 限制 recent_messages 数量 (30条)
4. **最大步数**: 限制 ReAct 循环步数 (5步)
5. **Critic轮数**: 限制评估和重新搜索轮数 (2轮)

