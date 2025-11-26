# 多Agent法律系统架构文档

## 概述

本系统采用多Agent架构，通过核心Agent（CoreAgent）进行领域分类和路由，将用户问题分配给对应的专业子Agent（SpecializedAgent）进行处理。

## 系统架构

```
用户问题
    ↓
CoreAgent (核心路由Agent)
    ├── 领域分类 (LegalDomain)
    │   ├── Labor_Law (劳动法)
    │   ├── Family_Law (婚姻家事)
    │   ├── Contract_Law (合同纠纷)
    │   ├── Corporate_Law (公司法)
    │   ├── Criminal_Law (刑法)
    │   ├── Procedural_Query (程序性问题)
    │   └── Non_Legal (非法律问题)
    │
    └── 路由到对应的 SpecializedAgent
            ↓
        SpecializedAgent (专业领域Agent)
            ├── 意图识别 (LegalIntent)
            │   ├── QA_Retrieval (法律法规查询)
            │   ├── Case_Analysis (案情分析)
            │   ├── Doc_Drafting (起草文书)
            │   ├── Calculation (计算)
            │   ├── Review_Contract (审查合同)
            │   └── Clarification (澄清)
            │
            └── 调用相应的处理方法
```

## 核心组件

### 1. CoreAgent (核心Agent)

**职责**：
- 分析用户问题所属的法律领域
- 将问题路由到对应的专业子Agent
- 处理非法律问题，引导用户询问法律相关问题

**主要方法**：
- `classify_domain(user_message: str) -> LegalDomain`: 分类用户问题所属的法律领域
- `route_to_sub_agent(domain: LegalDomain, user_message: str) -> str`: 将问题路由到对应的子Agent
- `handle_non_legal_query(user_message: str) -> str`: 处理非法律问题
- `get_or_create_sub_agent(domain: LegalDomain) -> Agent`: 获取或创建对应的子Agent

### 2. SpecializedAgent (专业领域Agent)

**职责**：
- 识别用户的法律专业意图
- 根据意图类型调用相应的处理方法

**支持的领域**：
- `Labor_Law`: 劳动法（裁员、工资）
- `Family_Law`: 婚姻家事（离婚、抚养权）
- `Contract_Law`: 合同纠纷
- `Corporate_Law`: 公司法
- `Criminal_Law`: 刑法
- `Procedural_Query`: 程序性问题

**支持的意图类型**：
- `QA_Retrieval`: 法律法规、法条、类似案例查询
  - 处理流程：提取关键词 -> 调用 RAG (搜索知识库) -> 生成回答
- `Case_Analysis`: 案情分析（用户描述了一个故事）
  - 处理流程：启动多轮追问机制 -> 总结案情 -> 法律匹配
- `Doc_Drafting`: 起草文书（合同、起诉状、律师函）
  - 处理流程：提取填充字段 (Slot Filling) -> 调用模板生成工具
- `Calculation`: 计算赔偿金、刑期、诉讼费
  - 处理流程：提取数值 -> 调用计算器工具 (Python)
- `Review_Contract`: 审查合同风险
  - 处理流程：上传文件 -> OCR/解析 -> 风险点比对
- `Clarification`: 信息不足，需要反问
  - 处理流程：暂停执行，生成反问句

**主要方法**：
- `recognize_legal_intent(user_message: str) -> LegalIntent`: 识别法律专业意图
- `handle_qa_retrieval(user_message: str) -> str`: 处理QA检索意图
- `handle_case_analysis(user_message: str) -> str`: 处理案情分析意图
- `handle_doc_drafting(user_message: str) -> str`: 处理起草文书意图
- `handle_calculation(user_message: str) -> str`: 处理计算意图
- `handle_review_contract(user_message: str) -> str`: 处理审查合同意图
- `handle_clarification(user_message: str) -> str`: 处理澄清意图

### 3. LegalIntentRecognizer (法律意图识别器)

**职责**：
- 识别用户的法律专业意图

**实现方式**：
- 使用LLM进行意图识别
- 可以结合规则匹配进行快速识别

## 使用示例

```python
import asyncio
from Agent.config.config import Config
from Agent.agent.core_agent import CoreAgent

async def main():
    # 初始化配置
    config = Config()
    
    # 创建核心Agent
    core_agent = CoreAgent(
        name="legal_core_agent",
        config=config
    )
    
    # 处理用户问题
    user_message = "公司要裁员，我应该得到多少赔偿？"
    response = await core_agent.process_message(user_message)
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## 工作流程

1. **用户提问** → CoreAgent接收问题
2. **领域分类** → CoreAgent分析问题所属的法律领域
3. **路由判断**：
   - 如果是非法律问题 → 引导用户询问法律相关问题
   - 如果是法律问题 → 路由到对应的SpecializedAgent
4. **意图识别** → SpecializedAgent识别用户的法律专业意图
5. **处理问题** → 根据意图类型调用相应的处理方法
6. **返回结果** → 将处理结果返回给用户

## Workflow模块

系统为每种任务类型创建了专门的Workflow，实现模块化和可扩展的处理流程：

### 1. QARetrievalWorkflow (QA检索Workflow)

**流程**：提取关键词 → RAG搜索 → 生成回答

**主要方法**：
- `extract_keywords()`: 提取关键词
- `search_knowledge_base()`: RAG搜索知识库
- `generate_answer()`: 基于检索结果生成回答

### 2. CaseAnalysisWorkflow (案情分析Workflow)

**流程**：多轮追问 → 总结案情 → 法律匹配

**主要方法**：
- `identify_missing_info()`: 识别缺失的关键信息
- `ask_clarification()`: 生成追问问题
- `summarize_case()`: 总结案情
- `match_laws()`: 匹配相关法律条文

### 3. DocDraftingWorkflow (起草文书Workflow)

**流程**：提取填充字段 (Slot Filling) → 调用模板生成工具

**主要方法**：
- `identify_doc_type()`: 识别文书类型
- `extract_slots()`: 提取填充字段
- `identify_missing_slots()`: 识别缺失的必填字段
- `load_template()`: 加载文书模板
- `fill_template()`: 填充模板

### 4. CalculationWorkflow (计算Workflow)

**流程**：提取数值 → 调用计算器工具

**主要方法**：
- `identify_calculation_type()`: 识别计算类型
- `extract_parameters()`: 提取计算参数
- `build_calculation_formula()`: 构建计算公式（Python代码）
- `execute_calculation()`: 执行计算
- `format_result()`: 格式化计算结果

### 5. ReviewContractWorkflow (审查合同Workflow)

**流程**：上传文件 → OCR/解析 → 风险点比对

**主要方法**：
- `extract_contract_text()`: 提取合同文本（OCR/解析）
- `parse_contract_structure()`: 解析合同结构
- `identify_risk_points()`: 识别风险点
- `generate_review_report()`: 生成审查报告

### 6. ClarificationWorkflow (澄清Workflow)

**流程**：生成反问句

**主要方法**：
- `identify_missing_info()`: 识别缺失的信息
- `generate_clarification_questions()`: 生成澄清问题

## 待实现功能

当前框架已搭建完成，以下功能使用 `pass` 或占位实现，需要后续完善：

1. **CoreAgent.classify_domain()**: 使用LLM进行领域分类
2. **CoreAgent.handle_non_legal_query()**: 生成引导回复
3. **LegalIntentRecognizer.recognize()**: 使用LLM或规则匹配识别意图
4. **各个Workflow的具体实现**：
   - QARetrievalWorkflow: RAG检索实现
   - CaseAnalysisWorkflow: 多轮追问和案情总结
   - DocDraftingWorkflow: 模板管理和字段填充
   - CalculationWorkflow: 计算公式生成和执行
   - ReviewContractWorkflow: OCR和风险点识别
   - ClarificationWorkflow: 智能反问生成

## 扩展性

系统设计具有良好的扩展性：

1. **新增法律领域**：在 `LegalDomain` 枚举中添加新领域，并在 `SpecializedAgent` 中添加对应的描述
2. **新增意图类型**：在 `LegalIntent` 枚举中添加新意图，并在 `SpecializedAgent` 中添加对应的处理方法
3. **自定义处理逻辑**：每个处理方法都可以独立实现，互不影响

