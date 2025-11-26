"""上下文管理器"""
from typing import List, Dict, Any, Optional
from .refiner import ContextRefiner
# 处理相对导入问题
try:
    from ..config.config import Config
    from ..schema import Message
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config
    from schema import Message


class ContextManager:
    """上下文管理器，负责窗口裁剪和上下文精炼"""
    
    def __init__(self, config: Config):
        """
        初始化上下文管理器
        
        Args:
            config: 系统配置
        """
        self.config = config
        self.window_size = config.context_window_size
        self.refine_threshold = config.context_refine_threshold
        self.refiner = ContextRefiner(config)
        
        # 存储精炼后的上下文历史
        self.refined_contexts: List[Dict[str, Any]] = []
    
    def get_context(
        self, 
        conversation_history: List[Dict[str, Any]],
        relevant_memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取当前上下文（窗口裁剪 + 上下文精炼）
        
        Args:
            conversation_history: 对话历史（可以是Message对象列表或字典列表）
            relevant_memory: 相关记忆（长期和短期）
            
        Returns:
            上下文字典，包含recent_messages, refined_context, memory等
        """
        # 转换为统一格式
        history = self._normalize_history(conversation_history)
        
        # 窗口裁剪：保留最近N轮对话
        recent_messages = self._window_crop(history)
        
        # 如果对话历史超过阈值，进行上下文精炼
        refined_context = None
        if len(history) > self.refine_threshold:
            # 获取需要精炼的往期对话（排除最近N轮）
            old_messages = history[:-self.window_size]
            
            if old_messages:
                # 使用embedding进行上下文精炼
                refined_context = self.refiner.refine(old_messages)
                
                # 保存精炼后的上下文（会通过memory_manager持久化到向量数据库）
                self.refined_contexts.append(refined_context)
        
        # 合并所有精炼后的上下文
        all_refined_context = self._merge_refined_contexts()
        
        return {
            "recent_messages": recent_messages,
            "refined_context": all_refined_context,
            "long_term_memory": relevant_memory.get("long_term", []),
            "short_term_memory": relevant_memory.get("short_term", [])
        }
    
    def _normalize_history(
        self,
        conversation_history: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        标准化对话历史格式
        
        Args:
            conversation_history: 对话历史（可以是Message对象列表或字典列表）
            
        Returns:
            标准化的字典列表
        """
        normalized = []
        for msg in conversation_history:
            if isinstance(msg, Message):
                normalized.append(msg.to_dict())
            elif isinstance(msg, dict):
                normalized.append(msg)
            else:
                # 尝试转换为字典
                if hasattr(msg, "to_dict"):
                    normalized.append(msg.to_dict())
                else:
                    # 使用默认格式
                    normalized.append({
                        "role": getattr(msg, "role", "unknown"),
                        "content": getattr(msg, "content", str(msg))
                    })
        return normalized
    
    def _window_crop(
        self, 
        conversation_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        窗口裁剪：保留最近N轮对话
        
        Args:
            conversation_history: 完整对话历史
            
        Returns:
            裁剪后的对话历史
        """
        if len(conversation_history) <= self.window_size:
            return conversation_history
        
        # 保留最近window_size轮对话
        return conversation_history[-self.window_size:]
    
    def _merge_refined_contexts(self) -> Optional[Dict[str, Any]]:
        """
        合并所有精炼后的上下文
        
        Returns:
            合并后的精炼上下文
        """
        if not self.refined_contexts:
            return None
        
        # 合并摘要
        summaries = [ctx.get("summary", "") for ctx in self.refined_contexts if ctx.get("summary")]
        merged_summary = "\n\n".join(summaries) if summaries else ""
        
        # 合并关键点
        all_key_points = []
        for ctx in self.refined_contexts:
            key_points = ctx.get("key_points", [])
            all_key_points.extend(key_points)
        
        # 去重关键点（基于相似度）
        unique_key_points = self._deduplicate_key_points(all_key_points)
        
        # 合并重要信息
        all_important_info = {
            "user_intents": [],
            "decisions": [],
            "key_entities": []
        }
        for ctx in self.refined_contexts:
            important_info = ctx.get("important_info", {})
            for key in all_important_info:
                if key in important_info:
                    all_important_info[key].extend(important_info[key])
        
        return {
            "summary": merged_summary,
            "key_points": unique_key_points,
            "important_info": all_important_info,
            "context_count": len(self.refined_contexts)
        }
    
    def _deduplicate_key_points(
        self,
        key_points: List[str],
        similarity_threshold: float = 0.8
    ) -> List[str]:
        """
        去重关键点（基于embedding相似度）
        
        Args:
            key_points: 关键点列表
            similarity_threshold: 相似度阈值
            
        Returns:
            去重后的关键点列表
        """
        if len(key_points) <= 1:
            return key_points
        
        try:
            # 使用embedding计算相似度
            embeddings = self.refiner.embedding_model.encode(key_points)
            
            unique_points = []
            used_indices = set()
            
            for i, point in enumerate(key_points):
                if i in used_indices:
                    continue
                
                unique_points.append(point)
                
                # 找到相似的点并标记为已使用
                for j in range(i + 1, len(key_points)):
                    if j in used_indices:
                        continue
                    
                    similarity = self.refiner._cosine_similarity(
                        embeddings[i],
                        embeddings[j]
                    )
                    
                    if similarity >= similarity_threshold:
                        used_indices.add(j)
            
            return unique_points
        
        except Exception:
            # 如果embedding失败，使用简单的文本去重
            return list(dict.fromkeys(key_points))  # 保持顺序的去重
    
    def clear_refined_contexts(self):
        """清空精炼后的上下文历史"""
        self.refined_contexts.clear()
    
    def get_refined_contexts_count(self) -> int:
        """获取精炼后的上下文数量"""
        return len(self.refined_contexts)

