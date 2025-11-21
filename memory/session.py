"""短期记忆Session管理"""
from typing import List, Dict, Any, Optional
from collections import deque
from ..config.config import Config


class SessionMemory:
    """短期记忆Session，用于存储当前会话的对话历史"""
    
    def __init__(self, config: Config, session_id: str):
        """
        初始化Session记忆
        
        Args:
            config: 系统配置
            session_id: 会话ID
        """
        self.config = config
        self.session_id = session_id
        self.memory = deque(maxlen=config.session_memory_size)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """
        添加消息到session记忆
        
        Args:
            role: 角色（user/assistant）
            content: 消息内容
            metadata: 元数据（如意图、工具使用等）
        """
        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        self.memory.append(message)
    
    def get_recent_messages(self, n: int) -> List[Dict[str, Any]]:
        """
        获取最近N条消息
        
        Args:
            n: 消息数量
            
        Returns:
            消息列表
        """
        return list(self.memory)[-n:]
    
    def get_all_messages(self) -> List[Dict[str, Any]]:
        """
        获取所有消息
        
        Returns:
            所有消息列表
        """
        return list(self.memory)
    
    def clear(self):
        """清空session记忆"""
        self.memory.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取session摘要
        
        Returns:
            session摘要信息
        """
        return {
            "session_id": self.session_id,
            "message_count": len(self.memory),
            "recent_messages": self.get_recent_messages(5)
        }

