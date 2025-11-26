# 评估模块使用说明

## 概述

本评估模块实现了法律多智能体问答系统的完整评估策略，包括三个Baseline的对比评估。

## 评估策略

### 三个被测对象

1. **Baseline A: Raw Model (裸模型)**
   - 无工具，无System Prompt
   - 用于证明Web Search工具的必要性

2. **Baseline B: Naive Agent (单步搜索)**
   - Qwen + Bocha Web Search
   - 简单的Retrieve -> Generate流程
   - 用于证明Multi-Agent架构的优越性

3. **Target System: Multi-Agent Refinement System**
   - Router -> Specialist Agent + Bocha -> Critic -> Final Answer
   - 完整的多Agent架构

### 评估维度

#### 维度一：端到端效果评估 (Effectiveness)
- **法条命中率 (Law Citation Recall)**: 回答中引用的法条与标准答案的重合程度
- **幻觉/错误引用率 (False Citation Rate)**: 引用的法条是否存在或正确

#### 维度二：系统性能评估 (System Architecture)
- **回答完整性与逻辑深度**: 使用LLM-as-a-Judge评估
- **反思机制有效性**: 统计Critic触发后的质量提升
- **领域路由准确率**: Core Agent路由的准确性

## 使用方法

### 基本使用

**运行评估脚本**

```bash
# 激活conda环境（如果需要）
source /home/mnt/xieqinghongbing/env/open_manus/bin/activate

# 设置PYTHONPATH（确保项目根目录在路径中）
export PYTHONPATH=/home/mnt/xieqinghongbing/code/xiazhaoyuan/Agent:$PYTHONPATH

# 运行评估脚本
python eval/run_eval.py --data_path data/test_example/zixun_gpt4.json --max_cases 50

# 或者使用 -m 方式运行
python -m eval.run_eval --data_path data/test_example/zixun_gpt4.json --max_cases 50
```

**参数说明**：

### 参数说明

- `--data_path`: 测试数据文件路径（默认: `data/test_example/zixun_gpt4.json`）
- `--max_cases`: 最大评估用例数（默认: 50）
- `--output`: 结果输出路径（默认: `eval/results.json`）

### 测试数据格式

测试数据应为JSON格式，包含以下字段：

```json
[
  {
    "query": "用户问题",
    "laws": ["法条1", "法条2", ...],
    "response": "标准答案"
  },
  ...
]
```

## 输出结果

评估结果会保存为JSON文件，包含：

1. **summary**: 统计摘要
   - 各Baseline的平均指标
   - 对比分析结果

2. **case_results**: 每个用例的详细结果
   - 各Baseline的回答
   - 法条提取结果
   - 评估指标

3. **raw_results**: 原始数据
   - 所有指标的原始列表

## 评估报告

运行完成后，会在控制台打印评估报告，包括：

- Baseline A vs Target System 的对比
- Baseline B vs Target System 的对比
- 各项指标的统计结果

