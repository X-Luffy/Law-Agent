"""记忆管理器：统一管理短期记忆、全局信息和长期记忆"""
from typing import Dict, Any, List, Optional
from .session import SessionMemory
from .vector_db import VectorDatabase
from .global_memory import GlobalMemory
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


class MemoryManager:
    """
    记忆管理器，统一管理三种记忆：
    1. 短期记忆（SessionMemory）：最近几次对话记录
    2. 全局信息（GlobalMemory）：CoreAgent提取的关键属性（当事人、金额、时间等硬指标）
    3. 长期记忆（VectorDatabase）：久远对话记录的embedding向量化存储
    """
    
    def __init__(self, config: Config, vector_store=None):
        """
        初始化记忆管理器
        
        Args:
            config: 系统配置
            vector_store: 向量存储接口（可选）
        """
        self.config = config
        
        # 短期记忆：最近几次对话记录
        self.sessions: Dict[str, SessionMemory] = {}
        
        # 全局信息：CoreAgent提取的关键属性
        self.global_memory = GlobalMemory(config)
        
        # 长期记忆：久远对话记录的embedding向量化存储
        self.vector_db = VectorDatabase(config, vector_store=vector_store)
    
    def get_session(self, session_id: str) -> SessionMemory:
        """
        获取或创建session记忆
        
        Args:
            session_id: 会话ID
            
        Returns:
            Session记忆实例
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionMemory(self.config, session_id)
        return self.sessions[session_id]
    
    def save_conversation(
        self, 
        session_id: str, 
        user_message: str, 
        assistant_message: str,
        intent: Optional[str] = None
    ) -> str:
        """
        保存对话到记忆（短期记忆 + 长期记忆向量数据库）
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            assistant_message: Assistant回复
            intent: 用户意图
            
        Returns:
            存储的ID
        """
        # 保存到短期记忆
        session = self.get_session(session_id)
        session.add_message("user", user_message, {"intent": intent})
        session.add_message("assistant", assistant_message)
        
        # 保存到长期记忆（向量数据库）
        conversation_text = f"User: {user_message}\nAssistant: {assistant_message}"
        metadata = {
            "session_id": session_id,
            "intent": intent,
            "type": "conversation"
        }
        memory_id = self.vector_db.add_memory(conversation_text, metadata)
        
        return memory_id
    
    def save_refined_context(
        self,
        summary: str,
        key_points: List[str],
        important_info: Dict[str, Any]
    ) -> str:
        """
        保存精炼后的上下文到长期记忆
        
        Args:
            summary: 摘要
            key_points: 关键点列表
            important_info: 重要信息
            
        Returns:
            存储的ID
        """
        return self.vector_db.add_refined_context(
            summary=summary,
            key_points=key_points,
            important_info=important_info
        )
    
    def save_tool_description(
        self,
        tool_name: str,
        description: str
    ) -> str:
        """
        保存工具描述到长期记忆（用于工具选择）
        
        Args:
            tool_name: 工具名称
            description: 工具描述
            
        Returns:
            存储的ID
        """
        return self.vector_db.add_tool_description(
            tool_name=tool_name,
            description=description
        )
    
    def retrieve_relevant_memory(
        self, 
        query: str, 
        session_id: str,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        检索相关记忆（从长期记忆和短期记忆）
        
        Args:
            query: 查询文本
            session_id: 会话ID
            top_k: 返回top-k结果
            
        Returns:
            相关记忆字典，包含long_term和short_term
        """
        # 从长期记忆（向量数据库）检索
        long_term_memories = self.vector_db.search(query, top_k=top_k)
        
        # 从短期记忆（session）获取最近对话
        session = self.get_session(session_id)
        recent_messages = session.get_recent_messages(5)
        
        return {
            "long_term": long_term_memories,
            "short_term": recent_messages
        }
    
    def retrieve_refined_contexts(
        self,
        query: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        检索精炼后的上下文
        
        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            
        Returns:
            精炼后的上下文列表
        """
        filter_metadata = {"type": "refined_context"}
        return self.vector_db.search(query, top_k=top_k, filter_metadata=filter_metadata)
    
    def retrieve_tool_descriptions(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        检索相关工具描述
        
        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            
        Returns:
            相关工具描述列表
        """
        return self.vector_db.search_tool_descriptions(query, top_k=top_k)
    
    def reset_session(self, session_id: str):
        """
        重置session
        
        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            self.sessions[session_id].clear()
            del self.sessions[session_id]
    
    def get_global_memory(self) -> GlobalMemory:
        """
        获取全局信息记忆
        
        Returns:
            GlobalMemory实例
        """
        return self.global_memory
    
    def update_global_memory(
        self,
        domain: Optional[str] = None,
        intent: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None
    ):
        """
        更新全局信息记忆
        
        Args:
            domain: 法律领域（可选）
            intent: 法律意图（可选）
            entities: 关键实体字典（可选）
        """
        self.global_memory.update(domain=domain, intent=intent, entities=entities)
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """
        获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "short_term_sessions": len(self.sessions),
            "global_info": {
                "domain": self.global_memory.global_info.get("domain"),
                "intent": self.global_memory.global_info.get("intent"),
                "entities_count": {
                    "persons": len(self.global_memory.global_info["entities"].get("persons", [])),
                    "amounts": len(self.global_memory.global_info["entities"].get("amounts", [])),
                    "dates": len(self.global_memory.global_info["entities"].get("dates", [])),
                    "locations": len(self.global_memory.global_info["entities"].get("locations", []))
                }
            },
            "long_term_memories": {
                "total": self.vector_db.count_memories(),
                "conversations": self.vector_db.count_memories(
                    filter_metadata={"type": "conversation"}
                ),
                "refined_contexts": self.vector_db.count_memories(
                    filter_metadata={"type": "refined_context"}
                )
            }
        }
