"""评估器主类"""
import json
import asyncio
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# 处理导入：优先使用相对导入，失败时使用绝对导入
try:
    from .baselines import BaselineA, BaselineB
    from .utils import extract_laws, calculate_recall, check_false_citation, llm_judge
    from ..flow.legal_flow import LegalFlow
    from ..agent.core_agent import CoreAgent
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，尝试绝对导入
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from eval.baselines import BaselineA, BaselineB
    from eval.utils import extract_laws, calculate_recall, check_false_citation, llm_judge
    from flow.legal_flow import LegalFlow
    from agent.core_agent import CoreAgent
    from config.config import Config


class Evaluator:
    """评估器类，实现完整的评估流程"""
    
    def __init__(self, config: Optional[Config] = None, target_only: bool = False):
        self.config = config or Config()
        self.target_only = target_only  # 是否只运行Target System
        
        if not self.target_only:
            # 只有在非target_only模式下才初始化Baseline
            self.baseline_a = BaselineA(self.config)
            self.baseline_b = BaselineB(self.config)
        else:
            self.baseline_a = None
            self.baseline_b = None
        
        # 初始化Target System
        self.core_agent = CoreAgent(config=self.config)
        self.target_system = LegalFlow(core_agent=self.core_agent, config=self.config)
        
        # 结果容器
        self.results = {
            "baseline_a": {
                "recall": [],
                "false_citation_rate": [],
                "answers": []
            },
            "baseline_b": {
                "score": [],
                "answers": []
            },
            "target_system": {
                "recall": [],
                "false_citation_rate": [],
                "score": [],
                "routing_correct": [],
                "reflection_triggered": 0,
                "answers": []
            }
        }
    
    def load_test_data(self, data_path: str) -> List[Dict[str, Any]]:
        """
        加载测试数据
        
        Args:
            data_path: 测试数据文件路径
            
        Returns:
            测试数据列表
        """
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 如果数据是列表，直接返回；如果是字典，提取列表
        if isinstance(data, dict):
            # 尝试从常见字段中提取
            if 'data' in data:
                data = data['data']
            elif 'test' in data:
                data = data['test']
            else:
                # 如果只有一个键，可能是数据本身
                keys = list(data.keys())
                if len(keys) == 1:
                    data = data[keys[0]]
        
        return data if isinstance(data, list) else [data]
    
    async def evaluate_single_case(
        self,
        case: Dict[str, Any],
        case_index: int,
        total_cases: int
    ) -> Dict[str, Any]:
        """
        评估单个测试用例
        
        Args:
            case: 测试用例
            case_index: 用例索引
            total_cases: 总用例数
            
        Returns:
            评估结果
        """
        query = case.get('query', '')
        ground_truth_laws = case.get('laws', [])
        ground_truth_response = case.get('response', '')
        
        print(f"\n[{case_index + 1}/{total_cases}] 评估用例: {query[:50]}...")
        
        case_result = {
            "query": query,
            "ground_truth_laws": ground_truth_laws,
            "baseline_a": {},
            "baseline_b": {},
            "target_system": {}
        }
        
        step_num = 1
        total_steps = 3 if not self.target_only else 1
        
        # 1. 运行 Baseline A（如果启用）
        if not self.target_only:
            print(f"  [{step_num}/{total_steps}] 运行 Baseline A (Raw Model)...")
            step_num += 1
            try:
                res_a = await self.baseline_a.run(query)
                laws_a = extract_laws(res_a)
                recall_a = calculate_recall(laws_a, ground_truth_laws)
                false_rate_a = check_false_citation(laws_a)
                
                case_result["baseline_a"] = {
                    "answer": res_a,
                    "laws": laws_a,
                    "recall": recall_a,
                    "false_citation_rate": false_rate_a
                }
                
                self.results["baseline_a"]["recall"].append(recall_a)
                self.results["baseline_a"]["false_citation_rate"].append(false_rate_a)
                self.results["baseline_a"]["answers"].append(res_a)
                
                print(f"    法条命中率: {recall_a:.2%}, 错误引用率: {false_rate_a:.2%}")
            except Exception as e:
                print(f"    Error: {e}")
                case_result["baseline_a"] = {"error": str(e)}
            
            # 2. 运行 Baseline B
            print(f"  [{step_num}/{total_steps}] 运行 Baseline B (Naive Agent)...")
            step_num += 1
            try:
                res_b = await self.baseline_b.run(query)
                case_result["baseline_b"] = {
                    "answer": res_b
                }
                self.results["baseline_b"]["answers"].append(res_b)
            except Exception as e:
                print(f"    Error: {e}")
                case_result["baseline_b"] = {"error": str(e)}
        
        # 3. 运行 Target System
        print(f"  [{step_num}/{total_steps}] 运行 Target System (Multi-Agent)...")
        try:
            # 重置Agent状态
            self.core_agent.state = self.core_agent.state.__class__.IDLE
            self.core_agent.current_step = 0
            
            res_target = await self.target_system.execute(query)
            laws_target = extract_laws(res_target)
            recall_target = calculate_recall(laws_target, ground_truth_laws)
            false_rate_target = check_false_citation(laws_target)
            
            # 获取路由信息（从state_memory）
            routing_info = "未知"
            if hasattr(self.core_agent, 'state_memory'):
                state_memory = self.core_agent.state_memory.get()
                domain = state_memory.get("domain", "未知")
                routing_info = domain
            
            # 检查是否触发了反思机制（简化：检查是否有多次think-act循环）
            reflection_triggered = self.core_agent.current_step > 2  # 如果步骤数>2，可能触发了反思
            
            case_result["target_system"] = {
                "answer": res_target,
                "laws": laws_target,
                "recall": recall_target,
                "false_citation_rate": false_rate_target,
                "routing": routing_info,
                "reflection_triggered": reflection_triggered,
                "steps": self.core_agent.current_step
            }
            
            self.results["target_system"]["recall"].append(recall_target)
            self.results["target_system"]["false_citation_rate"].append(false_rate_target)
            self.results["target_system"]["answers"].append(res_target)
            if reflection_triggered:
                self.results["target_system"]["reflection_triggered"] += 1
            
            print(f"    法条命中率: {recall_target:.2%}, 错误引用率: {false_rate_target:.2%}")
            print(f"    路由: {routing_info}, 反思触发: {reflection_triggered}")
        except Exception as e:
            print(f"    Error: {e}")
            case_result["target_system"] = {"error": str(e)}
        
        # 4. LLM Judge 比较 Baseline B 和 Target System（如果启用）
        if not self.target_only and case_result["baseline_b"].get("answer") and case_result["target_system"].get("answer"):
            print(f"  [{step_num + 1}/{step_num + 1}] LLM Judge 评估...")
            try:
                comparison = await llm_judge(
                    query=query,
                    answer_a=case_result["baseline_b"]["answer"],
                    answer_b=case_result["target_system"]["answer"],
                    ground_truth=ground_truth_response,
                    config=self.config
                )
                
                case_result["comparison"] = comparison
                self.results["baseline_b"]["score"].append(comparison["baseline_b_score"])
                self.results["target_system"]["score"].append(comparison["target_system_score"])
                
                print(f"    Baseline B 得分: {comparison['baseline_b_score']:.1f}/10")
                print(f"    Target System 得分: {comparison['target_system_score']:.1f}/10")
                print(f"    胜者: {comparison['winner']}")
            except Exception as e:
                print(f"    LLM Judge Error: {e}")
        
        return case_result
    
    async def evaluate(
        self,
        data_path: str,
        max_cases: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行完整评估
        
        Args:
            data_path: 测试数据文件路径
            max_cases: 最大评估用例数（None表示全部）
            
        Returns:
            评估结果
        """
        print("=" * 60)
        print("开始评估")
        print("=" * 60)
        
        # 加载测试数据
        print(f"\n加载测试数据: {data_path}")
        test_data = self.load_test_data(data_path)
        
        if max_cases:
            test_data = test_data[:max_cases]
        
        print(f"测试用例数: {len(test_data)}")
        
        # 评估每个用例
        case_results = []
        for i, case in enumerate(test_data):
            try:
                result = await self.evaluate_single_case(case, i, len(test_data))
                case_results.append(result)
            except Exception as e:
                print(f"评估用例 {i+1} 时出错: {e}")
                continue
        
        # 计算统计指标
        summary = self._calculate_summary()
        
        # 构建最终结果
        final_results = {
            "summary": summary,
            "case_results": case_results,
            "raw_results": self.results
        }
        
        return final_results
    
    def _calculate_summary(self) -> Dict[str, Any]:
        """计算统计摘要"""
        summary = {}
        
        # Baseline A 统计
        if self.results["baseline_a"]["recall"]:
            summary["baseline_a"] = {
                "avg_recall": sum(self.results["baseline_a"]["recall"]) / len(self.results["baseline_a"]["recall"]),
                "avg_false_citation_rate": sum(self.results["baseline_a"]["false_citation_rate"]) / len(self.results["baseline_a"]["false_citation_rate"]),
                "total_cases": len(self.results["baseline_a"]["recall"])
            }
        
        # Baseline B 统计
        if self.results["baseline_b"]["score"]:
            summary["baseline_b"] = {
                "avg_score": sum(self.results["baseline_b"]["score"]) / len(self.results["baseline_b"]["score"]),
                "total_cases": len(self.results["baseline_b"]["score"])
            }
        
        # Target System 统计
        if self.results["target_system"]["recall"]:
            summary["target_system"] = {
                "avg_recall": sum(self.results["target_system"]["recall"]) / len(self.results["target_system"]["recall"]),
                "avg_false_citation_rate": sum(self.results["target_system"]["false_citation_rate"]) / len(self.results["target_system"]["false_citation_rate"]),
                "avg_score": sum(self.results["target_system"]["score"]) / len(self.results["target_system"]["score"]) if self.results["target_system"]["score"] else 0,
                "reflection_triggered_count": self.results["target_system"]["reflection_triggered"],
                "reflection_triggered_rate": self.results["target_system"]["reflection_triggered"] / len(self.results["target_system"]["recall"]) if self.results["target_system"]["recall"] else 0,
                "total_cases": len(self.results["target_system"]["recall"])
            }
        
        # 对比分析
        if summary.get("baseline_a") and summary.get("target_system"):
            summary["comparison_a_vs_target"] = {
                "recall_improvement": summary["target_system"]["avg_recall"] - summary["baseline_a"]["avg_recall"],
                "false_citation_reduction": summary["baseline_a"]["avg_false_citation_rate"] - summary["target_system"]["avg_false_citation_rate"]
            }
        
        if summary.get("baseline_b") and summary.get("target_system"):
            summary["comparison_b_vs_target"] = {
                "score_improvement": summary["target_system"]["avg_score"] - summary["baseline_b"]["avg_score"],
                "win_rate": sum(1 for s_t, s_b in zip(self.results["target_system"]["score"], self.results["baseline_b"]["score"]) if s_t > s_b) / len(self.results["target_system"]["score"]) if self.results["target_system"]["score"] else 0
            }
        
        return summary
    
    def save_results(self, results: Dict[str, Any], output_path: str):
        """保存评估结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n评估结果已保存到: {output_path}")
    
    def print_report(self, summary: Dict[str, Any]):
        """打印评估报告"""
        print("\n" + "=" * 60)
        print("评估报告")
        print("=" * 60)
        
        # Baseline A vs Target System
        if "baseline_a" in summary and "target_system" in summary:
            print("\n【维度一：端到端效果评估 (Effectiveness)】")
            print(f"Baseline A (Raw Model):")
            print(f"  - 平均法条命中率: {summary['baseline_a']['avg_recall']:.2%}")
            print(f"  - 平均错误引用率: {summary['baseline_a']['avg_false_citation_rate']:.2%}")
            print(f"\nTarget System (Multi-Agent):")
            print(f"  - 平均法条命中率: {summary['target_system']['avg_recall']:.2%}")
            print(f"  - 平均错误引用率: {summary['target_system']['avg_false_citation_rate']:.2%}")
            
            if "comparison_a_vs_target" in summary:
                comp = summary["comparison_a_vs_target"]
                print(f"\n对比分析:")
                print(f"  - 法条命中率提升: {comp['recall_improvement']:.2%}")
                print(f"  - 错误引用率降低: {comp['false_citation_reduction']:.2%}")
        
        # Baseline B vs Target System
        if "baseline_b" in summary and "target_system" in summary:
            print("\n【维度二：系统性能评估 (System Architecture)】")
            print(f"Baseline B (Naive Agent):")
            print(f"  - 平均得分: {summary['baseline_b']['avg_score']:.2f}/10")
            print(f"\nTarget System (Multi-Agent):")
            print(f"  - 平均得分: {summary['target_system']['avg_score']:.2f}/10")
            print(f"  - 反思机制触发次数: {summary['target_system']['reflection_triggered_count']}")
            print(f"  - 反思机制触发率: {summary['target_system']['reflection_triggered_rate']:.2%}")
            
            if "comparison_b_vs_target" in summary:
                comp = summary["comparison_b_vs_target"]
                print(f"\n对比分析:")
                print(f"  - 得分提升: {comp['score_improvement']:.2f}分")
                print(f"  - 胜率: {comp['win_rate']:.2%}")
        
        print("\n" + "=" * 60)
