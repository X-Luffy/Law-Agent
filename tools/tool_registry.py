"""工具注册表，用于Native Function Calling"""
from typing import Dict, List, Any, Callable, Optional
from .base import BaseTool
# 处理相对导入问题
try:
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config


class ToolRegistry:
    """
    工具注册表类
    
    负责：
    1. 管理所有工具对象
    2. 生成工具JSON Schema（用于Native Function Calling）
    3. 建立工具名称到真实函数对象的映射字典
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化工具注册表
        
        Args:
            config: 系统配置
        """
        self.config = config or Config()
        
        # 工具字典：工具名称 -> 工具对象
        self.tools: Dict[str, BaseTool] = {}
        
        # 映射字典：工具名称 -> 真实函数对象（execute方法）
        self.available_functions: Dict[str, Callable] = {}
    
    def register_tool(self, tool: BaseTool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        tool_name = tool.get_name()
        self.tools[tool_name] = tool
        
        # 建立映射：工具名称 -> execute方法
        self.available_functions[tool_name] = tool.get_execute_function()
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具对象
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具实例，如果不存在返回None
        """
        return self.tools.get(tool_name)
    
    def get_function(self, tool_name: str) -> Optional[Callable]:
        """
        获取工具的执行函数
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具的执行函数，如果不存在返回None
        """
        return self.available_functions.get(tool_name)
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        生成所有工具的JSON Schema（用于Native Function Calling）
        
        Returns:
            OpenAI格式的工具列表
            格式: [
                {
                    "type": "function",
                    "function": {
                        "name": "tool_name",
                        "description": "...",
                        "parameters": {...}
                    }
                },
                ...
            ]
        """
        tools_schema = []
        
        for tool_name, tool in self.tools.items():
            try:
                schema = tool.to_schema()
                tools_schema.append(schema)
            except Exception as e:
                print(f"Warning: Failed to generate schema for tool '{tool_name}': {e}")
                continue
        
        return tools_schema
    
    def list_tools(self) -> List[str]:
        """
        列出所有已注册的工具名称
        
        Returns:
            工具名称列表
        """
        return list(self.tools.keys())
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """
        获取所有工具对象
        
        Returns:
            工具名称到工具对象的字典
        """
        return self.tools.copy()
    
    def get_available_functions(self) -> Dict[str, Callable]:
        """
        获取所有工具的执行函数映射字典
        
        Returns:
            工具名称到执行函数的字典
        """
        return self.available_functions.copy()

