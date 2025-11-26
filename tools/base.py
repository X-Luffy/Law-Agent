"""工具基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable


class BaseTool(ABC):
    """工具基类，所有工具都需要继承此类"""
    
    def __init__(self, name: str, description: str):
        """
        初始化工具
        
        Args:
            name: 工具名称
            description: 工具描述（用于Native Function Calling）
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, user_input: str, context: Dict[str, Any] = None) -> Any:
        """
        执行工具
        
        Args:
            user_input: 用户输入
            context: 上下文信息（可选）
            
        Returns:
            工具执行结果
        """
        pass
    
    @abstractmethod
    def to_schema(self) -> Dict[str, Any]:
        """
        将工具转换为OpenAI格式的JSON Schema（用于Native Function Calling）
        
        Returns:
            OpenAI格式的工具定义字典
            格式: {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "...",
                    "parameters": {
                        "type": "object",
                        "properties": {...},
                        "required": [...]
                    }
                }
            }
        """
        pass
    
    def get_description(self) -> str:
        """获取工具描述"""
        return self.description
    
    def get_name(self) -> str:
        """获取工具名称"""
        return self.name
    
    def get_execute_function(self) -> Callable:
        """
        获取工具的执行函数（用于映射字典）
        
        Returns:
            工具的execute方法
        """
        return self.execute

