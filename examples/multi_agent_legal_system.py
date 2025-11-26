"""多Agent法律系统使用示例"""
import asyncio
from Agent.config.config import Config
from Agent.agent.core_agent import CoreAgent
from Agent.schema import LegalDomain


async def main():
    """主函数：演示多Agent法律系统的使用"""
    
    # 初始化配置
    config = Config()
    
    # 创建核心Agent
    core_agent = CoreAgent(
        name="legal_core_agent",
        config=config
    )
    
    # 示例1: 劳动法问题
    print("=" * 60)
    print("示例1: 劳动法问题")
    print("=" * 60)
    user_message1 = "公司要裁员，我应该得到多少赔偿？"
    print(f"用户: {user_message1}")
    response1 = await core_agent.process_message(user_message1)
    print(f"Agent: {response1}\n")
    
    # 示例2: 婚姻家事问题
    print("=" * 60)
    print("示例2: 婚姻家事问题")
    print("=" * 60)
    user_message2 = "我想离婚，孩子的抚养权怎么判？"
    print(f"用户: {user_message2}")
    response2 = await core_agent.process_message(user_message2)
    print(f"Agent: {response2}\n")
    
    # 示例3: 合同纠纷问题
    print("=" * 60)
    print("示例3: 合同纠纷问题")
    print("=" * 60)
    user_message3 = "对方违约了，我应该怎么办？"
    print(f"用户: {user_message3}")
    response3 = await core_agent.process_message(user_message3)
    print(f"Agent: {response3}\n")
    
    # 示例4: 非法律问题（应该被引导）
    print("=" * 60)
    print("示例4: 非法律问题（应该被引导）")
    print("=" * 60)
    user_message4 = "今天天气怎么样？"
    print(f"用户: {user_message4}")
    response4 = await core_agent.process_message(user_message4)
    print(f"Agent: {response4}\n")
    
    # 示例5: 程序性问题
    print("=" * 60)
    print("示例5: 程序性问题")
    print("=" * 60)
    user_message5 = "我应该去哪个法院起诉？诉讼费要多少？"
    print(f"用户: {user_message5}")
    response5 = await core_agent.process_message(user_message5)
    print(f"Agent: {response5}\n")


if __name__ == "__main__":
    asyncio.run(main())

