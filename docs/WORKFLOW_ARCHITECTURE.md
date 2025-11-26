# Workflow架构文档

## 概述

Workflow模块为每种法律任务类型提供了专门的处理流程，实现了模块化和可扩展的架构设计。

## 架构设计

```
SpecializedAgent
    ↓
识别意图 (LegalIntent)
    ↓
选择对应的Workflow
    ├── QARetrievalWorkflow
    ├── CaseAnalysisWorkflow
    ├── DocDraftingWorkflow
    ├── CalculationWorkflow
    ├── ReviewContractWorkflow
    └── ClarificationWorkflow
```

## BaseWorkflow (基类)

所有Workflow都继承自`BaseWorkflow`，提供统一的接口：

```python
class BaseWorkflow(ABC):
    def __init__(self, agent: Optional[Agent] = None, config: Optional[Config] = None)
    
    @abstractmethod
    async def execute(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> str
```

## 各Workflow详细说明

### 1. QARetrievalWorkflow (QA检索Workflow)

**用途**：处理法律法规、法条、类似案例查询

**执行流程**：
1. **提取关键词** (`extract_keywords`)
   - 从用户消息中提取关键信息
   - 使用LLM或NLP工具进行关键词提取

2. **RAG搜索知识库** (`search_knowledge_base`)
   - 将关键词转换为embedding向量
   - 在向量数据库中搜索相似文档
   - 返回相关文档片段

3. **生成回答** (`generate_answer`)
   - 将检索到的文档作为上下文
   - 使用LLM生成基于文档的回答
   - 确保回答准确，避免幻觉

**示例**：
```python
workflow = QARetrievalWorkflow(agent=agent, config=config)
result = await workflow.execute("劳动合同法关于试用期的规定是什么？")
```

### 2. CaseAnalysisWorkflow (案情分析Workflow)

**用途**：处理用户描述的案情故事，进行多轮追问并匹配法律

**执行流程**：
1. **多轮追问机制** (`identify_missing_info`, `ask_clarification`)
   - 分析已收集的信息
   - 识别缺失的关键信息（时间、地点、当事人、事件经过等）
   - 生成友好的追问问题

2. **总结案情** (`summarize_case`)
   - 整理收集到的所有信息
   - 生成结构化的案情描述

3. **法律匹配** (`match_laws`)
   - 分析案情要点
   - 在知识库中搜索相关法条
   - 返回匹配的法条和适用性分析

**示例**：
```python
workflow = CaseAnalysisWorkflow(agent=agent, config=config, max_rounds=5)
result = await workflow.execute("我被公司开除了，没有提前通知")
```

### 3. DocDraftingWorkflow (起草文书Workflow)

**用途**：处理合同、起诉状、律师函等文书的起草

**执行流程**：
1. **识别文书类型** (`identify_doc_type`)
   - 使用LLM识别用户想要起草的文书类型

2. **提取填充字段** (`extract_slots`)
   - 从用户消息中提取所需字段
   - 例如：合同需要甲方、乙方、标的、金额、期限等

3. **检查必填字段** (`identify_missing_slots`)
   - 根据文书类型检查必填字段
   - 如果缺少，返回追问消息

4. **加载模板** (`load_template`)
   - 从模板库中加载对应类型的模板

5. **填充模板** (`fill_template`)
   - 将字段值填充到模板中
   - 生成最终文书

**示例**：
```python
workflow = DocDraftingWorkflow(agent=agent, config=config)
result = await workflow.execute("帮我起草一份劳动合同，甲方是XX公司，乙方是张三")
```

### 4. CalculationWorkflow (计算Workflow)

**用途**：处理赔偿金、刑期、诉讼费等计算

**执行流程**：
1. **识别计算类型** (`identify_calculation_type`)
   - 识别是赔偿金、刑期还是诉讼费计算

2. **提取计算参数** (`extract_parameters`)
   - 从用户消息中提取计算所需的参数
   - 例如：工资、工作年限、赔偿标准等

3. **检查必需参数** (`identify_missing_parameters`)
   - 根据计算类型检查必需参数

4. **构建计算公式** (`build_calculation_formula`)
   - 根据计算类型和参数生成Python计算代码

5. **执行计算** (`execute_calculation`)
   - 调用Python执行工具执行计算

6. **格式化结果** (`format_result`)
   - 将计算结果格式化为友好的文本

**示例**：
```python
workflow = CalculationWorkflow(agent=agent, config=config)
result = await workflow.execute("我月薪10000，工作了3年，被裁员应该得到多少赔偿？")
```

### 5. ReviewContractWorkflow (审查合同Workflow)

**用途**：处理合同风险审查

**执行流程**：
1. **提取合同文本** (`extract_contract_text`)
   - 从用户消息或上下文中提取合同文本
   - 如果是文件路径，读取文件
   - 如果是PDF/图片，使用OCR解析

2. **解析合同结构** (`parse_contract_structure`)
   - 识别合同类型
   - 提取主要条款
   - 提取关键信息（当事人、标的、金额、期限等）

3. **识别风险点** (`identify_risk_points`)
   - 检查常见风险点（违约责任、争议解决、保密条款等）
   - 比对标准合同模板
   - 识别缺失的关键条款
   - 识别不公平条款

4. **生成审查报告** (`generate_review_report`)
   - 生成结构化的审查报告
   - 包含合同基本信息、风险点列表及建议、总体评价

**示例**：
```python
workflow = ReviewContractWorkflow(agent=agent, config=config)
result = await workflow.execute("请审查这份劳动合同", context={"file_path": "contract.pdf"})
```

### 6. ClarificationWorkflow (澄清Workflow)

**用途**：处理信息不足的情况，生成反问句

**执行流程**：
1. **识别缺失信息** (`identify_missing_info`)
   - 分析用户消息和上下文
   - 识别缺失的关键信息

2. **生成澄清问题** (`generate_clarification_questions`)
   - 将缺失信息组织成友好的反问句
   - 根据重要性排序问题

**示例**：
```python
workflow = ClarificationWorkflow(agent=agent, config=config)
result = await workflow.execute("我想起草合同")
```

## 使用方式

### 在SpecializedAgent中使用

`SpecializedAgent`已经集成了所有Workflow，会根据识别的意图自动调用对应的Workflow：

```python
# SpecializedAgent会自动根据意图选择Workflow
agent = SpecializedAgent(domain=LegalDomain.LABOR_LAW, config=config)
response = await agent.process_message("劳动合同法关于试用期的规定是什么？")
```

### 直接使用Workflow

也可以直接使用Workflow：

```python
from Agent.workflow import QARetrievalWorkflow

workflow = QARetrievalWorkflow(agent=agent, config=config)
result = await workflow.execute("劳动合同法关于试用期的规定是什么？")
```

## 扩展性

### 添加新的Workflow

1. 创建新的Workflow类，继承`BaseWorkflow`
2. 实现`execute`方法
3. 在`SpecializedAgent`中注册新的Workflow
4. 在`LegalIntent`枚举中添加新的意图类型

### 自定义Workflow行为

每个Workflow的方法都可以独立实现和扩展，互不影响。可以根据具体需求：
- 调整执行流程
- 添加新的处理步骤
- 集成新的工具或服务

## 待实现功能

当前所有Workflow的方法都使用`pass`占位，需要后续实现：

1. **关键词提取和RAG检索**：实现向量搜索和文档检索
2. **多轮对话管理**：实现状态管理和上下文维护
3. **模板管理**：实现模板库和字段映射
4. **公式生成**：实现各种法律计算的公式库
5. **OCR和文档解析**：实现文件处理和文本提取
6. **风险点知识库**：构建合同风险点知识库

