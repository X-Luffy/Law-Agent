"""通用聊天Agent，用于处理非法律问题"""
from typing import Optional
from .agent import Agent
# 处理相对导入问题
try:
    from ..schema import AgentState, StatusCallback
    from ..config.config import Config
    from ..models.llm import LLM
except (ImportError, ValueError):
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from schema import AgentState, StatusCallback
    from config.config import Config
    from models.llm import LLM


class GeneralChatAgent(Agent):
    """通用聊天Agent，用于处理非法律问题"""
    
    def __init__(
        self,
        name: str = "general_chat_agent",
        description: Optional[str] = None,
        config: Optional[Config] = None,
        status_callback: Optional[StatusCallback] = None
    ):
        """
        初始化GeneralChatAgent
        
        Args:
            name: Agent名称
            description: Agent描述
            config: 系统配置
            status_callback: 状态回调函数
        """
        system_prompt = """你是一个友好的助手。请简洁地回答用户的问题。
如果用户询问的是法律相关问题，请引导他们使用法律助手功能。"""
        
        super().__init__(
            name=name,
            description=description or "General chat agent for non-legal queries",
            system_prompt=system_prompt,
            config=config,
            state=AgentState.IDLE,
            max_steps=1  # 非法律问题通常只需要一次回答
        )
        
        self.status_callback = status_callback
        self.llm = LLM(config or Config())
    
    async def run(self, message: str, context: str = "", status_callback: Optional[StatusCallback] = None) -> str:
        """
        处理非法律问题（无状态执行）
        
        Args:
            message: 用户消息
            context: 上下文信息（可选）
            status_callback: 状态回调函数（可选）
            
        Returns:
            Agent回复
        """
        if status_callback:
            self.status_callback = status_callback
        
        # 更新状态
        self.update_status("💬 处理非法律问题", "正在生成回答...", "running")
        
        try:
            # 构建消息列表
            messages = [{"role": "user", "content": message}]
            
            # 如果有上下文，添加到系统提示中
            system_prompt = self.system_prompt
            if context:
                system_prompt = f"{system_prompt}\n\n上下文信息：\n{context}"
            
            # 使用LLM生成回答
            response = self.llm.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            # 添加引导信息
            guidance = "\n\n---\n\n💡 **提示**：我是专业的法律助手，可以为您提供法律咨询服务。我可以帮助您处理以下法律领域的问题：\n\n- 📋 **劳动法**：裁员、工资、劳动合同、试用期等\n- 👨‍👩‍👧 **婚姻家事**：离婚、抚养权、财产分割、继承等\n- 📝 **合同纠纷**：合同违约、合同审查、合同签订等\n- 🏢 **公司法**：公司治理、股权纠纷、公司设立等\n- ⚖️ **刑法**：刑事案件、量刑、处罚等\n- 📍 **程序性问题**：法院管辖、诉讼费、诉讼流程等\n\n如果您有法律相关的问题，请随时告诉我，我会尽力帮助您！"
            
            result = str(response) + guidance
            
            self.update_status("✅ 完成", "回答生成完毕", "complete")
            return result
            
        except Exception as e:
            print(f"Warning: Failed to generate answer for non-legal query: {e}")
            self.update_status("❌ 错误", "处理过程中发生错误", "error")
            return f"我理解您的问题，但我主要专注于法律咨询服务。\n\n💡 **提示**：我是专业的法律助手，可以为您提供法律咨询服务。如果您有法律相关的问题，请随时告诉我，我会尽力帮助您！"

