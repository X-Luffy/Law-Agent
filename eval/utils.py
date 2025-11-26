"""评估工具函数"""
import re
import json
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Optional, TYPE_CHECKING

# 注意：不要在这里导入 LLM 和 Config，避免循环导入
# 使用 TYPE_CHECKING 进行类型提示，实际导入在函数内部进行（延迟导入）


def extract_laws(text: str) -> List[str]:
    """
    从文本中提取法律条款引用
    
    Args:
        text: 待提取的文本
        
    Returns:
        提取到的法条列表，格式如 ["《民法典》第123条", "《刑法》第234条"]
    """
    # 法条引用模式：支持多种格式
    patterns = [
        r'《[^》]+》第\d+条',  # 《民法典》第123条
        r'《[^》]+》\s*第\d+条',  # 《民法典》 第123条
        r'《[^》]+》\s*第\d+款',  # 《民法典》 第123款
        r'《[^》]+》\s*第\d+项',  # 《民法典》 第123项
        r'《[^》]+》\s*第\d+章',  # 《民法典》 第123章
        r'《[^》]+》\s*第\d+节',  # 《民法典》 第123节
    ]
    
    laws = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        laws.extend(matches)
    
    # 去重并清理
    laws = list(set(laws))
    # 清理空白字符
    laws = [law.strip() for law in laws]
    
    return laws


def calculate_recall(predicted_laws: List[str], ground_truth_laws: List[str]) -> float:
    """
    计算法条命中率 (Recall)
    
    Args:
        predicted_laws: 预测的法条列表
        ground_truth_laws: 标准答案的法条列表
        
    Returns:
        Recall值 (0-1之间)
    """
    if not ground_truth_laws:
        return 0.0
    
    # 标准化法条格式（去除空格，统一格式）
    def normalize_law(law: str) -> str:
        # 去除空格，统一格式
        law = re.sub(r'\s+', '', law)
        return law
    
    predicted_set = {normalize_law(law) for law in predicted_laws}
    ground_truth_set = {normalize_law(law) for law in ground_truth_laws}
    
    # 计算交集
    intersection = predicted_set & ground_truth_set
    
    # Recall = 命中数 / 标准答案总数
    recall = len(intersection) / len(ground_truth_set) if ground_truth_set else 0.0
    
    return recall


def check_false_citation(predicted_laws: List[str]) -> float:
    """
    检查幻觉/错误引用率
    
    注意：这是一个简化的实现，实际应该与真实法条库比对
    这里只做基本的格式检查（如法条号是否合理）
    
    Args:
        predicted_laws: 预测的法条列表
        
    Returns:
        错误引用率 (0-1之间)
    """
    if not predicted_laws:
        return 0.0
    
    false_count = 0
    
    for law in predicted_laws:
        # 提取法条号
        match = re.search(r'第(\d+)条', law)
        if match:
            article_num = int(match.group(1))
            # 简单检查：法条号是否在合理范围内（1-10000）
            # 实际应该与真实法条库比对
            if article_num > 10000 or article_num < 1:
                false_count += 1
        else:
            # 无法提取法条号，可能是格式错误
            false_count += 1
    
    return false_count / len(predicted_laws) if predicted_laws else 0.0


async def llm_judge(
    query: str,
    answer_a: str,
    answer_b: str,
    ground_truth: Optional[str] = None,
    config: Optional[Any] = None
) -> Dict[str, Any]:
    """
    使用LLM作为Judge，比较两个答案的质量
    
    Args:
        query: 用户问题
        answer_a: 答案A（Baseline B）
        answer_b: 答案B（Target System）
        ground_truth: 标准答案（可选）
        config: 配置对象
        
    Returns:
        包含评分和比较结果的字典
    """
    # 延迟导入：在函数内部导入，避免循环导入
    # 优先尝试相对导入，失败则使用绝对导入
    try:
        from ..models.llm import LLM
        from ..config.config import Config
    except (ImportError, ValueError):
        # 如果相对导入失败，使用绝对导入
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from models.llm import LLM
        from config.config import Config
    
    if config is None:
        config = Config()
    
    llm = LLM(config)
    
    # 构建评估Prompt
    judge_prompt = f"""你是一个专业的法律问答评估专家。请比较以下两个回答的质量。

**用户问题**：
{query}

**回答A**：
{answer_a}

**回答B**：
{answer_b}
"""
    
    if ground_truth:
        judge_prompt += f"""

**标准答案（参考）**：
{ground_truth}
"""
    
    judge_prompt += """

请从以下维度评估两个回答：
1. **完整性**：是否全面回答了用户的问题，是否解决了潜在追问
2. **逻辑深度**：逻辑链条是否完整，推理是否严密
3. **准确性**：法条引用是否准确，内容是否正确
4. **可读性**：表达是否清晰易懂

请按照以下JSON格式返回评估结果：
{
    "answer_a_score": 分数(1-10),
    "answer_b_score": 分数(1-10),
    "winner": "A" 或 "B" 或 "tie",
    "reason": "评估理由"
}
"""
    
    try:
        # LLM.chat是同步方法，在异步函数中使用run_in_executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: llm.chat(
                messages=[{"role": "user", "content": judge_prompt}],
                system_prompt="你是一个专业的法律问答评估专家，请客观、公正地评估答案质量。",
                temperature=0.1,
                max_tokens=500
            )
        )
        
        # 解析JSON响应
        response = response.strip()
        if "```" in response:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        else:
            json_match = re.search(r'\{.*?\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
        
        result = json.loads(response)
        
        return {
            "baseline_b_score": result.get("answer_a_score", 5),
            "target_system_score": result.get("answer_b_score", 5),
            "winner": result.get("winner", "tie"),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"Warning: LLM Judge failed: {e}")
        # 返回默认值
        return {
            "baseline_b_score": 5,
            "target_system_score": 5,
            "winner": "tie",
            "reason": f"评估失败: {str(e)}"
        }
