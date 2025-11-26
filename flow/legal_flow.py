"""法律Flow，协调CoreAgent和子Agent"""
from typing import Optional, Dict, Any
from pydantic import Field
# 处理相对导入问题
try:
    from .base import BaseFlow
    from ..agent.core_agent import CoreAgent
    from ..schema import LegalDomain, LegalIntent, StatusCallback
    from ..config.config import Config
    from ..models.llm import LLM
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from flow.base import BaseFlow
    from agent.core_agent import CoreAgent
    from schema import LegalDomain, LegalIntent, StatusCallback
    from config.config import Config
    from models.llm import LLM


class LegalFlow(BaseFlow):
    """法律Flow，协调CoreAgent和子Agent的协同工作"""
    
    core_agent: Optional[CoreAgent] = Field(default=None, exclude=True)
    config: Optional[Config] = Field(default=None, exclude=True)
    llm: Optional[LLM] = Field(default=None, exclude=True)
    
    def __init__(
        self,
        core_agent: Optional[CoreAgent] = None,
        config: Optional[Config] = None,
        **kwargs
    ):
        """
        初始化LegalFlow
        
        Args:
            core_agent: CoreAgent实例（如果不提供，会创建一个）
            config: 系统配置
            **kwargs: 其他参数
        """
        if config is None:
            config = Config()
        
        if core_agent is None:
            core_agent = CoreAgent(config=config)
        
        super().__init__(agents={"core": core_agent}, **kwargs)
        
        # 使用object.__setattr__来绕过Pydantic的限制
        object.__setattr__(self, 'core_agent', core_agent)
        object.__setattr__(self, 'config', config)
        object.__setattr__(self, 'llm', LLM(config))
    
    async def execute(self, input_text: str, status_callback: Optional[StatusCallback] = None) -> str:
        """
        执行LegalFlow
        
        新流程（由CoreAgent.process_message统一处理）：
        1. CoreAgent识别业务领域、意图
        2. 路由到子Agent
        
        Args:
            input_text: 用户输入
            status_callback: 状态回调函数
            
        Returns:
            执行结果
        """
        # 直接使用CoreAgent的process_message方法，它已经包含了完整的流程
        return await self.core_agent.process_message(input_text, status_callback)

