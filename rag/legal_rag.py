"""法律专业信息库RAG"""
from typing import List, Dict, Any, Optional
from .retriever import RAGRetriever
from ..llm.llm import LLM
from ..config.config import Config


class LegalRAG:
    """法律专业信息库RAG，从法律专业信息库中检索相关片段，使用LLM整合生成答案"""
    
    def __init__(self, config: Config):
        """
        初始化法律专业信息库RAG
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.retriever = RAGRetriever(config)
        self.llm = LLM(config)
    
    def retrieve_and_generate(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        max_context_length: int = 2000
    ) -> Dict[str, Any]:
        """
        检索相关法律信息并生成答案
        
        Args:
            query: 查询文本
            top_k: 返回top-k个检索结果
            filter_metadata: 元数据过滤条件（如法律类型、章节等）
            max_context_length: 最大上下文长度
            
        Returns:
            包含答案、检索到的文档、元数据等的字典
        """
        # 1. 从法律专业信息库检索相关片段
        retrieved_docs = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        if not retrieved_docs:
            return {
                "answer": "抱歉，在法律专业信息库中未找到相关信息。",
                "retrieved_docs": [],
                "sources": [],
                "answer_source": "unable_to_answer"
            }
        
        # 2. 格式化检索到的文档为上下文
        context = self._format_context(retrieved_docs, max_context_length)
        
        # 3. 使用LLM整合生成答案
        answer = self._generate_answer(query, context, retrieved_docs)
        
        # 4. 提取来源信息
        sources = self._extract_sources(retrieved_docs)
        
        return {
            "answer": answer,
            "retrieved_docs": retrieved_docs,
            "sources": sources,
            "context_length": len(context),
            "answer_source": "document"  # 标记为基于文档的回答
        }
    
    def _format_context(
        self,
        retrieved_docs: List[Dict[str, Any]],
        max_length: int = 2000
    ) -> str:
        """
        格式化检索到的文档为上下文
        
        Args:
            retrieved_docs: 检索到的文档列表
            max_length: 最大长度限制
            
        Returns:
            格式化后的上下文文本
        """
        context_parts = []
        current_length = 0
        
        for i, doc in enumerate(retrieved_docs):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            score = doc.get("score", 0.0)
            
            # 格式化文档信息
            doc_text = f"[法律文档片段 {i + 1}]"
            if metadata:
                law_type = metadata.get("law_type", "")
                chapter = metadata.get("chapter", "")
                if law_type:
                    doc_text += f" 法律类型: {law_type}"
                if chapter:
                    doc_text += f" 章节: {chapter}"
            doc_text += f"\n{content}\n"
            
            # 检查长度限制
            if current_length + len(doc_text) > max_length:
                break
            
            context_parts.append(doc_text)
            current_length += len(doc_text)
        
        return "\n".join(context_parts)
    
    def _generate_answer(
        self,
        query: str,
        context: str,
        retrieved_docs: List[Dict[str, Any]]
    ) -> str:
        """
        使用LLM整合生成答案
        
        Args:
            query: 查询文本
            context: 检索到的上下文
            retrieved_docs: 检索到的文档列表
            
        Returns:
            生成的答案
        """
        # 构建prompt（增强版，避免幻觉）
        system_prompt = """你是一个专业的法律助手。请根据提供的法律文档片段，准确、完整地回答用户的问题。

**重要约束**：
1. **严格基于文档**：答案必须严格基于提供的法律文档片段，不得编造或推测法律条文
2. **无法回答时明确说明**：如果文档中没有相关信息，必须明确说明"根据提供的法律文档，无法找到相关信息"或"无法回答此问题"
3. **引用具体法条**：必须引用具体的法律条款、章节或案例编号
4. **禁止幻觉**：严禁编造法律条文、案例或事实，如果不知道，必须说明
5. **专业回答格式**：开头说明"根据检索到的法律文档..."，并明确标注来源

**回答格式**：
- 开头说明"根据检索到的法律文档/法律条文..."
- 引用具体法条："依据《XX法》第X条..."
- 如果无法回答：明确说明"无法回答"或"未找到相关信息"

要求：
1. 答案必须基于提供的法律文档片段
2. 答案要准确、完整、专业
3. 如果文档中没有相关信息，请明确说明
4. 必须引用具体的法律条款或章节
5. 使用清晰、易懂的语言"""
        
        user_prompt = f"""用户问题：{query}

相关法律文档片段：
{context}

请根据上述法律文档片段，回答用户的问题。如果文档中没有相关信息，请明确说明。"""
        
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
        retrieved_docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        提取来源信息
        
        Args:
            retrieved_docs: 检索到的文档列表
            
        Returns:
            来源信息列表
        """
        sources = []
        for doc in retrieved_docs:
            metadata = doc.get("metadata", {})
            source = {
                "content": doc.get("content", "")[:200],  # 只取前200字符
                "score": doc.get("score", 0.0),
                "law_type": metadata.get("law_type", ""),
                "chapter": metadata.get("chapter", ""),
                "id": doc.get("id", "")
            }
            sources.append(source)
        return sources
    
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
        self.retriever.add_documents(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

