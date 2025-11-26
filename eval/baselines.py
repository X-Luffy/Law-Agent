"""Baseline实现"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# 处理导入：优先使用相对导入，失败时使用绝对导入
try:
    from ..models.llm import LLM
    from ..config.config import Config
    from ..tools.web_search import WebSearchTool
except (ImportError, ValueError):
    # 如果相对导入失败，尝试绝对导入
    # 获取项目根目录
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from models.llm import LLM
        from config.config import Config
        from tools.web_search import WebSearchTool
    except ImportError:
        # 如果还是失败，尝试从项目根目录导入
        import os
        os.chdir(project_root)
        from models.llm import LLM
        from config.config import Config
        from tools.web_search import WebSearchTool


class BaselineA:
    """
    Baseline A: Raw Model (裸模型)
    - 无工具
    - 无System Prompt角色扮演
    - 直接使用LLM生成回答
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm = LLM(self.config)
    
    async def run(self, query: str) -> str:
        """
        运行Baseline A
        
        Args:
            query: 用户问题
            
        Returns:
            LLM生成的回答
        """
        try:
            # LLM.chat是同步方法，在异步函数中使用run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.llm.chat(
                    messages=[{"role": "user", "content": query}],
                    system_prompt=None,  # 无System Prompt
                    temperature=0.7,
                    max_tokens=self.config.llm_max_tokens
                )
            )
            return response
        except Exception as e:
            return f"Error: {str(e)}"


class BaselineB:
    """
    Baseline B: Naive Agent (单步搜索)
    - Qwen + Bocha Web Search
    - 简单的 Retrieve -> Generate 流程
    - 无路由分发，无反思环节
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm = LLM(self.config)
        self.web_search = WebSearchTool(self.config)
    
    async def run(self, query: str) -> str:
        """
        运行Baseline B
        
        Args:
            query: 用户问题
            
        Returns:
            基于搜索结果生成的回答
        """
        try:
            # 1. 搜索
            search_results = self.web_search.execute(query, {"max_results": 5})
            
            # 2. 生成回答
            prompt = f"""用户问题：{query}

搜索结果：
{search_results}

请根据搜索结果回答用户的问题。如果搜索结果中没有相关信息，请说明无法回答。"""
            
            # LLM.chat是同步方法，在异步函数中使用run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="你是一个法律助手，请根据搜索结果回答用户的问题。",
                    temperature=0.7,
                    max_tokens=self.config.llm_max_tokens
                )
            )
            
            return response
        except Exception as e:
            return f"Error: {str(e)}"
