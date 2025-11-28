"""工具管理器"""
from typing import Dict, List, Optional, Callable, Any
from .base import BaseTool
from .web_search import WebSearchTool
from .common_tools import (
    PythonExecutorTool,
    CalculatorTool,
    FileReadTool,
    DateTimeTool
)
from .realtime_tools import WeatherTool, WebCrawlerTool
from .document_tool import DocumentGeneratorTool
from .tool_registry import ToolRegistry
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


class ToolManager:
    """工具管理器，负责注册、管理和调用工具（使用ToolRegistry）"""
    
    def __init__(self, config: Config):
        """
        初始化工具管理器
        
        Args:
            config: 系统配置
        """
        self.config = config
        
        # 使用ToolRegistry管理工具
        self.registry = ToolRegistry(config)
        
        # 注册默认工具
        self._register_default_tools()
        
        # 注册实时信息工具
        self.register_tool(WeatherTool(config))
        self.register_tool(WebCrawlerTool(config))
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 注册博查Web搜索工具（返回高质量摘要，无需额外的URL阅读工具）
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
        
        # 注册法律文书生成工具
        document_generator = DocumentGeneratorTool(self.config)
        self.register_tool(document_generator)
    
    def register_tool(self, tool: BaseTool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        self.registry.register_tool(tool)
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具实例，如果不存在返回None
        """
        return self.registry.get_tool(tool_name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有工具
        
        Returns:
            所有工具实例列表
        """
        return list(self.registry.get_all_tools().values())
    
    def get_all_tool_descriptions(self) -> Dict[str, str]:
        """
        获取所有工具的描述（保留兼容性，用于embedding）
        
        Returns:
            工具名称到描述的字典
        """
        return {
            tool.get_name(): tool.get_description()
            for tool in self.registry.get_all_tools().values()
        }
    
    def list_tools(self) -> List[str]:
        """
        列出所有工具名称
        
        Returns:
            工具名称列表
        """
        return self.registry.list_tools()
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的JSON Schema（用于Native Function Calling）
        
        Returns:
            OpenAI格式的工具列表
        """
        return self.registry.get_tools_schema()
    
    def get_available_functions(self) -> Dict[str, Callable]:
        """
        获取工具名称到执行函数的映射字典（用于Native Function Calling）
        
        Returns:
            工具名称到执行函数的字典
        """
        return self.registry.get_available_functions()
    
    @property
    def tools(self) -> Dict[str, BaseTool]:
        """
        获取工具字典（保留兼容性）
        
        Returns:
            工具名称到工具对象的字典
        """
        return self.registry.get_all_tools()

