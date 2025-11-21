"""BaseAgent基类"""
from abc import ABC, abstractmethod
from typing import Optional, List
from ..schema import AgentState, Memory, Message, ROLE_TYPE
from ..config.config import Config


class BaseAgent(ABC):
    """Agent基类，定义Agent的基本组成成分"""
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10
    ):
        """
        初始化BaseAgent
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数
        """
        self.name = name
        self.description = description or f"An agent named {name}"
        self.system_prompt = system_prompt
        self.config = config or Config()
        self.memory = memory or Memory()
        self.state = state
        self.max_steps = max_steps
        self.current_step = 0
    
    def update_memory(self, role: ROLE_TYPE, content: str, **kwargs):
        """
        更新记忆
        
        Args:
            role: 消息角色
            content: 消息内容
            **kwargs: 其他参数（如tool_call_id等）
        """
        if role == "system":
            message = Message.system_message(content)
        elif role == "user":
            message = Message.user_message(content)
        elif role == "assistant":
            message = Message.assistant_message(content, kwargs.get("tool_calls"))
        elif role == "tool":
            message = Message.tool_message(
                content, 
                kwargs.get("tool_call_id", ""),
                kwargs.get("name")
            )
        else:
            raise ValueError(f"Unsupported role: {role}")
        
        self.memory.add_message(message)
    
    def get_messages(self) -> List[Message]:
        """获取所有消息"""
        return self.memory.messages
    
    def reset(self):
        """重置Agent状态"""
        self.state = AgentState.IDLE
        self.current_step = 0
        self.memory.clear()
    
    @abstractmethod
    async def step(self) -> str:
        """
        执行一步操作
        
        Returns:
            步骤执行结果
        """
        pass
    
    async def run(self, request: Optional[str] = None) -> str:
        """
        运行Agent主循环
        
        Args:
            request: 可选的初始用户请求
            
        Returns:
            执行结果摘要
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")
        
        if request:
            self.update_memory("user", request)
        
        self.state = AgentState.RUNNING
        results = []
        
        try:
            while self.current_step < self.max_steps and self.state != AgentState.FINISHED:
                self.current_step += 1
                step_result = await self.step()
                results.append(f"Step {self.current_step}: {step_result}")
                
                if self.state == AgentState.FINISHED:
                    break
            
            if self.current_step >= self.max_steps:
                self.state = AgentState.IDLE
                results.append(f"Terminated: Reached max steps ({self.max_steps})")
        except Exception as e:
            self.state = AgentState.ERROR
            results.append(f"Error: {str(e)}")
            raise
        
        return "\n".join(results) if results else "No steps executed"

