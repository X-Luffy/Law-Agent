"""Web检索RAG"""
from typing import List, Dict, Any, Optional
from ..tools.web_search import WebSearchTool
from ..llm.llm import LLM
from ..config.config import Config


class WebRAG:
    """Web检索RAG，使用工具进行Google搜索，然后使用LLM整合生成答案"""
    
    def __init__(self, config: Config, web_search_tool: Optional[WebSearchTool] = None):
        """
        初始化Web检索RAG
        
        Args:
            config: 系统配置
            web_search_tool: Web搜索工具（如果为None，则创建新实例）
        """
        self.config = config
        self.llm = LLM(config)
        self.web_search_tool = web_search_tool or WebSearchTool(config)
    
    def search_and_generate(
        self,
        query: str,
        max_results: int = 5,
        max_context_length: int = 2000,
        crawl_content: bool = True
    ) -> Dict[str, Any]:
        """
        搜索网络信息并生成答案
        
        Args:
            query: 查询文本
            max_results: 最大搜索结果数
            max_context_length: 最大上下文长度
            crawl_content: 是否爬取网页内容（用于更详细的RAG）
            
        Returns:
            包含答案、搜索结果、来源等的字典
        """
        # 1. 使用Web搜索工具搜索相关信息
        search_results = self._search_web(query, max_results)
        
        if not search_results or not search_results.get("results"):
            return {
                "answer": "抱歉，未能从网络搜索到相关信息。",
                "search_results": [],
                "sources": [],
                "answer_source": "unable_to_answer"
            }
        
        # 2. 如果需要，爬取网页详细内容
        if crawl_content:
            from ..tools.realtime_tools import WebCrawlerTool
            crawler = WebCrawlerTool(self.config)
            
            # 爬取前3个结果的详细内容
            urls_to_crawl = [r.get("url", "") for r in search_results["results"][:3] if r.get("url")]
            if urls_to_crawl:
                crawl_results = crawler.execute(
                    user_input=str(urls_to_crawl),
                    context={}
                )
                
                # 将爬取的内容添加到搜索结果中
                if crawl_results.get("contents"):
                    for i, content_result in enumerate(crawl_results["contents"]):
                        if i < len(search_results["results"]) and content_result.get("status") == "success":
                            search_results["results"][i]["full_content"] = content_result.get("content", "")
        
        # 3. 格式化搜索结果为上下文
        context = self._format_search_results(search_results["results"], max_context_length)
        
        # 4. 使用LLM整合生成答案
        answer = self._generate_answer(query, context, search_results["results"])
        
        # 5. 提取来源信息
        sources = self._extract_sources(search_results["results"])
        
        return {
            "answer": answer,
            "search_results": search_results["results"],
            "sources": sources,
            "context_length": len(context),
            "answer_source": "web_search"
        }
    
    def _search_web(
        self,
        query: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        使用Web搜索工具搜索网络信息
        
        Args:
            query: 查询文本
            max_results: 最大搜索结果数
            
        Returns:
            搜索结果字典
        """
        try:
            # 调用Web搜索工具
            result = self.web_search_tool.execute(
                user_input=query,
                context={"max_results": max_results}
            )
            
            # 处理搜索结果
            if isinstance(result, dict):
                return result
            else:
                # 如果返回的是字符串，尝试解析
                return {
                    "query": query,
                    "results": []
                }
        except Exception as e:
            print(f"Warning: Web search failed: {e}")
            return {
                "query": query,
                "results": []
            }
    
    def _format_search_results(
        self,
        search_results: List[Dict[str, Any]],
        max_length: int = 2000
    ) -> str:
        """
        格式化搜索结果为上下文
        
        Args:
            search_results: 搜索结果列表
            max_length: 最大长度限制
            
        Returns:
            格式化后的上下文文本
        """
        context_parts = []
        current_length = 0
        
        for i, result in enumerate(search_results):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            url = result.get("url", "")
            
            # 格式化搜索结果
            result_text = f"[搜索结果 {i + 1}]"
            if title:
                result_text += f" 标题: {title}\n"
            if snippet:
                result_text += f" 内容: {snippet}\n"
            if url:
                result_text += f" 来源: {url}\n"
            
            # 检查长度限制
            if current_length + len(result_text) > max_length:
                break
            
            context_parts.append(result_text)
            current_length += len(result_text)
        
        return "\n".join(context_parts)
    
    def _generate_answer(
        self,
        query: str,
        context: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """
        使用LLM整合生成答案
        
        Args:
            query: 查询文本
            context: 搜索结果的上下文
            search_results: 搜索结果列表
            
        Returns:
            生成的答案
        """
        # 构建prompt（增强版，避免幻觉）
        system_prompt = """你是一个专业的信息助手，特别擅长法律相关问题的回答。请根据提供的网络搜索结果，准确、完整地回答用户的问题。

**重要约束**：
1. **严格基于搜索结果**：答案必须严格基于提供的搜索结果，不得编造或推测
2. **无法回答时明确说明**：如果搜索结果中没有相关信息，必须明确说明"根据搜索结果，无法找到相关信息"或"无法回答此问题"
3. **引用来源**：必须明确引用具体的来源URL
4. **区分专业回答和一般回答**：
   - 专业回答（法律条文、案例等）：必须基于搜索结果，明确标注来源
   - 一般回答：可以基于常识，但要说明这是基于一般知识
5. **禁止幻觉**：严禁编造法律条文、案例或事实，如果不知道，必须说明

**回答格式**：
- 开头说明"根据网络搜索结果..."
- 引用具体来源："来源：[URL]"
- 如果无法回答：明确说明"无法回答"或"未找到相关信息"

要求：
1. 答案必须基于提供的搜索结果
2. 答案要准确、完整、客观
3. 如果搜索结果中没有相关信息，请明确说明
4. 必须引用具体的来源URL
5. 使用清晰、易懂的语言
6. 注意信息的时效性和准确性"""
        
        user_prompt = f"""用户问题：{query}

网络搜索结果：
{context}

请根据上述网络搜索结果，回答用户的问题。如果搜索结果中没有相关信息，请明确说明。"""
        
        try:
            # 使用LLM生成答案
            answer = self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.3,  # 使用较低温度以获得更准确的答案
                max_tokens=1000
            )
            return answer
        except Exception as e:
            return f"生成答案时出错: {str(e)}"
    
    def _extract_sources(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        提取来源信息
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            来源信息列表
        """
        sources = []
        for result in search_results:
            source = {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", "")[:200]  # 只取前200字符
            }
            sources.append(source)
        return sources

