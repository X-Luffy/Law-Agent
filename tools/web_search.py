"""Web检索工具（Google搜索）"""
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
from .base import BaseTool
from ..config.config import Config


class WebSearchTool(BaseTool):
    """Web检索工具，用于搜索网络信息（Google搜索）"""
    
    def __init__(self, config: Config):
        """
        初始化Web检索工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="web_search",
            description="Search the web for information using Google search. Use this tool when you need to find current information, facts, or data from the internet."
        )
        self.config = config
        self.max_results = config.web_search_max_results
        
        # Google搜索API配置（可以使用Google Custom Search API或爬虫方式）
        self.google_api_key = None  # 从环境变量或配置中获取
        self.google_cx = None  # Google Custom Search Engine ID
        self._initialize_google_search()
    
    def _initialize_google_search(self):
        """初始化Google搜索配置"""
        import os
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_CX")
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Web搜索
        
        Args:
            user_input: 用户输入（包含搜索关键词）
            context: 上下文信息（可包含max_results等参数）
            
        Returns:
            搜索结果字典，包含results, query等
        """
        # 提取搜索关键词
        query = user_input.strip()
        if not query:
            return {
                "query": query,
                "results": [],
                "error": "Empty query"
            }
        
        # 获取最大结果数
        max_results = context.get("max_results", self.max_results)
        
        # 尝试使用Google Custom Search API
        if self.google_api_key and self.google_cx:
            try:
                return self._search_with_google_api(query, max_results)
            except Exception as e:
                print(f"Warning: Google API search failed: {e}, trying alternative method")
        
        # 如果API不可用，使用爬虫方式（需要实现）
        try:
            return self._search_with_scraper(query, max_results)
        except Exception as e:
            return {
                "query": query,
                "results": [],
                "error": f"Search failed: {str(e)}"
            }
    
    def _search_with_google_api(
        self,
        query: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        使用Google Custom Search API搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            搜索结果字典
        """
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_api_key,
            "cx": self.google_cx,
            "q": query,
            "num": min(max_results, 10)  # Google API最多返回10个结果
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 解析搜索结果
            results = []
            if "items" in data:
                for item in data["items"][:max_results]:
                    result = {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "display_url": item.get("displayLink", "")
                    }
                    results.append(result)
            
            return {
                "query": query,
                "results": results,
                "total_results": data.get("searchInformation", {}).get("totalResults", "0")
            }
        except Exception as e:
            raise RuntimeError(f"Google API search failed: {str(e)}")
    
    def _search_with_scraper(
        self,
        query: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        使用爬虫方式搜索（备用方案）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            搜索结果字典
        """
        # 注意：直接爬取Google搜索结果可能违反服务条款
        # 这里提供一个框架，实际使用时建议使用Google Custom Search API
        
        # 构建Google搜索URL
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={max_results}"
        
        # 设置请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取搜索结果（Google的HTML结构可能会变化）
            results = []
            search_results = soup.find_all('div', class_='g')[:max_results]
            
            for result in search_results:
                title_elem = result.find('h3')
                link_elem = result.find('a')
                snippet_elem = result.find('span', class_='aCOpRe')
                
                if title_elem and link_elem:
                    result_data = {
                        "title": title_elem.get_text(),
                        "url": link_elem.get('href', ''),
                        "snippet": snippet_elem.get_text() if snippet_elem else ""
                    }
                    results.append(result_data)
            
            return {
                "query": query,
                "results": results
            }
        except Exception as e:
            raise RuntimeError(f"Scraper search failed: {str(e)}")
    
    def search_simple(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        简单搜索接口（返回结果列表）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            搜索结果列表
        """
        result = self.execute(query, {"max_results": max_results})
        return result.get("results", [])
