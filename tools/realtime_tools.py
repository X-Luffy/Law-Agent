"""实时信息获取工具"""
from typing import Dict, Any, Optional
import requests
from datetime import datetime
from .base import BaseTool
from ..config.config import Config


class WeatherTool(BaseTool):
    """天气查询工具，用于获取实时天气信息"""
    
    def __init__(self, config: Config):
        """
        初始化天气查询工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="weather",
            description="Get real-time weather information for a specific city. Use this tool when users ask about weather conditions, temperature, or weather forecasts. Input should be the city name, e.g., '深圳' or 'Shenzhen'."
        )
        self.config = config
        # 可以使用天气API（如OpenWeatherMap、和风天气等）
        # 这里提供一个简单的实现框架
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行天气查询
        
        Args:
            user_input: 城市名称（如"深圳"、"Shenzhen"）
            context: 上下文信息
            
        Returns:
            天气信息字典
        """
        city = user_input.strip()
        if not city:
            return {
                "error": "City name is required",
                "city": "",
                "weather": None
            }
        
        # 尝试使用天气API
        try:
            # 方法1: 使用和风天气API（需要API Key）
            weather_data = self._get_weather_from_api(city)
            if weather_data:
                return weather_data
            
            # 方法2: 使用Web搜索获取天气信息
            weather_data = self._get_weather_from_web(city)
            if weather_data:
                return weather_data
            
            return {
                "error": "Failed to get weather information",
                "city": city,
                "weather": None
            }
        except Exception as e:
            return {
                "error": str(e),
                "city": city,
                "weather": None
            }
    
    def _get_weather_from_api(self, city: str) -> Optional[Dict[str, Any]]:
        """从天气API获取天气信息"""
        import os
        # 可以使用和风天气、OpenWeatherMap等API
        api_key = os.getenv("WEATHER_API_KEY")
        if not api_key:
            return None
        
        # 这里提供一个框架，实际使用时需要根据具体API文档实现
        # 示例：和风天气API
        try:
            # 先获取城市代码
            city_url = f"https://geoapi.qweather.com/v2/city/lookup?location={city}&key={api_key}"
            city_response = requests.get(city_url, timeout=5)
            if city_response.status_code == 200:
                city_data = city_response.json()
                if city_data.get("code") == "200" and city_data.get("location"):
                    location_id = city_data["location"][0]["id"]
                    
                    # 获取实时天气
                    weather_url = f"https://devapi.qweather.com/v7/weather/now?location={location_id}&key={api_key}"
                    weather_response = requests.get(weather_url, timeout=5)
                    if weather_response.status_code == 200:
                        weather_data = weather_response.json()
                        if weather_data.get("code") == "200" and weather_data.get("now"):
                            now = weather_data["now"]
                            return {
                                "city": city,
                                "temperature": now.get("temp"),
                                "feels_like": now.get("feelsLike"),
                                "weather": now.get("text"),
                                "humidity": now.get("humidity"),
                                "wind_speed": now.get("windSpeed"),
                                "wind_dir": now.get("windDir"),
                                "pressure": now.get("pressure"),
                                "update_time": now.get("obsTime"),
                                "source": "qweather_api"
                            }
        except Exception as e:
            print(f"Weather API error: {e}")
        
        return None
    
    def _get_weather_from_web(self, city: str) -> Optional[Dict[str, Any]]:
        """从Web搜索获取天气信息（备用方案）"""
        try:
            # 使用Web搜索工具搜索天气信息
            from .web_search import WebSearchTool
            web_search = WebSearchTool(self.config)
            
            # 构建搜索查询
            query = f"{city} 天气 今天"
            search_results = web_search.execute(query, {"max_results": 3})
            
            if search_results.get("results"):
                # 从搜索结果中提取天气信息
                first_result = search_results["results"][0]
                snippet = first_result.get("snippet", "")
                
                # 尝试从snippet中提取天气信息
                # 这里提供一个简单的解析，实际可以更复杂
                return {
                    "city": city,
                    "weather_info": snippet,
                    "source": first_result.get("url", ""),
                    "update_time": datetime.now().isoformat(),
                    "source_type": "web_search"
                }
        except Exception as e:
            print(f"Web weather search error: {e}")
        
        return None


class WebCrawlerTool(BaseTool):
    """网络爬虫工具，用于爬取网页内容用于RAG检索"""
    
    def __init__(self, config: Config):
        """
        初始化网络爬虫工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="web_crawler",
            description="Crawl and extract content from web pages. Use this tool when you need to get detailed content from a specific URL for RAG retrieval. Input should be a URL or a list of URLs."
        )
        self.config = config
        self.timeout = 10
        self.max_content_length = 50000  # 最大内容长度
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行网页爬取
        
        Args:
            user_input: URL或URL列表（JSON格式）
            context: 上下文信息
            
        Returns:
            爬取结果字典
        """
        import json
        
        # 解析输入（可能是URL字符串或JSON格式的URL列表）
        try:
            urls = json.loads(user_input) if user_input.strip().startswith("[") else [user_input.strip()]
        except:
            urls = [user_input.strip()]
        
        if not urls or not urls[0]:
            return {
                "error": "URL is required",
                "urls": [],
                "contents": []
            }
        
        results = []
        for url in urls[:5]:  # 最多处理5个URL
            try:
                content = self._crawl_url(url)
                if content:
                    results.append({
                        "url": url,
                        "content": content,
                        "length": len(content),
                        "status": "success"
                    })
                else:
                    results.append({
                        "url": url,
                        "content": "",
                        "length": 0,
                        "status": "failed",
                        "error": "Failed to extract content"
                    })
            except Exception as e:
                results.append({
                    "url": url,
                    "content": "",
                    "length": 0,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "urls": urls,
            "contents": results,
            "total": len(results),
            "successful": sum(1 for r in results if r["status"] == "success")
        }
    
    def _crawl_url(self, url: str) -> Optional[str]:
        """
        爬取单个URL的内容
        
        Args:
            url: 网页URL
            
        Returns:
            网页文本内容
        """
        from bs4 import BeautifulSoup
        import re
        
        try:
            # 设置请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # 发送请求
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return None
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除script和style标签
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()
            
            # 提取文本内容
            text = soup.get_text()
            
            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # 限制长度
            if len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "..."
            
            return text
        
        except Exception as e:
            print(f"Error crawling URL {url}: {e}")
            return None

