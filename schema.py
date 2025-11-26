"""数据模式定义"""
from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field


class Role(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


ROLE_TYPE = Role | str

# 定义状态回调函数类型
# 参数: stage (阶段名称/标题), message (详细信息), state (状态: running/complete/error)
StatusCallback = Callable[[str, str, str], None]


class AgentState(str, Enum):
    """Agent状态"""
    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    FINISHED = "finished"  # 已完成
    ERROR = "error"  # 错误
    PROFESSIONAL_ANSWER = "professional_answer"  # 专业回答（基于文档/法律条文）


class AnswerSource(str, Enum):
    """答案来源"""
    DOCUMENT = "document"  # 基于文档
    WEB_SEARCH = "web_search"  # 基于网络搜索
    KNOWLEDGE_BASE = "knowledge_base"  # 基于知识库
    MEMORY = "memory"  # 基于记忆
    GENERAL = "general"  # 一般回答
    UNABLE_TO_ANSWER = "unable_to_answer"  # 无法回答


class LegalDomain(str, Enum):
    """法律领域分类"""
    LABOR_LAW = "Labor_Law"  # 劳动法：裁员、工资
    FAMILY_LAW = "Family_Law"  # 婚姻家事：离婚、抚养权
    CONTRACT_LAW = "Contract_Law"  # 合同纠纷
    CORPORATE_LAW = "Corporate_Law"  # 公司法
    CRIMINAL_LAW = "Criminal_Law"  # 刑法
    PROCEDURAL_QUERY = "Procedural_Query"  # 程序性问题：去哪个法院起诉、诉讼费多少
    NON_LEGAL = "Non_Legal"  # 非法律问题（闲聊、天气、其他专业领域等）


class LegalIntent(str, Enum):
    """法律专业意图类型"""
    QA_RETRIEVAL = "QA_Retrieval"  # 法律法规、法条、类似案例查询
    CASE_ANALYSIS = "Case_Analysis"  # 案情分析（用户描述了一个故事）
    DOC_DRAFTING = "Doc_Drafting"  # 起草文书（合同、起诉状、律师函）
    CALCULATION = "Calculation"  # 计算赔偿金、刑期、诉讼费
    REVIEW_CONTRACT = "Review_Contract"  # 审查合同风险
    CLARIFICATION = "Clarification"  # 信息不足，需要反问


@dataclass
class Message:
    """消息类"""
    role: ROLE_TYPE
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    
    @classmethod
    def system_message(cls, content: str) -> "Message":
        """创建系统消息"""
        return cls(role=Role.SYSTEM, content=content)
    
    @classmethod
    def user_message(cls, content: str) -> "Message":
        """创建用户消息"""
        return cls(role=Role.USER, content=content)
    
    @classmethod
    def assistant_message(cls, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> "Message":
        """创建助手消息"""
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls)
    
    @classmethod
    def tool_message(cls, content: str, tool_call_id: str = "", name: str = "") -> "Message":
        """创建工具消息"""
        return cls(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（OpenAI格式）"""
        role = self.role.value if isinstance(self.role, Role) else self.role
        
        # 对于tool消息，OpenAI格式需要role="tool"且包含tool_call_id
        if role == "tool":
            result = {
                "role": "tool",
                "content": self.content,
                "tool_call_id": self.tool_call_id
            }
        else:
            result = {
                "role": role,
                "content": self.content
            }
            # assistant消息可能包含tool_calls
            if self.tool_calls:
                result["tool_calls"] = self.tool_calls
        return result


@dataclass
class Memory:
    """记忆类"""
    messages: List[Message] = field(default_factory=list)
    max_size: int = 100
    
    def add_message(self, message: Message):
        """添加消息"""
        self.messages.append(message)
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]
    
    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """获取最近N条消息"""
        return self.messages[-n:] if len(self.messages) > n else self.messages
    
    def clear(self):
        """清空消息"""
        self.messages.clear()
