"""ReActAgent类"""
from abc import abstractmethod
from typing import Optional
from .base import BaseAgent
# 处理相对导入问题
try:
    from ..schema import AgentState, Memory
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from schema import AgentState, Memory
    from config.config import Config


class ReActAgent(BaseAgent):
    """ReActAgent，继承BaseAgent，定义think和act抽象函数，实现思考-行动循环"""
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10
    ):
        """
        初始化ReActAgent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数（思考-行动循环的最大步数）
        """
        super().__init__(
            name=name,
            description=description,
            system_prompt=system_prompt,
            next_step_prompt=next_step_prompt,
            config=config,
            memory=memory,
            state=state,
            max_steps=max_steps
        )
    
    @abstractmethod
    async def think(self) -> bool:
        """
        思考阶段：处理当前状态并决定下一步行动
        
        Returns:
            是否需要执行行动（True表示需要执行，False表示不需要）
        """
        pass
    
    @abstractmethod
    async def act(self) -> str:
        """
        行动阶段：执行决定的行动
        
        Returns:
            行动执行结果
        """
        pass
    
    async def step(self) -> str:
        """
        执行一步：思考-行动循环
        
        Returns:
            步骤执行结果
        """
        # 思考阶段
        should_act = await self.think()
        
        if not should_act:
            return "Thinking complete - no action needed"
        
        # 行动阶段
        return await self.act()
