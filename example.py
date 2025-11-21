"""Agent系统使用示例"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from agent.agent import Agent


def example_basic_usage():
    """基本使用示例"""
    # 初始化配置
    config = Config()
    
    # 创建Agent实例
    agent = Agent(config)
    
    # 处理用户消息
    import asyncio
    user_message = "你好，请帮我搜索一下Python的最新版本信息"
    response = asyncio.run(agent.process_message(user_message))
    print(f"用户: {user_message}")
    print(f"Agent: {response}")
    print("-" * 50)


def example_multi_turn_conversation():
    """多轮对话示例"""
    import asyncio
    config = Config()
    agent = Agent(config)
    
    # 第一轮对话
    messages = [
        "我想了解机器学习",
        "具体来说，我想知道什么是深度学习",
        "深度学习有哪些应用？"
    ]
    
    for msg in messages:
        response = asyncio.run(agent.process_message(msg))
        print(f"用户: {msg}")
        print(f"Agent: {response}")
        print("-" * 50)
    
    # 重置会话
    agent.reset()
    print("会话已重置")


def example_with_tools():
    """使用工具的示例"""
    import asyncio
    config = Config()
    agent = Agent(config)
    
    # 需要Web搜索的消息
    messages = [
        "搜索一下今天的天气",
        "帮我执行这段Python代码：print('Hello, World!')",
        "计算 123 * 456 的结果"
    ]
    
    for msg in messages:
        response = asyncio.run(agent.process_message(msg))
        print(f"用户: {msg}")
        print(f"Agent: {response}")
        print("-" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("Agent系统使用示例")
    print("=" * 50)
    print("\n1. 基本使用示例:")
    example_basic_usage()
    
    print("\n2. 多轮对话示例:")
    example_multi_turn_conversation()
    
    print("\n3. 使用工具的示例:")
    example_with_tools()

