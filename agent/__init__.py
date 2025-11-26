"""Agent核心模块"""
# 处理相对导入问题
try:
    from .base import BaseAgent
    from .react import ReActAgent
    from .toolcall import ToolCallAgent
    from .agent import Agent
    from .core_agent import CoreAgent
    from .specialized_agent import SpecializedAgent
    from ..schema import AgentState, LegalDomain, LegalIntent
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agent.base import BaseAgent
    from agent.react import ReActAgent
    from agent.toolcall import ToolCallAgent
    from agent.agent import Agent
    from agent.core_agent import CoreAgent
    from agent.specialized_agent import SpecializedAgent
    from schema import AgentState, LegalDomain, LegalIntent

__all__ = [
    'BaseAgent', 
    'ReActAgent', 
    'ToolCallAgent', 
    'Agent', 
    'CoreAgent',
    'SpecializedAgent',
    'AgentState',
    'LegalDomain',
    'LegalIntent'
]

