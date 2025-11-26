"""博查 (Bocha) 搜索工具 - 专为中文互联网设计"""
import requests
import json
import os
from typing import Dict, Any, List
# 处理相对导入问题
try:
    from .base import BaseTool
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from tools.base import BaseTool
    from config.config import Config


class WebSearchTool(BaseTool):
    """
    博查 (Bocha) 搜索工具
    
    专为中文互联网设计，能直接返回高质量的内容摘要和来源链接。
    对于大多数查询，不需要额外的 url_reader 即可获取足够信息。
    
    优势：
    - 后端预读取和清洗网页内容
    - 开启summary=True时返回信息密度极高的内容摘要
    - 包含核心事实、数据和逻辑
    """
    
    def __init__(self, config: Config):
        """
        初始化博查搜索工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="web_search",
            description=(
                "搜索中文互联网信息。当需要查询事实、法律法规、案例分析或新闻时使用。"
                "返回结果包含详细摘要和来源链接。"
                "该工具返回的摘要已经足够详细，通常不需要额外的URL阅读工具。"
            )
        )
        self.config = config
        
        # 博查 API Key（优先从config获取，然后从环境变量）
        self.api_key = (
            getattr(config, 'bocha_api_key', None) or
            os.getenv("BOCHA_API_KEY") or
            "sk-abc3ef836fd9487c867cc58df5f76c31"  # 默认API Key（建议后续放入环境变量）
        )
        
        # 博查 API 端点
        self.api_url = "https://api.bochaai.com/v1/web-search"
        
        # 最大结果数
        self.max_results = getattr(config, 'web_search_max_results', 8)
    
    def execute(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """
        执行搜索
        
        Args:
            user_input: 搜索关键词 (Query)
            context: 上下文信息（可包含max_results等参数）
            
        Returns:
            格式化后的文本，包含标题、URL和长摘要
        """
        query = user_input.strip()
        if not query:
            return "Error: Empty search query"
        
        # 从context获取max_results，如果没有则使用默认值
        max_results = context.get("max_results", self.max_results) if context else self.max_results
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构造请求体
        payload = {
            "query": query,
            "freshness": "noLimit",  # 时间限制：noLimit, oneDay, oneWeek, oneMonth, oneYear
            "summary": True,         # 关键点：开启长摘要，替代 url_reader 的部分功能
            "count": max_results     # 返回结果数量
        }
        
        try:
            # 发起请求
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return f"Error: Search API returned status code {response.status_code}"
            
            data = response.json()
            
            # 检查业务状态码
            if data.get("code") != 200:
                return f"Error: {data.get('msg', 'Unknown error')}"
            
            # 提取网页数据
            web_pages = data.get("data", {}).get("webPages", {}).get("value", [])
            
            if not web_pages:
                return f"No results found for query: {query}"
                
            return self._format_results(query, web_pages)
            
        except requests.exceptions.Timeout:
            return "Error: Search request timeout. Please try again later."
        except requests.exceptions.RequestException as e:
            return f"Error: Network error - {str(e)}"
        except Exception as e:
            return f"Search failed: {str(e)}"
    
    def _format_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        将 JSON 数据格式化为 LLM 和人类都易读的文本
        
        Args:
            query: 搜索查询
            results: 搜索结果列表
            
        Returns:
            格式化的结果字符串
        """
        parts = [f"Search results for '{query}':\n"]
        
        for i, item in enumerate(results, 1):
            title = item.get("name", "No Title")
            url = item.get("url", "No URL")
            # 优先使用 summary (长摘要)，如果没有则使用 snippet (短摘要)
            content = item.get("summary") or item.get("snippet") or "No content available."
            
            # 发布时间 (如果有)
            date_published = item.get("datePublished", "")
            time_info = f" (Time: {date_published})" if date_published else ""
            
            parts.append(f"Result {i}:")
            parts.append(f"Title: {title}{time_info}")
            parts.append(f"Source: {url}")  # 明确标注 Source，方便 LLM 引用
            parts.append(f"Content: {content}")
            parts.append("-" * 30)  # 分隔符
        
        return "\n".join(parts)
    
    def to_schema(self) -> Dict[str, Any]:
        """
        将工具转换为OpenAI格式的JSON Schema
        
        Returns:
            OpenAI格式的工具定义字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或查询字符串"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数量（可选，默认8）",
                            "default": self.max_results
                        }
                    },
                    "required": ["query"]
                }
            }
        }
