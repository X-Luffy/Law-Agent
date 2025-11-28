"""BaseAgent基类"""
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Optional, List
# 处理相对导入问题
try:
    from ..schema import AgentState, Memory, Message, ROLE_TYPE, StatusCallback
    from ..config.config import Config
    from ..models.llm import LLM
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from schema import AgentState, Memory, Message, ROLE_TYPE, StatusCallback
    from config.config import Config
    from models.llm import LLM


class BaseAgent(ABC):
    """Agent基类，定义Agent的基本组成成分
    
    提供状态管理、记忆管理和基于步骤的执行循环的基础功能。
    子类必须实现 step 方法。
    """
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,  # 可选，如果为None则无状态执行
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10,
        llm: Optional[LLM] = None,
        duplicate_threshold: int = 2,
        status_callback: Optional[StatusCallback] = None
    ):
        """
        初始化BaseAgent（支持无状态执行）
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词
            config: 系统配置
            memory: 记忆存储（可选，如果为None则无状态执行，会在run时创建临时memory）
            state: Agent状态
            max_steps: 最大执行步数
            llm: 语言模型实例（可选，如果不提供则使用config创建）
            duplicate_threshold: 检测卡住状态的重复阈值
            status_callback: 状态更新回调函数
        """
        self.name = name
        self.description = description or f"An agent named {name}"
        self.system_prompt = system_prompt
        self.next_step_prompt = next_step_prompt
        self.config = config or Config()
        self.memory = memory  # 允许为None（无状态）
        self.state = state
        self.max_steps = max_steps
        self.current_step = 0
        self.duplicate_threshold = duplicate_threshold
        self.status_callback = status_callback
        
        # 初始化LLM（如果未提供）
        if llm is None or not isinstance(llm, LLM):
            self.llm = LLM(self.config)
        else:
            self.llm = llm

    def update_status(self, stage: str, message: str, state: str = "running"):
        """更新状态"""
        if self.status_callback:
            try:
                self.status_callback(stage, message, state)
            except Exception as e:
                print(f"Warning: Failed to update status: {e}")
    
    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """上下文管理器，用于安全的Agent状态转换
        
        Args:
            new_state: 要转换到的状态
            
        Yields:
            None: 允许在新状态下执行
            
        Raises:
            ValueError: 如果new_state无效
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")
        
        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # 失败时转换到ERROR状态
            raise e
        finally:
            self.state = previous_state  # 恢复到之前的状态
    
    def update_memory(
        self,
        role: ROLE_TYPE,
        content: str,
        base64_image: Optional[str] = None,
        **kwargs
    ):
        """
        添加消息到Agent的记忆中（支持无状态执行）
        
        Args:
            role: 消息角色（user, system, assistant, tool）
            content: 消息内容
            base64_image: 可选的base64编码图片
            **kwargs: 其他参数（如tool_call_id用于tool消息）
            
        Raises:
            ValueError: 如果角色不支持或memory为None
        """
        if self.memory is None:
            # 无状态执行时，创建临时memory
            self.memory = Memory()
        
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": lambda content, **kw: Message.assistant_message(content, kw.get("tool_calls")),
            "tool": lambda content, **kw: Message.tool_message(
                content,
                kw.get("tool_call_id", ""),
                kw.get("name", "")
            ),
        }
        
        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")
        
        # 根据角色创建消息
        if role == "tool":
            # tool消息需要tool_call_id和name
            message = message_map[role](content, **kwargs)
        elif role == "assistant":
            # assistant消息可能需要tool_calls
            message = message_map[role](content, **kwargs)
        else:
            # user和system消息
            message = message_map[role](content)
        
        # 如果支持base64_image，可以在这里添加（需要Message类支持）
        # 目前Message类可能不支持base64_image，所以先不添加
        
        self.memory.add_message(message)
    
    @property
    def messages(self) -> List[Message]:
        """获取Agent记忆中的消息列表（支持无状态执行）"""
        if self.memory is None:
            return []
        return self.memory.messages
    
    @messages.setter
    def messages(self, value: List[Message]):
        """设置Agent记忆中的消息列表"""
        self.memory.messages = value
    
    def get_messages(self) -> List[Message]:
        """获取所有消息（向后兼容方法）"""
        return self.memory.messages
    
    def reset(self):
        """重置Agent状态"""
        self.state = AgentState.IDLE
        self.current_step = 0
        self.memory.clear()
    
    def is_stuck(self) -> bool:
        """检查Agent是否卡在循环中（通过检测重复内容）
        
        Returns:
            如果检测到卡住状态返回True
        """
        if self.memory is None or len(self.memory.messages) < 2:
            return False
        
        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False
        
        # 统计相同内容的出现次数
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )
        
        return duplicate_count >= self.duplicate_threshold
    
    def handle_stuck_state(self):
        """处理卡住状态，通过添加提示来改变策略"""
        stuck_prompt = "Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        if self.next_step_prompt:
            self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        else:
            self.next_step_prompt = stuck_prompt
        print(f"⚠️ Agent detected stuck state. Added prompt: {stuck_prompt}")
    
    @abstractmethod
    async def step(self) -> str:
        """
        执行一步操作
        
        Returns:
            步骤执行结果
        """
        pass
    
    async def run(self, request: Optional[str] = None, status_callback: Optional[StatusCallback] = None, context: str = "") -> str:
        """
        异步执行Agent的主循环（支持无状态执行）
        
        Args:
            request: 可选的初始用户请求
            status_callback: 可选的状态回调函数
            context: 上下文信息（可选，用于无状态执行）
            
        Returns:
            执行结果摘要字符串
            
        Raises:
            RuntimeError: 如果Agent启动时不在IDLE状态
        """
        # 更新回调函数
        if status_callback:
            self.status_callback = status_callback

        # 修复第二个query卡死问题：确保状态为IDLE
        if self.state != AgentState.IDLE:
            print(f"[DEBUG] Agent状态不是IDLE: {self.state}，强制重置为IDLE")
            self.state = AgentState.IDLE
            self.current_step = 0
        
        # 如果memory为None（无状态），创建临时memory用于执行
        temp_memory = None
        if self.memory is None:
            temp_memory = Memory()
            self.memory = temp_memory
        
        # 如果有context，将其添加到系统提示中
        original_system_prompt = None
        if context:
            original_system_prompt = self.system_prompt
            self.system_prompt = f"{self.system_prompt}\n\n上下文信息：\n{context}"
        
        try:
            if request:
                self.update_memory("user", request)
            
            results: List[str] = []
            async with self.state_context(AgentState.RUNNING):
                while (
                    self.current_step < self.max_steps and self.state != AgentState.FINISHED
                ):
                    self.current_step += 1
                    print(f"Executing step {self.current_step}/{self.max_steps}")
                    step_result = await self.step()
                    
                    # 检查是否卡住
                    if self.is_stuck():
                        self.handle_stuck_state()
                    
                    results.append(f"Step {self.current_step}: {step_result}")
                
                if self.current_step >= self.max_steps:
                    # 达到最大步数，强制生成最终答案
                    print(f"⚠️ Reached max steps ({self.max_steps}), forcing final answer generation...")
                    self.update_status("⚠️ 达到最大步数", "已达到最大步数限制，正在生成最终回答...", "running")
                    
                    # 添加一个系统消息，强制LLM生成最终答案
                    self.update_memory("system", "已达到最大步数限制。请立即基于现有信息生成完整的最终回答，不要再调用任何工具。")
                    
                    # 再次调用LLM生成最终答案
                    try:
                        # 获取最近的对话上下文
                        recent_messages = self.memory.get_recent_messages(30)
                        messages_dict = []
                        for msg in recent_messages:
                            if isinstance(msg, Message):
                                messages_dict.append(msg.to_dict())
                            elif isinstance(msg, dict):
                                messages_dict.append(msg)
                        
                        # 不提供tools，强制LLM只生成文本回答
                        if hasattr(self, 'llm'):
                            response = self.llm.chat(
                                messages=messages_dict,
                                temperature=0.7,
                                max_tokens=self.config.llm_max_tokens
                            )
                            
                            if isinstance(response, dict):
                                final_content = response.get("content", "")
                            else:
                                final_content = str(response)
                            
                            if final_content:
                                # 添加最终回答到memory
                                self.update_memory("assistant", final_content)
                                self.current_step = 0
                                self.state = AgentState.IDLE
                                self.update_status("✅ 完成", "已生成最终回答", "complete")
                                return final_content
                    except Exception as e:
                        print(f"Warning: Failed to generate final answer: {e}")
                    
                    # 如果生成失败，从memory中提取最后一条assistant消息作为兜底
                    for msg in reversed(self.memory.messages):
                        if msg.role == "assistant" and msg.content and len(msg.content) > 50:
                            self.current_step = 0
                            self.state = AgentState.IDLE
                            self.update_status("✅ 完成", "已提取最终回答", "complete")
                            return msg.content
                    
                    # 如果还是没有，返回一个提示信息
                    self.current_step = 0
                    self.state = AgentState.IDLE
                    self.update_status("⚠️ 完成（部分）", "已达到最大步数，但未能生成完整回答", "complete")
                    return f"抱歉，处理过程已达到最大步数限制（{self.max_steps}步）。基于已获取的信息，建议您咨询专业律师获取更详细的法律意见。"
                
                # 检查是否有工具执行结果，如果有，提取最终回答
                # 查找最后一条assistant消息（应该是基于工具结果的最终回答）
                final_answer = None
                if self.memory:
                    for msg in reversed(self.memory.messages):
                        if msg.role == "assistant" and msg.content:
                            # 检查这条消息是否在工具结果之后
                            msg_index = self.memory.messages.index(msg)
                            has_tool_before = any(
                                self.memory.messages[i].role == "tool" 
                                for i in range(msg_index)
                            )
                            if has_tool_before or not any(m.role == "tool" for m in self.memory.messages):
                                # 如果前面有工具结果，或者没有工具调用，这应该是最终回答
                                final_answer = msg.content
                                break
                
                # 如果有最终回答，返回它；否则返回步骤结果
                if final_answer:
                    # 确保执行完成后状态重置为IDLE（修复第二个query卡死问题）
                    if self.state != AgentState.IDLE:
                        print(f"[DEBUG] run方法结束前，重置Agent状态为IDLE")
                        self.state = AgentState.IDLE
                        self.current_step = 0
                    return final_answer
                else:
                    # 确保执行完成后状态重置为IDLE
                    if self.state != AgentState.IDLE:
                        print(f"[DEBUG] run方法结束前（无最终答案），重置Agent状态为IDLE")
                        self.state = AgentState.IDLE
                        self.current_step = 0
                    return "\n".join(results) if results else "No steps executed"
        finally:
            # 恢复原始memory和system_prompt（如果是临时创建的）
            if temp_memory is not None:
                self.memory = None
            if context and original_system_prompt:
                self.system_prompt = original_system_prompt

