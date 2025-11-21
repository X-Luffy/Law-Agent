"""RAG管理器（整合法律库RAG和Web检索RAG）"""
from typing import List, Dict, Any, Optional
from .legal_rag import LegalRAG
from .web_rag import WebRAG
from ..config.config import Config
from ..tools.web_search import WebSearchTool


class RAGManager:
    """RAG管理器，统一管理法律库RAG和Web检索RAG"""
    
    def __init__(self, config: Config, web_search_tool: Optional[WebSearchTool] = None):
        """
        初始化RAG管理器
        
        Args:
            config: 系统配置
            web_search_tool: Web搜索工具（可选）
        """
        self.config = config
        self.legal_rag = LegalRAG(config)
        self.web_rag = WebRAG(config, web_search_tool)
    
    def retrieve_and_generate(
        self,
        query: str,
        rag_type: str = "auto",  # "legal", "web", "auto"
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        max_context_length: int = 2000
    ) -> Dict[str, Any]:
        """
        检索并生成答案（自动选择RAG类型或指定类型）
        
        Args:
            query: 查询文本
            rag_type: RAG类型（"legal": 法律库RAG, "web": Web检索RAG, "auto": 自动选择）
            top_k: 返回top-k个检索结果（仅用于法律库RAG）
            filter_metadata: 元数据过滤条件（仅用于法律库RAG）
            max_context_length: 最大上下文长度
            
        Returns:
            包含答案、来源等的字典
        """
        # 自动选择RAG类型
        if rag_type == "auto":
            rag_type = self._select_rag_type(query)
        
        # 根据类型选择RAG
        if rag_type == "legal":
            return self.legal_rag.retrieve_and_generate(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
                max_context_length=max_context_length
            )
        elif rag_type == "web":
            return self.web_rag.search_and_generate(
                query=query,
                max_results=top_k,
                max_context_length=max_context_length
            )
        else:
            # 如果类型未知，尝试两种RAG并合并结果
            return self._hybrid_retrieve_and_generate(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
                max_context_length=max_context_length
            )
    
    def _select_rag_type(self, query: str) -> str:
        """
        自动选择RAG类型
        
        Args:
            query: 查询文本
            
        Returns:
            RAG类型（"legal" 或 "web"）
        """
        # 简单的关键词判断（可以后续使用LLM进行更智能的判断）
        legal_keywords = ["法律", "法规", "条例", "条款", "合同", "诉讼", "律师", "法院", "判决"]
        query_lower = query.lower()
        
        # 检查是否包含法律相关关键词
        if any(keyword in query_lower for keyword in legal_keywords):
            return "legal"
        else:
            return "web"
    
    def _hybrid_retrieve_and_generate(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        max_context_length: int = 2000
    ) -> Dict[str, Any]:
        """
        混合检索：同时使用法律库RAG和Web检索RAG，然后合并结果
        
        Args:
            query: 查询文本
            top_k: 返回top-k个检索结果
            filter_metadata: 元数据过滤条件
            max_context_length: 最大上下文长度
            
        Returns:
            合并后的结果字典
        """
        # 并行检索
        legal_result = self.legal_rag.retrieve_and_generate(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata,
            max_context_length=max_context_length // 2
        )
        
        web_result = self.web_rag.search_and_generate(
            query=query,
            max_results=top_k,
            max_context_length=max_context_length // 2
        )
        
        # 合并结果
        combined_answer = self._combine_answers(
            query=query,
            legal_answer=legal_result.get("answer", ""),
            web_answer=web_result.get("answer", ""),
            legal_sources=legal_result.get("sources", []),
            web_sources=web_result.get("sources", [])
        )
        
        return {
            "answer": combined_answer,
            "legal_result": legal_result,
            "web_result": web_result,
            "sources": legal_result.get("sources", []) + web_result.get("sources", [])
        }
    
    def _combine_answers(
        self,
        query: str,
        legal_answer: str,
        web_answer: str,
        legal_sources: List[Dict[str, Any]],
        web_sources: List[Dict[str, Any]]
    ) -> str:
        """
        合并法律库答案和Web答案
        
        Args:
            query: 查询文本
            legal_answer: 法律库答案
            web_answer: Web答案
            legal_sources: 法律库来源
            web_sources: Web来源
            
        Returns:
            合并后的答案
        """
        # 如果法律库有答案，优先使用法律库答案
        if legal_answer and "未找到" not in legal_answer and "抱歉" not in legal_answer:
            if web_answer and "未找到" not in web_answer and "抱歉" not in web_answer:
                # 两种都有答案，合并
                return f"{legal_answer}\n\n补充信息（来自网络搜索）：\n{web_answer}"
            else:
                return legal_answer
        elif web_answer and "未找到" not in web_answer and "抱歉" not in web_answer:
            return web_answer
        else:
            return "抱歉，未能找到相关信息。"
    
    def add_legal_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        添加法律文档到知识库
        
        Args:
            documents: 文档列表
            metadatas: 元数据列表（如法律类型、章节、日期等）
            ids: 文档ID列表
        """
        self.legal_rag.add_legal_documents(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def format_context_for_prompt(
        self,
        retrieved_docs: List[Dict[str, Any]],
        max_length: int = 2000
    ) -> str:
        """
        将检索到的文档格式化为prompt格式
        
        Args:
            retrieved_docs: 检索到的文档列表
            max_length: 最大长度限制
            
        Returns:
            格式化后的上下文文本
        """
        context_parts = []
        current_length = 0
        
        for doc in retrieved_docs:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            score = doc.get("score", 0.0)
            
            # 格式化文档信息
            doc_text = f"[文档 {len(context_parts) + 1}]"
            if metadata:
                doc_text += f" ({metadata.get('type', '未知类型')})"
            doc_text += f"\n{content}\n"
            
            # 检查长度限制
            if current_length + len(doc_text) > max_length:
                break
            
            context_parts.append(doc_text)
            current_length += len(doc_text)
        
        return "\n".join(context_parts)
