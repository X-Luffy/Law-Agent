#!/usr/bin/env python
"""运行评估脚本"""
import asyncio
import argparse
import sys
import os
from pathlib import Path

# 获取脚本所在目录的父目录（项目根目录）
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.absolute()

# 确保项目根目录在sys.path的最前面（必须在所有导入之前）
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 切换到项目根目录
os.chdir(project_root)

# 使用绝对导入（从项目根目录开始）
from eval.evaluator import Evaluator
from config.config import Config


async def main():
    parser = argparse.ArgumentParser(description='法律多智能体问答系统评估')
    parser.add_argument(
        '--data_path',
        type=str,
        default='data/test_example/zixun_gpt4.json',
        help='测试数据文件路径'
    )
    parser.add_argument(
        '--max_cases',
        type=int,
        default=50,
        help='最大评估用例数（默认50）'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='eval/results.json',
        help='结果输出路径'
    )
    parser.add_argument(
        '--target_only',
        action='store_true',
        help='只运行Target System，跳过Baseline A和Baseline B'
    )
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建评估器
    config = Config()
    evaluator = Evaluator(config=config, target_only=args.target_only)
    
    # 执行评估
    results = await evaluator.evaluate(
        data_path=args.data_path,
        max_cases=args.max_cases
    )
    
    # 保存结果
    evaluator.save_results(results, str(output_path))
    
    # 打印报告
    evaluator.print_report(results["summary"])


if __name__ == "__main__":
    asyncio.run(main())
