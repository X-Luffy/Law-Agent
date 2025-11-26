"""Flow基类"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
from pydantic import BaseModel
# 处理相对导入问题
try:
    from ..agent.base import BaseAgent
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agent.base import BaseAgent


class BaseFlow(BaseModel, ABC):
    """Flow基类，定义所有flow的通用接口"""
    
    agents: Dict[str, BaseAgent]
    primary_agent_key: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self, 
        agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], 
        **data
    ):
        """
        初始化Flow
        
        Args:
            agents: Agent实例（单个、列表或字典）
            **data: 其他数据
        """
        # 处理不同方式提供的agents
        if isinstance(agents, BaseAgent):
            agents_dict = {"default": agents}
        elif isinstance(agents, list):
            agents_dict = {f"agent_{i}": agent for i, agent in enumerate(agents)}
        else:
            agents_dict = agents
        
        # 如果没有指定primary_agent_key，使用第一个agent
        primary_key = data.get("primary_agent_key")
        if not primary_key and agents_dict:
            primary_key = next(iter(agents_dict))
            data["primary_agent_key"] = primary_key
        
        # 设置agents字典
        data["agents"] = agents_dict
        
        # 使用BaseModel的init
        super().__init__(**data)
    
    @property
    def primary_agent(self) -> Optional[BaseAgent]:
        """获取primary agent"""
        return self.agents.get(self.primary_agent_key)
    
    def get_agent(self, key: str) -> Optional[BaseAgent]:
        """获取指定key的agent"""
        return self.agents.get(key)
    
    def add_agent(self, key: str, agent: BaseAgent) -> None:
        """添加agent到flow"""
        self.agents[key] = agent
    
    @abstractmethod
    async def execute(self, input_text: str) -> str:
        """
        执行flow
        
        Args:
            input_text: 输入文本
            
        Returns:
            执行结果
        """
        pass

