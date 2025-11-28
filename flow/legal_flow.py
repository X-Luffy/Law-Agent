"""法律Flow，协调CoreAgent和子Agent - 中心化记忆管理版本"""
from typing import Optional, Dict, Any, Tuple
from pydantic import Field
# 处理相对导入问题
try:
    from .base import BaseFlow
    from ..agent.core_agent import CoreAgent
    from ..agent.specialized_agent import SpecializedAgent
    from ..agent.general_agent import GeneralChatAgent
    from ..schema import LegalDomain, LegalIntent, StatusCallback
    from ..config.config import Config
    from ..models.llm import LLM
    from ..memory.memory_manager import MemoryManager
except (ImportError, ValueError):
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from flow.base import BaseFlow
    from agent.core_agent import CoreAgent
    from agent.specialized_agent import SpecializedAgent
    from agent.general_agent import GeneralChatAgent
    from schema import LegalDomain, LegalIntent, StatusCallback
    from config.config import Config
    from models.llm import LLM
    from memory.memory_manager import MemoryManager


class LegalFlow(BaseFlow):
    """法律Flow，协调CoreAgent和子Agent的协同工作 - 中心化记忆管理"""
    
    core_agent: Optional[CoreAgent] = Field(default=None, exclude=True)
    config: Optional[Config] = Field(default=None, exclude=True)
    llm: Optional[LLM] = Field(default=None, exclude=True)
    memory: Optional[MemoryManager] = Field(default=None, exclude=True)
    global_state: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    agents: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    
    def __init__(
        self,
        core_agent: Optional[CoreAgent] = None,
        config: Optional[Config] = None,
        **kwargs
    ):
        """
        初始化LegalFlow（中心化记忆管理）
        
        Args:
            core_agent: CoreAgent实例（如果不提供，会创建一个无状态的）
            config: 系统配置
            **kwargs: 其他参数
        """
        if config is None:
            config = Config()
        
        # 1. 记忆中心化：唯一持有MemoryManager实例
        memory = MemoryManager(config)
        
        # 2. 全局状态：暂存CoreAgent提取的关键实体
        global_state = {}
        
        # 3. Agent初始化（无状态）
        if core_agent is None:
            # 创建无状态的CoreAgent（不传入memory）
            core_agent = CoreAgent(config=config)
        else:
            # 如果传入了core_agent，确保它是无状态的（不持有memory）
            # 注意：这里假设core_agent已经是无状态的，或者我们需要清理它的memory引用
            pass
        
        # 初始化所有子Agent（无状态）
        agents = {
            "family": SpecializedAgent(LegalDomain.FAMILY_LAW, config=config),
            "labor": SpecializedAgent(LegalDomain.LABOR_LAW, config=config),
            "contract": SpecializedAgent(LegalDomain.CONTRACT_LAW, config=config),
            "corporate": SpecializedAgent(LegalDomain.CORPORATE_LAW, config=config),
            "criminal": SpecializedAgent(LegalDomain.CRIMINAL_LAW, config=config),
            "procedural": SpecializedAgent(LegalDomain.PROCEDURAL_QUERY, config=config),
            "general": GeneralChatAgent(config=config)  # 统一处理非法律
        }
        
        super().__init__(agents={"core": core_agent}, **kwargs)
        
        # 使用object.__setattr__来绕过Pydantic的限制
        object.__setattr__(self, 'core_agent', core_agent)
        object.__setattr__(self, 'config', config)
        object.__setattr__(self, 'llm', LLM(config))
        object.__setattr__(self, 'memory', memory)
        object.__setattr__(self, 'global_state', global_state)
        object.__setattr__(self, 'agents', agents)
    
    async def execute(self, input_text: str, status_callback: Optional[StatusCallback] = None, session_id: str = "default") -> str:
        """
        执行LegalFlow（中心化记忆管理流程）
        
        严格顺序：
        1. Write User: 保存用户输入到记忆
        2. Read Context: 获取完整上下文（Session历史 + VectorDB检索 + GlobalState）
        3. Route: CoreAgent路由（返回领域、意图、实体）
        4. Update Global: 更新全局状态
        5. Execute: 调用目标Agent（无状态执行）
        6. Write Assistant: 保存Agent回复到记忆
        7. Archive: 检查并归档长期记忆
        
        Args:
            input_text: 用户输入
            status_callback: 状态回调函数
            session_id: 会话ID（默认"default"）
            
        Returns:
            执行结果
        """
        try:
            # Step 1: 存用户输入
            self.memory.add_message("user", input_text, session_id=session_id)
            
            if status_callback:
                status_callback("🔍 Phase 1: 意图识别", "正在分析用户问题，识别法律领域和意图...", "running")
            
            # Step 2: 以此刻的记忆构建上下文
            current_context = self.memory.get_full_context(input_text, session_id=session_id)
            
            # Step 3: CoreAgent 路由 (无状态调用)
            # CoreAgent.route 应返回元组: (领域, 意图, 实体)
            domain, intent, entities = await self.core_agent.route(input_text, current_context, status_callback)
            
            # Step 4: 更新全局状态 (如果提取到了新实体)
            if entities:
                self.global_state.update(entities)
                # 更新MemoryManager的全局记忆
                domain_str = domain.value if hasattr(domain, 'value') else str(domain)
                intent_str = intent.value if hasattr(intent, 'value') else str(intent)
                self.memory.update_global_memory(domain=domain_str, intent=intent_str, entities=entities)
                # 重新刷新上下文，把新实体加进去
                current_context = self.memory.format_context(self.global_state)
            
            # Step 5: 选择 Agent
            domain_key_map = {
                LegalDomain.FAMILY_LAW: "family",
                LegalDomain.LABOR_LAW: "labor",
                LegalDomain.CONTRACT_LAW: "contract",
                LegalDomain.CORPORATE_LAW: "corporate",
                LegalDomain.CRIMINAL_LAW: "criminal",
                LegalDomain.PROCEDURAL_QUERY: "procedural",
                LegalDomain.NON_LEGAL: "general"
            }
            
            domain_key = domain_key_map.get(domain, "general")
            target_agent = self.agents.get(domain_key, self.agents["general"])
            
            if status_callback:
                status_callback("⚡ Phase 2: 专业Agent执行", f"已识别领域: {domain.value if hasattr(domain, 'value') else domain}，意图: {intent.value if hasattr(intent, 'value') else intent}，正在唤醒专业Agent...", "running")
            
            # Step 6: 执行任务 (无状态调用)
            # 对于SpecializedAgent，需要传递domain和intent
            if isinstance(target_agent, SpecializedAgent):
                response = await target_agent.run(input_text, context=current_context, domain=domain, intent=intent, status_callback=status_callback)
            else:
                # GeneralChatAgent或其他Agent
                response = await target_agent.run(input_text, context=current_context, status_callback=status_callback)
            
            # Step 7: 存 Agent 回复
            self.memory.add_message("assistant", response, session_id=session_id)
            
            # Step 8: 长期记忆归档管理 (检查窗口，存入向量库)
            await self.memory.check_and_archive(session_id=session_id)
            
            if status_callback:
                status_callback("✅ Phase 3: 完成", "回答生成完毕", "complete")
            
            return response
            
        except Exception as e:
            print(f"[ERROR] LegalFlow.execute发生异常: {e}")
            import traceback
            traceback.print_exc()
            if status_callback:
                status_callback("❌ 错误", "处理过程中发生错误", "error")
            return f"抱歉，系统在处理您的问题时遇到了技术问题：{str(e)}。请稍后重试或咨询专业律师。"
