"""全局信息记忆：存储CoreAgent提取的关键属性（当事人、金额、时间等硬指标）"""
from typing import Dict, Any, List, Optional
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


class GlobalMemory:
    """
    全局信息记忆（State Memory）
    
    存储CoreAgent从用户query中提取的关键属性：
    - 当事人（persons）
    - 金额（amounts）
    - 时间（dates）
    - 地点（locations）
    - 其他关键信息（other）
    
    防止模型遗忘这些硬指标。
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化全局信息记忆
        
        Args:
            config: 系统配置（可选）
        """
        self.config = config or Config()
        
        # 全局信息存储
        self.global_info: Dict[str, Any] = {
            "domain": None,  # 当前法律领域
            "intent": None,  # 当前法律意图
            "entities": {
                "persons": [],  # 人名列表
                "amounts": [],  # 金额列表
                "dates": [],  # 时间列表
                "locations": [],  # 地点列表
                "other": {}  # 其他关键信息
            },
            "context": []  # 对话历史摘要
        }
    
    def update(
        self,
        domain: Optional[str] = None,
        intent: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None
    ):
        """
        更新全局信息
        
        Args:
            domain: 法律领域（可选）
            intent: 法律意图（可选）
            entities: 关键实体字典（可选）
        """
        if domain:
            self.global_info["domain"] = domain
        if intent:
            self.global_info["intent"] = intent
        if entities:
            # 合并实体信息（追加而不是替换）
            current_entities = self.global_info["entities"]
            for key, value in entities.items():
                if key in current_entities:
                    if isinstance(value, list):
                        # 列表类型：合并去重
                        current_entities[key] = list(set(current_entities[key] + value))
                    elif isinstance(value, dict):
                        # 字典类型：合并
                        current_entities[key].update(value)
                    else:
                        current_entities[key] = value
                else:
                    current_entities[key] = value
    
    def get(self) -> Dict[str, Any]:
        """
        获取全局信息
        
        Returns:
            全局信息字典
        """
        return self.global_info.copy()
    
    def get_entities(self) -> Dict[str, Any]:
        """
        获取关键实体
        
        Returns:
            关键实体字典
        """
        return self.global_info["entities"].copy()
    
    def clear(self):
        """清空全局信息"""
        self.global_info = {
            "domain": None,
            "intent": None,
            "entities": {
                "persons": [],
                "amounts": [],
                "dates": [],
                "locations": [],
                "other": {}
            },
            "context": []
        }
    
    def to_string(self) -> str:
        """
        将全局信息转换为字符串（用于prompt）
        
        Returns:
            格式化的字符串
        """
        parts = []
        if self.global_info.get("domain"):
            parts.append(f"当前法律领域：{self.global_info['domain']}")
        if self.global_info.get("intent"):
            parts.append(f"当前法律意图：{self.global_info['intent']}")
        
        entities = self.global_info.get("entities", {})
        if entities.get("persons"):
            parts.append(f"已知当事人：{', '.join(entities['persons'])}")
        if entities.get("amounts"):
            parts.append(f"已知金额：{', '.join(entities['amounts'])}")
        if entities.get("dates"):
            parts.append(f"已知时间：{', '.join(entities['dates'])}")
        if entities.get("locations"):
            parts.append(f"已知地点：{', '.join(entities['locations'])}")
        
        return "\n".join(parts) if parts else "暂无全局信息"

