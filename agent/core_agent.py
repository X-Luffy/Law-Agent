"""核心Agent，负责领域分类和路由"""
from typing import Optional, Dict, Any, List, Tuple
from .agent import Agent
# 处理相对导入问题
try:
    from ..schema import LegalDomain, LegalIntent, AgentState, Memory, StatusCallback
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
    from schema import LegalDomain, LegalIntent, AgentState, Memory, StatusCallback
    from config.config import Config
    from models.llm import LLM
import json
import re


class CoreAgent(Agent):
    """核心Agent，负责分析业务领域并将问题路由到对应的子Agent"""
    
    def __init__(
        self,
        name: str = "core_agent",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,  # 保留参数以兼容，但不再使用
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10
    ):
        """
        初始化CoreAgent（无状态版本）
        
        Args:
            name: Agent名称
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词
            config: 系统配置
            memory: 记忆存储（已废弃，不再使用，由Flow中心化管理）
            state: Agent状态
            max_steps: 最大执行步数
        """
        # 使用默认系统提示词
        try:
            from ..prompt.core_agent_prompts import CORE_AGENT_SYSTEM_PROMPT
        except (ImportError, ValueError):
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.core_agent_prompts import CORE_AGENT_SYSTEM_PROMPT
        default_system_prompt = CORE_AGENT_SYSTEM_PROMPT
        
        # 不传入memory，使其无状态
        super().__init__(
            name=name,
            description=description or "Core agent for legal domain classification and routing",
            system_prompt=system_prompt or default_system_prompt,
            next_step_prompt=next_step_prompt,
            config=config,
            memory=None,  # 无状态：不持有memory
            state=state,
            max_steps=max_steps
        )
        
        # 领域分类器（使用LLM）
        # 为CoreAgent创建单独的配置，使用qwen-flash以提高路由速度
        core_config = config or Config()
        if core_config.llm_model == "qwen-max":
            # 如果使用默认配置，改为qwen-flash以提高速度
            core_config = Config()
            core_config.llm_model = "qwen-flash"
            # 复制其他配置
            if config:
                core_config.llm_api_key = config.llm_api_key
                core_config.llm_base_url = config.llm_base_url
        self.domain_classifier = LLM(core_config)
        
        # 子Agent字典（按domain+intent分类）- 保留以兼容旧方法
        self.sub_agents: Dict[str, Agent] = {}
    
    async def identify_domain_and_intent(
        self, 
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> tuple[LegalDomain, LegalIntent]:
        """
        识别业务领域和意图（使用LLM和定制prompt）
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史（可选）
            
        Returns:
            (法律领域, 法律意图) 元组
        """
        # 构建识别prompt
        try:
            from ..prompt.core_agent_prompts import DOMAIN_INTENT_ENTITIES_PROMPT
        except (ImportError, ValueError):
            # 如果相对导入失败，使用绝对导入
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.core_agent_prompts import DOMAIN_INTENT_ENTITIES_PROMPT
        system_prompt = DOMAIN_INTENT_ENTITIES_PROMPT

        # 构建对话历史上下文
        history_context = ""
        if conversation_history:
            history_context = "\n对话历史：\n"
            for msg in conversation_history[-5:]:  # 只使用最近5条
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_context += f"{role}: {content}\n"
        
        # 移除"已知事实"上下文，因为实体提取已移至Sub-Agent

        user_prompt = f"""{history_context}
当前用户问题：{user_message}

请识别法律领域和意图，返回JSON格式结果。忽略实体提取要求。"""

        try:
            # 使用LLM进行识别
            response = self.domain_classifier.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.1,  # 使用低温度以获得更稳定的结果
                max_tokens=500
            )
            
            # 解析JSON响应
            response = response.strip()
            
            # 移除可能的代码块标记
            if "```" in response:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)
            else:
                # 尝试直接提取JSON对象
                json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)
            
            # 解析JSON
            result = json.loads(response)
            
            # 获取领域和意图
            domain_str = result.get("domain", "Non_Legal")
            intent_str = result.get("intent", "QA_Retrieval")
            # entities 忽略
            
            # 调试日志
            print(f"[DEBUG] LLM识别结果 - domain: {domain_str}, intent: {intent_str}")
            
            # 转换为枚举
            try:
                # 处理各种可能的domain_str格式
                domain_str_upper = domain_str.upper().replace(" ", "_").replace("-", "_")
                if domain_str_upper == "NON_LEGAL" or domain_str_upper == "NONLEGAL":
                    domain = LegalDomain.NON_LEGAL
                else:
                    domain = LegalDomain[domain_str_upper]
            except KeyError:
                # 如果无法识别，尝试模糊匹配
                print(f"[DEBUG] 无法直接匹配domain: {domain_str}, 尝试模糊匹配")
                domain = self._fuzzy_match_domain(domain_str)
                if domain == LegalDomain.NON_LEGAL:
                    # 如果模糊匹配也失败，尝试基于用户消息的关键词检测
                    domain = self._keyword_based_domain_detection(user_message)
                    print(f"[DEBUG] 关键词检测结果: {domain}")
            
            # 如果LLM返回Non_Legal，但用户消息包含法律关键词，进行二次检查
            if domain == LegalDomain.NON_LEGAL:
                keyword_domain = self._keyword_based_domain_detection(user_message)
                if keyword_domain != LegalDomain.NON_LEGAL:
                    print(f"[DEBUG] LLM返回Non_Legal，但关键词检测发现法律问题: {keyword_domain}，使用关键词检测结果")
                    domain = keyword_domain
            
            # 最终验证：如果domain仍然是NON_LEGAL，但用户消息明显是法律问题，强制修正
            if domain == LegalDomain.NON_LEGAL:
                # 检查是否包含明显的法律关键词
                if any(keyword in user_message for keyword in ["法", "法律", "婚姻", "离婚", "合同", "劳动", "公司", "刑事", "犯罪", "法院", "诉讼"]):
                    print(f"[DEBUG] 检测到法律关键词，但domain仍为NON_LEGAL，强制使用关键词检测")
                    domain = self._keyword_based_domain_detection(user_message)
                    if domain == LegalDomain.NON_LEGAL:
                        # 如果还是NON_LEGAL，默认使用FAMILY_LAW（最常见）
                        domain = LegalDomain.FAMILY_LAW
                        print(f"[DEBUG] 强制设置为FAMILY_LAW作为默认值")
            
            try:
                intent = LegalIntent[intent_str.upper()]
            except KeyError:
                # 如果无法识别，默认使用QA_Retrieval
                intent = LegalIntent.QA_RETRIEVAL
            
            print(f"[DEBUG] 最终识别结果 - domain: {domain}, intent: {intent}")
            return domain, intent
            
        except Exception as e:
            print(f"Warning: Failed to identify domain and intent: {e}")
            print(f"User message: {user_message}")
            # 如果识别失败，尝试基于关键词的模糊匹配，而不是直接返回NON_LEGAL
            domain = self._fuzzy_match_domain(user_message)
            # 如果模糊匹配也失败，再尝试基于常见法律关键词判断
            if domain == LegalDomain.NON_LEGAL:
                domain = self._keyword_based_domain_detection(user_message)
            return domain, LegalIntent.QA_RETRIEVAL

    # 旧方法保留兼容性，但指向新逻辑
    async def identify_domain_intent_and_entities(
        self, 
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> tuple[LegalDomain, LegalIntent, Dict[str, Any]]:
        domain, intent = await self.identify_domain_and_intent(user_message, conversation_history)
        return domain, intent, {}
    
    async def route(
        self,
        user_message: str,
        context: str,
        status_callback: Optional[StatusCallback] = None
    ) -> Tuple[LegalDomain, LegalIntent, Dict[str, Any]]:
        """
        路由方法（无状态）：识别领域、意图和实体
        
        Args:
            user_message: 用户消息
            context: 上下文信息（由Flow提供）
            status_callback: 状态回调函数
            
        Returns:
            (domain, intent, entities) 元组
        """
        if status_callback:
            self.status_callback = status_callback
        
        # 从context中提取对话历史（如果存在）
        conversation_history = []
        # 简单解析context中的对话历史（格式：role: content）
        if "=== 对话历史 ===" in context:
            history_section = context.split("=== 对话历史 ===")[1].split("===")[0]
            for line in history_section.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        role = parts[0].strip()
                        content = parts[1].strip()
                        if role in ["user", "assistant"]:
                            conversation_history.append({"role": role, "content": content})
        
        # 识别领域和意图
        domain, intent = await self.identify_domain_and_intent(user_message, conversation_history)
        
        # 提取实体（简化版，可以后续增强）
        entities = {}
        
        # 尝试从context中提取全局状态中的实体
        if "=== 当前案件已知事实 ===" in context:
            global_section = context.split("=== 当前案件已知事实 ===")[1]
            # 简单解析实体信息
            if "已知当事人：" in global_section:
                persons_line = [l for l in global_section.split("\n") if "已知当事人：" in l]
                if persons_line:
                    persons_str = persons_line[0].split("：")[1].strip()
                    entities["persons"] = [p.strip() for p in persons_str.split(",") if p.strip()]
            if "已知金额：" in global_section:
                amounts_line = [l for l in global_section.split("\n") if "已知金额：" in l]
                if amounts_line:
                    amounts_str = amounts_line[0].split("：")[1].strip()
                    entities["amounts"] = [a.strip() for a in amounts_str.split(",") if a.strip()]
            if "已知时间：" in global_section:
                dates_line = [l for l in global_section.split("\n") if "已知时间：" in l]
                if dates_line:
                    dates_str = dates_line[0].split("：")[1].strip()
                    entities["dates"] = [d.strip() for d in dates_str.split(",") if d.strip()]
            if "已知地点：" in global_section:
                locations_line = [l for l in global_section.split("\n") if "已知地点：" in l]
                if locations_line:
                    locations_str = locations_line[0].split("：")[1].strip()
                    entities["locations"] = [l.strip() for l in locations_str.split(",") if l.strip()]
        
        return domain, intent, entities
    
    def _fuzzy_match_domain(self, domain_str: str) -> LegalDomain:
        """模糊匹配法律领域"""
        domain_str = domain_str.lower()
        
        if "labor" in domain_str or "劳动" in domain_str or "工资" in domain_str or "裁员" in domain_str or "试用期" in domain_str or "加班" in domain_str:
            return LegalDomain.LABOR_LAW
        elif "family" in domain_str or "婚姻" in domain_str or "家事" in domain_str or "离婚" in domain_str or "抚养" in domain_str or "继承" in domain_str:
            return LegalDomain.FAMILY_LAW
        elif "contract" in domain_str or "合同" in domain_str or "违约" in domain_str:
            return LegalDomain.CONTRACT_LAW
        elif "corporate" in domain_str or "公司" in domain_str or "股权" in domain_str or "治理" in domain_str:
            return LegalDomain.CORPORATE_LAW
        elif "criminal" in domain_str or "刑事" in domain_str or "刑法" in domain_str or "犯罪" in domain_str or "量刑" in domain_str or "处罚" in domain_str or "抢劫" in domain_str or "盗窃" in domain_str or "诈骗" in domain_str or "嫌疑人" in domain_str:
            return LegalDomain.CRIMINAL_LAW
        elif "procedural" in domain_str or "程序" in domain_str or "法院" in domain_str or "起诉" in domain_str or "诉讼" in domain_str or "诉讼费" in domain_str:
            return LegalDomain.PROCEDURAL_QUERY
        else:
            return LegalDomain.NON_LEGAL
    
    def _keyword_based_domain_detection(self, user_message: str) -> LegalDomain:
        """基于关键词的领域检测（更宽松的匹配）"""
        message_lower = user_message.lower()
        
        # 法律相关关键词
        legal_keywords = {
            LegalDomain.CRIMINAL_LAW: ["抢", "偷", "盗", "骗", "杀", "伤害", "处罚", "判刑", "量刑", "罪", "嫌疑人", "被告人"],
            LegalDomain.FAMILY_LAW: ["婚姻", "离婚", "结婚", "抚养", "赡养", "继承", "财产分割", "夫妻"],
            LegalDomain.LABOR_LAW: ["工资", "加班", "裁员", "解雇", "劳动合同", "试用期", "五险一金", "工伤"],
            LegalDomain.CONTRACT_LAW: ["合同", "协议", "违约", "履行", "解除", "签订"],
            LegalDomain.CORPORATE_LAW: ["公司", "企业", "股东", "股权", "董事会", "法人"],
            LegalDomain.PROCEDURAL_QUERY: ["法院", "起诉", "诉讼", "仲裁", "上诉", "执行", "管辖"]
        }
        
        # 检查是否包含法律关键词
        for domain, keywords in legal_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return domain
        
        # 如果包含"法"字，很可能是法律问题，默认返回QA_Retrieval对应的领域
        if "法" in user_message:
            # 尝试更精确的匹配
            if "婚姻" in user_message or "离婚" in user_message:
                return LegalDomain.FAMILY_LAW
            elif "刑" in user_message or "犯罪" in user_message:
                return LegalDomain.CRIMINAL_LAW
            elif "劳动" in user_message:
                return LegalDomain.LABOR_LAW
            elif "合同" in user_message:
                return LegalDomain.CONTRACT_LAW
            elif "公司" in user_message:
                return LegalDomain.CORPORATE_LAW
            else:
                # 包含"法"但无法确定具体领域，默认返回FAMILY_LAW（因为最常见）
                return LegalDomain.FAMILY_LAW
        
        return LegalDomain.NON_LEGAL
    
    async def classify_domain(self, user_message: str) -> LegalDomain:
        """
        分类用户问题所属的法律领域（保留兼容性）
        
        Args:
            user_message: 用户消息
            
        Returns:
            法律领域枚举
        """
        domain, _ = await self.identify_domain_and_intent(user_message)
        return domain
    
    async def route_to_sub_agent(
        self,
        domain: LegalDomain,
        user_message: str
    ) -> str:
        """
        将问题路由到对应的子Agent
        
        Args:
            domain: 法律领域
            user_message: 用户消息
            
        Returns:
            子Agent的回复
        """
        # TODO: 获取或创建对应的子Agent，然后调用其process_message方法
        sub_agent = self.get_or_create_sub_agent(domain)
        return await sub_agent.process_message(user_message)
    
    async def handle_non_legal_query(self, user_message: str) -> str:
        """
        处理非法律问题：先简单回答，然后引导用户询问法律相关问题
        
        Args:
            user_message: 用户消息
            
        Returns:
            回答+引导回复
        """
        # 使用LLM简单回答非法律问题
        try:
            simple_answer = self.domain_classifier.chat(
                messages=[{"role": "user", "content": user_message}],
                system_prompt="你是一个友好的助手。请简洁地回答用户的问题。",
                temperature=0.7,
                max_tokens=200
            )
            
            # 添加引导信息
            guidance = "\n\n---\n\n💡 **提示**：我是专业的法律助手，可以为您提供法律咨询服务。我可以帮助您处理以下法律领域的问题：\n\n- 📋 **劳动法**：裁员、工资、劳动合同、试用期等\n- 👨‍👩‍👧 **婚姻家事**：离婚、抚养权、财产分割、继承等\n- 📝 **合同纠纷**：合同违约、合同审查、合同签订等\n- 🏢 **公司法**：公司治理、股权纠纷、公司设立等\n- ⚖️ **刑法**：刑事案件、量刑、处罚等\n- 📍 **程序性问题**：法院管辖、诉讼费、诉讼流程等\n\n如果您有法律相关的问题，请随时告诉我，我会尽力帮助您！"
            
            return simple_answer + guidance
        except Exception as e:
            # 如果LLM调用失败，返回默认引导信息
            print(f"Warning: Failed to generate simple answer for non-legal query: {e}")
            return f"我理解您的问题，但我主要专注于法律咨询服务。\n\n💡 **提示**：我是专业的法律助手，可以为您提供法律咨询服务。我可以帮助您处理以下法律领域的问题：\n\n- 📋 **劳动法**：裁员、工资、劳动合同、试用期等\n- 👨‍👩‍👧 **婚姻家事**：离婚、抚养权、财产分割、继承等\n- 📝 **合同纠纷**：合同违约、合同审查、合同签订等\n- 🏢 **公司法**：公司治理、股权纠纷、公司设立等\n- ⚖️ **刑法**：刑事案件、量刑、处罚等\n- 📍 **程序性问题**：法院管辖、诉讼费、诉讼流程等\n\n如果您有法律相关的问题，请随时告诉我，我会尽力帮助您！"
    
    async def process_message(self, user_message: str, status_callback: Optional[StatusCallback] = None) -> str:
        """
        处理用户消息（重写父类方法）
        
        新流程（简化版）：
        1. 识别领域和意图
        2. 路由到子Agent（子Agent负责关键词提取和执行）
        
        Args:
            user_message: 用户消息
            status_callback: 状态回调函数
            
        Returns:
            Agent回复
        """
        try:
            # 更新回调
            if status_callback:
                self.status_callback = status_callback
                
            # 1. 获取对话历史（无状态：如果没有memory则使用空列表）
            conversation_history = []
            if hasattr(self, 'memory') and self.memory:
                recent_messages = self.memory.get_recent_messages(10)
                for msg in recent_messages:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        conversation_history.append({
                            "role": msg.role,
                            "content": msg.content
                        })
            
            # 2. 识别业务领域和意图
            self.update_status("🔍 Phase 1: 意图识别", "正在分析用户问题，识别法律领域和意图...", "running")
            try:
                domain, intent = await self.identify_domain_and_intent(
                    user_message,
                    conversation_history
                )
            except Exception as e:
                print(f"[ERROR] 识别领域和意图失败: {e}")
                import traceback
                traceback.print_exc()
                # 默认使用Family_Law和QA_Retrieval
                domain = LegalDomain.FAMILY_LAW
                intent = LegalIntent.QA_RETRIEVAL
            
            # 3. 更新State Memory（用于前端显示）- 如果存在state_memory
            if hasattr(self, 'state_memory'):
                self.update_state_memory(domain=domain, intent=intent)
            
            # 4. 如果是非法律问题，先简单回答，然后引导用户
            print(f"[DEBUG] process_message - domain: {domain}, domain.value: {domain.value if hasattr(domain, 'value') else domain}")
            if domain == LegalDomain.NON_LEGAL:
                print(f"[DEBUG] 触发non_legal处理逻辑")
                self.update_status("💡 Phase 1.5: 非法律指引", "识别为非法律问题，生成引导信息...", "complete")
                try:
                    return await self.handle_non_legal_query(user_message)
                except Exception as e:
                    print(f"[ERROR] 处理非法律问题失败: {e}")
                    return "抱歉，在处理您的问题时遇到了技术问题。请稍后重试或咨询专业律师。"
            else:
                print(f"[DEBUG] 继续处理法律问题，domain: {domain}")
            
            # 6. 路由到对应的子Agent
            self.update_status("⚙️ Phase 2: 智能路由", f"已识别领域: {domain.value}，意图: {intent.value}，正在唤醒专业Agent...", "running")
            try:
                sub_agent = self.get_or_create_sub_agent(domain, intent)
            except Exception as e:
                print(f"[ERROR] 创建子Agent失败: {e}")
                import traceback
                traceback.print_exc()
                return f"抱歉，系统在处理您的问题时遇到了技术问题（无法创建专业Agent）。请稍后重试或咨询专业律师。"
            
            # 执行任务（关键词提取现在由子Agent处理）
            # 传递 status_callback 给子Agent
            self.update_status("⚡ Phase 3: 专业Agent执行", f"专业Agent ({domain.value}) 开始处理任务，将进行关键词提取、工具调用等步骤...", "running")
            try:
                result = await sub_agent.execute_task(user_message, domain, intent, status_callback)
            except Exception as e:
                print(f"[ERROR] 子Agent执行任务失败: {e}")
                import traceback
                traceback.print_exc()
                result = None
            
            # 确保有结果返回（即使max_steps到了也要返回）
            if not result or result.strip() == "":
                # 如果子Agent没有返回结果，从memory中提取最后一条assistant消息
                try:
                    for msg in reversed(sub_agent.memory.messages):
                        if msg.role == "assistant" and msg.content and len(msg.content) > 50:
                            result = msg.content
                            break
                except Exception as e:
                    print(f"[ERROR] 从memory提取结果失败: {e}")
                
                # 如果还是没有，生成一个兜底回答
                if not result or result.strip() == "":
                    result = f"抱歉，在处理您的问题时遇到了一些困难。根据已识别的法律领域（{domain.value}）和意图（{intent.value}），建议您咨询专业律师获取更详细的法律意见。"
            
            self.update_status("✅ Phase 4: 完成", "回答生成完毕", "complete")
            return result
            
        except Exception as e:
            print(f"[ERROR] process_message发生未捕获的异常: {e}")
            import traceback
            traceback.print_exc()
            self.update_status("❌ Phase 4: 错误", "处理过程中发生错误", "error")
            return f"抱歉，系统在处理您的问题时遇到了技术问题：{str(e)}。请稍后重试或咨询专业律师。"
    
    def get_or_create_sub_agent(self, domain: LegalDomain, intent: Optional[LegalIntent] = None) -> "Agent":
        """
        获取或创建对应的子Agent
        
        Args:
            domain: 法律领域
            intent: 法律意图（可选，用于定制化子Agent）
            
        Returns:
            子Agent实例
        """
        try:
            # 使用domain+intent作为key，以便为不同意图创建定制化的子Agent
            domain_str = domain.value if hasattr(domain, 'value') else str(domain)
            intent_str = intent.value if intent and hasattr(intent, 'value') else (str(intent) if intent else 'default')
            key = f"{domain_str}_{intent_str}"
            
            print(f"[DEBUG] get_or_create_sub_agent: key={key}, domain={domain}, intent={intent}")
            
            if key not in self.sub_agents:
                print(f"[DEBUG] 创建新的子Agent: {key}")
                from .specialized_agent import SpecializedAgent
                try:
                    # 无状态：不传入memory
                    self.sub_agents[key] = SpecializedAgent(
                        domain=domain,
                        intent=intent,
                        config=self.config,
                        memory=None  # 无状态：不持有memory
                    )
                    print(f"[DEBUG] 子Agent创建成功: {key}")
                except Exception as e:
                    print(f"[ERROR] 创建子Agent时发生异常: {e}")
                    print(f"[ERROR] domain类型: {type(domain)}, domain值: {domain}")
                    print(f"[ERROR] intent类型: {type(intent)}, intent值: {intent}")
                    import traceback
                    traceback.print_exc()
                    raise
            else:
                print(f"[DEBUG] 使用已存在的子Agent: {key}")
            
            return self.sub_agents[key]
        except Exception as e:
            print(f"[ERROR] get_or_create_sub_agent发生异常: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def update_state_memory(
        self,
        domain: Optional[LegalDomain] = None,
        intent: Optional[LegalIntent] = None,
        entities: Optional[Dict[str, Any]] = None
    ):
        """
        更新State Memory（当前案件已知事实）
        
        Args:
            domain: 法律领域（可选）
            intent: 法律意图（可选）
            entities: 关键实体字典（可选）
        """
        # 无状态：如果state_memory不存在，跳过更新
        if not hasattr(self, 'state_memory'):
            return
        domain_str = domain.value if domain else None
        intent_str = intent.value if intent else None
        self.state_memory.update(domain=domain_str, intent=intent_str, entities=entities)
    
    def check_missing_required_info(
        self,
        domain: LegalDomain,
        intent: LegalIntent
    ) -> Optional[str]:
        """
        检查是否缺少必要信息，如果缺少则返回追问问题
        
        Args:
            domain: 法律领域
            intent: 法律意图
            
        Returns:
            如果缺少必要信息，返回追问问题；否则返回None
        """
        # 根据领域和意图定义必需信息
        required_info = {
            (LegalDomain.FAMILY_LAW, LegalIntent.CASE_ANALYSIS): {
                "persons": "至少需要知道涉及的人员姓名",
                "dates": "需要知道关键时间点（如结婚时间、分居时间等）"
            },
            (LegalDomain.LABOR_LAW, LegalIntent.CALCULATION): {
                "amounts": "需要知道工资、工龄等金额信息",
                "dates": "需要知道工作时间、离职时间等"
            },
            # 可以继续添加其他组合的必需信息
        }
        
        requirements = required_info.get((domain, intent), {})
        if not requirements:
            return None  # 没有特定要求
        
        missing = []
        # 无状态：如果state_memory不存在，返回None
        if not hasattr(self, 'state_memory'):
            return None
        entities = self.state_memory.get_entities()
        
        for key, description in requirements.items():
            if key not in entities or not entities[key]:
                missing.append(description)
        
        if missing:
            # 生成友好的追问问题
            question = f"为了更好地帮助您，我需要了解以下信息：\n"
            for i, desc in enumerate(missing, 1):
                question += f"{i}. {desc}\n"
            question += "\n请您提供这些信息，谢谢！"
            return question
        
        return None
    
    async def evaluate_and_provide_feedback(
        self,
        user_message: str,
        result: str,
        domain: LegalDomain,
        intent: LegalIntent,
        sub_agent: "Agent"
    ) -> str:
        """
        评估结果并提供反馈给子Agent（避免死循环）
        
        如果结果不满足要求，直接给子Agent提供具体的修改意见，而不是回到CoreAgent重新路由。
        
        Args:
            user_message: 原始用户消息
            result: 子Agent返回的结果
            domain: 法律领域
            intent: 法律意图
            sub_agent: 子Agent实例
            
        Returns:
            最终结果（如果评估通过）或重新执行后的结果
        """
        # 使用LLM评估结果质量（使用严格的Critic Prompt）
        try:
            from ..prompt.core_agent_prompts import RESULT_EVALUATION_PROMPT
        except (ImportError, ValueError):
            # 如果相对导入失败，使用绝对导入
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.core_agent_prompts import RESULT_EVALUATION_PROMPT
        
        system_prompt = RESULT_EVALUATION_PROMPT

        user_prompt = f"""用户问题：{user_message}
法律领域：{domain.value}
法律意图：{intent.value}
子Agent返回的结果：
{result[:2000]}

请严格按照硬性标准评估这个结果。如果不通过，必须明确指出违反了哪条标准，并提供具体的修改指令。"""

        try:
            # 使用LLM进行评估（使用低温度以确保严格性）
            response = self.domain_classifier.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.0,  # 使用0温度，确保严格评估
                max_tokens=500  # 增加token数以支持详细的反馈
            )
            
            # 解析JSON响应
            response = response.strip()
            
            # 提取JSON
            if "```" in response:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)
            
            # 解析JSON
            eval_result = json.loads(response)
            is_acceptable = eval_result.get("is_acceptable", True)
            feedback = eval_result.get("feedback", "可以返回")
            
            if is_acceptable:
                print(f"✅ 结果评估：可以返回。")
                return result
            else:
                print(f"⚠️ 结果评估：不通过。反馈：{feedback}")
                # 将反馈直接给子Agent，让它重新执行
                # 在子Agent的memory中添加反馈信息
                sub_agent.update_memory(
                    "system",
                    f"【Critic评估反馈 - 必须改进】\n{feedback}\n\n请严格按照反馈要求改进回答：\n1. 如果缺少法条引用，请重新搜索并引用具体法条编号\n2. 如果使用了不确定表述，请改为肯定表述\n3. 如果缺少分点分析，请使用结构化格式\n4. 确保回答符合法律意见书格式"
                )
                # 重新执行任务（只执行一次，避免无限循环）
                improved_result = await sub_agent.execute_task(
                    f"{user_message}\n\n【Critic评估反馈 - 必须改进】\n{feedback}",
                    domain,
                    intent
                )
                return improved_result
            
        except Exception as e:
            print(f"Warning: Failed to evaluate result: {e}, assuming result is acceptable")
            # 如果评估失败，默认认为结果可以接受
            return result

