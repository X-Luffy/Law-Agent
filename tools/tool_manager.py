"""工具管理器"""
from typing import Dict, List, Optional
from .base import BaseTool
from .web_search import WebSearchTool
from .common_tools import (
    PythonExecutorTool,
    CalculatorTool,
    FileReadTool,
    DateTimeTool
)
from .realtime_tools import WeatherTool, WebCrawlerTool
from ..config.config import Config


class ToolManager:
    """工具管理器，负责注册、管理和调用工具"""
    
    def __init__(self, config: Config):
        """
        初始化工具管理器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.tools: Dict[str, BaseTool] = {}
        
        # 注册默认工具
        self._register_default_tools()
        
        # 注册实时信息工具
        self.register_tool(WeatherTool(config))
        self.register_tool(WebCrawlerTool(config))
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 注册Web搜索工具
        web_search = WebSearchTool(self.config)
        self.register_tool(web_search)
        
        # 注册Python执行工具
        python_executor = PythonExecutorTool(self.config)
        self.register_tool(python_executor)
        
        # 注册计算器工具
        calculator = CalculatorTool(self.config)
        self.register_tool(calculator)
        
        # 注册文件读取工具
        file_read = FileReadTool(self.config)
        self.register_tool(file_read)
        
        # 注册日期时间工具
        datetime_tool = DateTimeTool(self.config)
        self.register_tool(datetime_tool)
    
    def register_tool(self, tool: BaseTool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        self.tools[tool.get_name()] = tool
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具实例，如果不存在返回None
        """
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有工具
        
        Returns:
            所有工具实例列表
        """
        return list(self.tools.values())
    
    def get_all_tool_descriptions(self) -> Dict[str, str]:
        """
        获取所有工具的描述（用于embedding）
        
        Returns:
            工具名称到描述的字典
        """
        return {
            tool.get_name(): tool.get_description()
            for tool in self.tools.values()
        }
    
    def list_tools(self) -> List[str]:
        """
        列出所有工具名称
        
        Returns:
            工具名称列表
        """
        return list(self.tools.keys())

