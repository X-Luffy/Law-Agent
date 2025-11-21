"""Agent系统主入口"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from agent.agent import Agent


def main():
    """主函数"""
    # 初始化配置
    config = Config()
    
    # 创建Agent实例
    agent = Agent(config)
    
    # 示例：交互式对话
    print("Agent系统已启动，输入'exit'退出")
    print("-" * 50)
    
    while True:
        user_input = input("\n用户: ")
        
        if user_input.lower() in ['exit', 'quit', '退出']:
            print("再见！")
            break
        
        # 处理用户消息
        import asyncio
        response = asyncio.run(agent.process_message(user_input))
        
        print(f"\nAgent: {response}")


if __name__ == "__main__":
    main()

