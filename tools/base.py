"""工具基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTool(ABC):
    """工具基类，所有工具都需要继承此类"""
    
    def __init__(self, name: str, description: str):
        """
        初始化工具
        
        Args:
            name: 工具名称
            description: 工具描述（用于embedding和工具选择）
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, user_input: str, context: Dict[str, Any]) -> Any:
        """
        执行工具
        
        Args:
            user_input: 用户输入
            context: 上下文信息
            
        Returns:
            工具执行结果
        """
        pass
    
    def get_description(self) -> str:
        """获取工具描述"""
        return self.description
    
    def get_name(self) -> str:
        """获取工具名称"""
        return self.name

