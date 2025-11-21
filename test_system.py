"""系统端到端测试脚本"""
import sys
import os
import asyncio

# 添加项目根目录到路径（父目录，使Agent成为一个包）
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

# 确保可以导入模块
os.chdir(project_root)

# 使用绝对导入
from Agent.config.config import Config
from Agent.agent.agent import Agent


async def test_basic_conversation():
    """测试基本对话流程"""
    print("=" * 60)
    print("开始系统端到端测试")
    print("=" * 60)
    
    # 1. 初始化配置
    print("\n[1/6] 初始化配置...")
    try:
        config = Config()
        print(f"✅ 配置初始化成功")
        print(f"   - LLM模型: {config.llm_model}")
        print(f"   - Embedding模型: {config.embedding_model}")
        print(f"   - 向量数据库路径: {config.vector_db_path}")
        print(f"   - LLM超时: {config.llm_timeout}秒")
        print(f"   - Embedding超时: {config.embedding_timeout}秒")
        print(f"   - LLM最大重试: {config.llm_max_retries}次")
        print(f"   - Embedding最大重试: {config.embedding_max_retries}次")
    except Exception as e:
        print(f"❌ 配置初始化失败: {e}")
        return False
    
    # 2. 创建Agent实例
    print("\n[2/6] 创建Agent实例...")
    try:
        agent = Agent(
            name="test_agent",
            description="测试Agent",
            system_prompt="你是一个友好的AI助手，请简洁地回答用户的问题。",
            config=config
        )
        print(f"✅ Agent创建成功")
        print(f"   - Agent名称: {agent.name}")
        print(f"   - 工具数量: {len(agent.tool_manager.tools)}")
    except Exception as e:
        print(f"❌ Agent创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 测试简单对话（不需要工具）
    print("\n[3/6] 测试简单对话（问候）...")
    try:
        user_message = "你好，请介绍一下你自己"
        print(f"用户: {user_message}")
        
        response = await agent.process_message(user_message)
        print(f"Agent: {response}")
        print(f"✅ 简单对话测试成功")
    except Exception as e:
        print(f"❌ 简单对话测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. 测试意图识别
    print("\n[4/6] 测试意图识别...")
    try:
        test_messages = [
            "你好",
            "什么是合同法？",
            "帮我计算123+456",
            "再见"
        ]
        
        for msg in test_messages:
            intent = agent.intent_recognizer.recognize(
                msg,
                agent.state,
                []
            )
            print(f"   - '{msg}' -> 意图: {intent}")
        
        print(f"✅ 意图识别测试成功")
    except Exception as e:
        print(f"❌ 意图识别测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 测试记忆系统
    print("\n[5/6] 测试记忆系统...")
    try:
        # 测试短期记忆
        agent.update_memory("user", "测试消息1")
        agent.update_memory("assistant", "测试回复1")
        
        recent_messages = agent.memory.get_recent_messages(5)
        print(f"   - 短期记忆消息数: {len(recent_messages)}")
        
        # 测试长期记忆（向量数据库）
        memory_id = agent.memory_manager.vector_db.add_memory(
            content="这是一个测试记忆",
            metadata={"type": "test", "session_id": "test_session"}
        )
        print(f"   - 长期记忆ID: {memory_id}")
        
        # 搜索记忆
        results = agent.memory_manager.vector_db.search(
            query="测试记忆",
            top_k=1
        )
        print(f"   - 搜索到记忆数: {len(results)}")
        
        print(f"✅ 记忆系统测试成功")
    except Exception as e:
        print(f"❌ 记忆系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 6. 测试工具系统（如果可用）
    print("\n[6/6] 测试工具系统...")
    try:
        # 测试工具选择
        tool_descriptions = agent.tool_manager.get_all_tool_descriptions()
        print(f"   - 可用工具数: {len(tool_descriptions)}")
        for tool_name, desc in list(tool_descriptions.items())[:3]:
            print(f"     * {tool_name}: {desc[:50]}...")
        
        # 测试工具选择器
        selected_tools = agent.tool_selector.select_tools(
            "帮我计算123+456",
            context={},
            top_k=3
        )
        print(f"   - 工具选择结果: {selected_tools}")
        
        print(f"✅ 工具系统测试成功")
    except Exception as e:
        print(f"❌ 工具系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！系统运行正常")
    print("=" * 60)
    return True


async def test_query_with_tools():
    """测试带工具的查询"""
    print("\n" + "=" * 60)
    print("测试带工具的查询")
    print("=" * 60)
    
    try:
        config = Config()
        agent = Agent(
            name="test_agent",
            description="测试Agent",
            system_prompt="你是一个友好的AI助手，可以使用工具来帮助用户。",
            config=config
        )
        
        # 测试案例1：计算器工具
        print("\n[测试1] 计算器工具")
        print("-" * 40)
        user_message1 = "帮我计算123+456等于多少"
        print(f"用户: {user_message1}")
        response1 = await agent.process_message(user_message1)
        print(f"Agent: {response1}")
        
        # 测试案例2：Python执行工具
        print("\n[测试2] Python执行工具")
        print("-" * 40)
        user_message2 = "请用Python计算1到100的和"
        print(f"用户: {user_message2}")
        response2 = await agent.process_message(user_message2)
        print(f"Agent: {response2}")
        
        # 测试案例3：日期时间工具
        print("\n[测试3] 日期时间工具")
        print("-" * 40)
        user_message3 = "今天是几号？"
        print(f"用户: {user_message3}")
        response3 = await agent.process_message(user_message3)
        print(f"Agent: {response3}")
        
        print("\n✅ 带工具的查询测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 带工具的查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_legal_query():
    """测试法律条文查询（RAG检索）"""
    print("\n" + "=" * 60)
    print("测试法律条文查询（RAG检索）")
    print("=" * 60)
    
    try:
        config = Config()
        agent = Agent(
            name="legal_agent",
            description="法律助手Agent",
            system_prompt="你是一个专业的法律助手，可以检索法律条文并回答法律相关问题。",
            config=config
        )
        
        # 先添加一些法律文档到知识库（用于测试）
        print("\n[准备] 添加法律文档到知识库...")
        legal_documents = [
            "《合同法》第一条：为了保护合同当事人的合法权益，维护社会经济秩序，促进社会主义现代化建设，制定本法。",
            "《合同法》第二条：本法所称合同是平等主体的自然人、法人、其他组织之间设立、变更、终止民事权利义务关系的协议。",
            "《合同法》第三条：合同当事人的法律地位平等，一方不得将自己的意志强加给另一方。",
            "《合同法》第四条：当事人依法享有自愿订立合同的权利，任何单位和个人不得非法干预。",
            "《合同法》第五条：当事人应当遵循公平原则确定各方的权利和义务。",
            "《民法典》第一千零四十一条：婚姻家庭受国家保护。实行婚姻自由、一夫一妻、男女平等的婚姻制度。",
            "《民法典》第一千零四十二条：禁止包办、买卖婚姻和其他干涉婚姻自由的行为。禁止借婚姻索取财物。",
        ]
        
        metadatas = [
            {"law_type": "合同法", "chapter": "第一章", "article": "第一条"},
            {"law_type": "合同法", "chapter": "第一章", "article": "第二条"},
            {"law_type": "合同法", "chapter": "第一章", "article": "第三条"},
            {"law_type": "合同法", "chapter": "第一章", "article": "第四条"},
            {"law_type": "合同法", "chapter": "第一章", "article": "第五条"},
            {"law_type": "民法典", "chapter": "婚姻家庭编", "article": "第一千零四十一条"},
            {"law_type": "民法典", "chapter": "婚姻家庭编", "article": "第一千零四十二条"},
        ]
        
        agent.rag_manager.add_legal_documents(
            documents=legal_documents,
            metadatas=metadatas
        )
        print(f"✅ 已添加 {len(legal_documents)} 条法律文档")
        
        # 测试案例1：合同法相关查询
        print("\n[测试1] 合同法相关查询")
        print("-" * 40)
        user_message1 = "什么是合同？合同法的基本原则是什么？"
        print(f"用户: {user_message1}")
        response1 = await agent.process_message(user_message1)
        print(f"Agent: {response1}")
        
        # 检查是否为专业回答
        if agent.state.value == "professional_answer":
            print("✅ 已标记为专业回答（基于文档）")
        else:
            print("⚠️  未标记为专业回答")
        
        # 测试案例2：具体法条查询
        print("\n[测试2] 具体法条查询")
        print("-" * 40)
        user_message2 = "请告诉我合同法的第一条内容"
        print(f"用户: {user_message2}")
        response2 = await agent.process_message(user_message2)
        print(f"Agent: {response2}")
        
        # 测试案例3：民法典相关查询
        print("\n[测试3] 民法典相关查询")
        print("-" * 40)
        user_message3 = "婚姻家庭的基本原则是什么？"
        print(f"用户: {user_message3}")
        response3 = await agent.process_message(user_message3)
        print(f"Agent: {response3}")
        
        # 测试案例4：无法回答的情况
        print("\n[测试4] 无法回答的情况（测试幻觉避免）")
        print("-" * 40)
        user_message4 = "请告诉我刑法第一百条的内容"
        print(f"用户: {user_message4}")
        response4 = await agent.process_message(user_message4)
        print(f"Agent: {response4}")
        
        # 检查是否明确说明无法回答
        if "无法" in response4 or "未找到" in response4 or "抱歉" in response4:
            print("✅ 正确说明无法回答（避免幻觉）")
        else:
            print("⚠️  可能未明确说明无法回答")
        
        print("\n✅ 法律条文查询测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 法律条文查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_weather_query():
    """测试天气查询（实时信息）"""
    print("\n" + "=" * 60)
    print("测试天气查询（实时信息）")
    print("=" * 60)
    
    try:
        config = Config()
        agent = Agent(
            name="weather_agent",
            description="天气助手Agent",
            system_prompt="你是一个友好的AI助手，可以帮助用户查询实时天气信息。",
            config=config
        )
        
        # 测试案例1：深圳天气查询
        print("\n[测试1] 深圳天气查询")
        print("-" * 40)
        user_message1 = "今天深圳的天气如何？"
        print(f"用户: {user_message1}")
        response1 = await agent.process_message(user_message1)
        print(f"Agent: {response1}")
        
        # 检查是否使用了工具
        if "weather" in str(response1).lower() or "天气" in response1:
            print("✅ 可能使用了天气工具或RAG检索")
        else:
            print("⚠️  可能未使用天气工具")
        
        # 测试案例2：其他城市天气查询
        print("\n[测试2] 其他城市天气查询")
        print("-" * 40)
        user_message2 = "北京今天天气怎么样？"
        print(f"用户: {user_message2}")
        response2 = await agent.process_message(user_message2)
        print(f"Agent: {response2}")
        
        # 测试案例3：实时信息关键词测试
        print("\n[测试3] 实时信息关键词测试")
        print("-" * 40)
        user_message3 = "现在深圳的温度是多少？"
        print(f"用户: {user_message3}")
        response3 = await agent.process_message(user_message3)
        print(f"Agent: {response3}")
        
        print("\n✅ 天气查询测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 天气查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_case():
    """测试一个简单的端到端案例"""
    print("\n" + "=" * 60)
    print("测试简单端到端案例")
    print("=" * 60)
    
    try:
        # 初始化
        config = Config()
        agent = Agent(
            name="simple_test_agent",
            description="简单测试Agent",
            system_prompt="你是一个友好的AI助手。",
            config=config
        )
        
        # 测试案例1：简单问候
        print("\n[案例1] 简单问候")
        print("-" * 40)
        user_msg1 = "你好"
        print(f"用户: {user_msg1}")
        response1 = await agent.process_message(user_msg1)
        print(f"Agent: {response1}")
        
        # 测试案例2：简单查询（不需要工具）
        print("\n[案例2] 简单查询")
        print("-" * 40)
        user_msg2 = "请介绍一下你自己"
        print(f"用户: {user_msg2}")
        response2 = await agent.process_message(user_msg2)
        print(f"Agent: {response2}")
        
        # 测试案例3：检查记忆
        print("\n[案例3] 检查记忆")
        print("-" * 40)
        recent_messages = agent.memory.get_recent_messages(5)
        print(f"短期记忆消息数: {len(recent_messages)}")
        for i, msg in enumerate(recent_messages[-3:], 1):
            print(f"  {i}. {msg.role}: {msg.content[:50]}...")
        
        # 测试案例4：检查向量数据库
        print("\n[案例4] 检查向量数据库")
        print("-" * 40)
        memory_count = agent.memory_manager.vector_db.count_memories()
        print(f"长期记忆数量: {memory_count}")
        
        print("\n✅ 简单端到端测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 简单端到端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n🚀 启动系统测试...")
    print("注意：请确保已激活conda环境: conda activate /home/mnt/xieqinghongbing/env/open_manus")
    print("注意：请确保已设置环境变量: export DASHSCOPE_API_KEY=sk-5d4975fe68f24d83809ac3c7bf7468ba")
    print()
    
    # 检查环境变量
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("⚠️  警告: 未设置DASHSCOPE_API_KEY环境变量")
        print("   将使用配置文件中的默认值")
    
    # 运行测试
    try:
        # 基本测试
        success = asyncio.run(test_basic_conversation())
        
        if success:
            # 简单端到端测试
            print("\n运行简单端到端测试...")
            asyncio.run(test_simple_case())
            
            # 带工具的测试
            print("\n运行带工具的查询测试...")
            asyncio.run(test_query_with_tools())
            
            # 法律条文查询测试（RAG检索）
            print("\n运行法律条文查询测试...")
            asyncio.run(test_legal_query())
            
            # 天气查询测试（实时信息）
            print("\n运行天气查询测试...")
            asyncio.run(test_weather_query())
        
        print("\n✅ 所有测试完成！")
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

