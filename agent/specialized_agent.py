"""专业领域Agent，负责具体法律领域的任务执行"""
from typing import Optional, Dict, Any, Tuple
from .agent import Agent
# 处理相对导入问题
try:
    from ..schema import LegalDomain, LegalIntent, AgentState, Memory, StatusCallback, Message
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
    from schema import LegalDomain, LegalIntent, AgentState, Memory, StatusCallback, Message
    from config.config import Config
    from models.llm import LLM


class SpecializedAgent(Agent):
    """专业领域Agent，负责具体法律领域的任务执行"""
    
    def __init__(
        self,
        domain: LegalDomain,
        intent: Optional[LegalIntent] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        next_step_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        memory: Optional[Memory] = None,
        state: AgentState = AgentState.IDLE,
        max_steps: int = 10,
        status_callback: Optional[StatusCallback] = None
    ):
        """
        初始化SpecializedAgent
        
        Args:
            domain: 法律领域
            intent: 法律意图（用于定制化Agent）
            name: Agent名称（如果不提供，将使用领域名称）
            description: Agent描述
            system_prompt: 系统提示词
            next_step_prompt: 下一步提示词
            config: 系统配置
            memory: 记忆存储
            state: Agent状态
            max_steps: 最大执行步数
            status_callback: 状态回调函数
        """
        self.domain = domain
        self.intent = intent
        
        # 根据领域和意图生成默认系统提示词
        domain_descriptions = {
            LegalDomain.LABOR_LAW: "劳动法专家，擅长处理裁员、工资、劳动合同等劳动法相关问题",
            LegalDomain.FAMILY_LAW: "婚姻家事法专家，擅长处理离婚、抚养权、财产分割等婚姻家事相关问题",
            LegalDomain.CONTRACT_LAW: "合同法专家，擅长处理合同纠纷、合同审查等合同法相关问题",
            LegalDomain.CORPORATE_LAW: "公司法专家，擅长处理公司治理、股权纠纷等公司法相关问题",
            LegalDomain.CRIMINAL_LAW: "刑法专家，擅长处理刑事案件、量刑等刑法相关问题",
            LegalDomain.PROCEDURAL_QUERY: "程序法专家，擅长处理诉讼程序、法院管辖、诉讼费等程序性问题",
        }
        
        intent_descriptions = {
            LegalIntent.QA_RETRIEVAL: "法律法规、法条、类似案例查询",
            LegalIntent.CASE_ANALYSIS: "案情分析（用户描述了一个故事）",
            LegalIntent.DOC_DRAFTING: "起草文书（合同、起诉状、律师函）",
            LegalIntent.CALCULATION: "计算赔偿金、刑期、诉讼费",
            LegalIntent.REVIEW_CONTRACT: "审查合同风险",
            LegalIntent.CLARIFICATION: "信息不足，需要反问",
        }
        
        domain_desc = domain_descriptions.get(domain, "法律")
        intent_desc = intent_descriptions.get(intent, "处理") if intent else "处理"
        
        # 使用prompt模板
        try:
            from ..prompt.specialized_agent_prompts import SPECIALIZED_AGENT_SYSTEM_PROMPT_TEMPLATE
        except (ImportError, ValueError):
            # 如果相对导入失败，使用绝对导入
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.specialized_agent_prompts import SPECIALIZED_AGENT_SYSTEM_PROMPT_TEMPLATE
        
        # 传入domain以选择特定的SOP
        default_system_prompt = SPECIALIZED_AGENT_SYSTEM_PROMPT_TEMPLATE(domain_desc, intent_desc, domain)
        
        # 无状态：不传入memory，由Flow中心化管理
        super().__init__(
            name=name or f"{domain.value}_{intent.value if intent else 'default'}_agent",
            description=description or f"{domain_desc} - {intent_desc}",
            system_prompt=system_prompt or default_system_prompt,
            next_step_prompt=next_step_prompt,
            config=config,
            memory=None,  # 无状态：不持有memory
            state=state,
            max_steps=max_steps
        )
        
        # 在初始化后设置status_callback（BaseAgent有这个属性）
        self.status_callback = status_callback
        
        self.llm = LLM(config or Config())
        
        # 根据意图设置next_step_prompt，引导工具选择
        try:
            from ..prompt.specialized_agent_prompts import (
                QA_RETRIEVAL_NEXT_STEP_PROMPT,
                CALCULATION_NEXT_STEP_PROMPT,
                REVIEW_CONTRACT_NEXT_STEP_PROMPT,
                DEFAULT_NEXT_STEP_PROMPT
            )
        except (ImportError, ValueError):
            # 如果相对导入失败，使用绝对导入
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from prompt.specialized_agent_prompts import (
                QA_RETRIEVAL_NEXT_STEP_PROMPT,
                CALCULATION_NEXT_STEP_PROMPT,
                REVIEW_CONTRACT_NEXT_STEP_PROMPT,
                DEFAULT_NEXT_STEP_PROMPT
            )
        if intent == LegalIntent.QA_RETRIEVAL:
            self.next_step_prompt = QA_RETRIEVAL_NEXT_STEP_PROMPT
        elif intent == LegalIntent.CALCULATION:
            self.next_step_prompt = CALCULATION_NEXT_STEP_PROMPT
        elif intent == LegalIntent.REVIEW_CONTRACT:
            self.next_step_prompt = REVIEW_CONTRACT_NEXT_STEP_PROMPT
        else:
            self.next_step_prompt = DEFAULT_NEXT_STEP_PROMPT
    
    async def run(
        self,
        message: str,
        context: str = "",
        domain: Optional[LegalDomain] = None,
        intent: Optional[LegalIntent] = None,
        status_callback: Optional[StatusCallback] = None
    ) -> str:
        """
        运行Agent（无状态版本，接受context参数）
        
        Args:
            message: 用户消息
            context: 上下文信息（由Flow提供）
            domain: 法律领域（可选）
            intent: 法律意图（可选）
            status_callback: 状态回调函数
            
        Returns:
            执行结果
        """
        # 如果有domain和intent，使用execute_task（保持兼容性）
        if domain and intent:
            return await self.execute_task(message, domain, intent, status_callback)
        else:
            # 否则使用父类的run方法
            return await super().run(message, status_callback)
    
    async def execute_task(
        self,
        user_message: str,
        domain: LegalDomain,
        intent: LegalIntent,
        status_callback: Optional[StatusCallback] = None,
        context: str = ""
    ) -> str:
        """
        执行任务（精细化计划流程）
        
        流程：
        1. 根据意图类型制定精细化计划
        2. 使用Agent的react机制执行（think-act循环）
        3. 每一步都要think，根据结果决定下一步
        4. 直到完成任务返回结果
        
        Args:
            user_message: 用户消息
            domain: 法律领域
            intent: 法律意图
            status_callback: 状态回调函数
            
        Returns:
            执行结果
        """
        # 更新回调
        if status_callback:
            self.status_callback = status_callback

        # 确保Agent状态为IDLE（修复第二个query卡死问题）
        if self.state != AgentState.IDLE:
            print(f"[DEBUG] Agent状态不是IDLE: {self.state}，重置为IDLE")
            self.state = AgentState.IDLE
            self.current_step = 0
        
        # 1. 根据意图类型制定精细化计划
        self.update_status("📋 Phase 3.1: 制定计划", "正在制定精细化执行计划...", "running")
        plan = await self._create_plan(user_message, domain, intent)
        
        # 2. 如果有context，将其添加到系统提示中
        if context:
            enhanced_system_prompt = f"{self.system_prompt}\n\n上下文信息：\n{context}\n\n执行计划：{plan}"
        else:
            enhanced_system_prompt = f"{self.system_prompt}\n\n执行计划：{plan}"
        
        # 临时保存原始system_prompt
        original_system_prompt = self.system_prompt
        self.system_prompt = enhanced_system_prompt
        
        # 3. 使用Agent的react机制执行（通过父类的run方法）
        # 注意：由于无状态化，我们需要创建一个临时的memory用于执行
        # 但这里我们使用一个简化的方法：直接调用父类的run，它会在内部创建临时memory
        self.update_status("⚡ Phase 3.2: 执行任务", f"开始执行计划，将进行关键词提取、工具调用等步骤...", "running")
        # 更新status_callback（如果提供了）
        if status_callback:
            self.status_callback = status_callback
        
        # 调用父类的run方法（它会创建临时的memory用于执行）
        # 传递context参数以支持无状态执行
        result = await super().run(user_message, status_callback, context=context)
        
        # 恢复原始system_prompt
        self.system_prompt = original_system_prompt
        
        # 4. 确保有结果返回（即使max_steps到了也要返回）
        if not result or result.strip() == "":
            # 从临时memory中提取最后一条assistant消息（如果存在）
            if hasattr(self, 'memory') and self.memory:
                for msg in reversed(self.memory.messages):
                    if msg.role == "assistant" and msg.content and len(msg.content) > 50:
                        result = msg.content
                        break
            
            # 如果还是没有，生成一个兜底回答
            if not result or result.strip() == "":
                result = f"抱歉，在处理您的问题时遇到了一些困难。根据已识别的法律领域（{domain.value}）和意图（{intent.value}），建议您咨询专业律师获取更详细的法律意见。"
        
        # 5. 自我评估（Critic机制）- 严格检验结果质量
        self.update_status("🔍 Phase 3.3: 自我评估", "正在严格评估回答质量...", "running")
        max_critic_rounds = 2  # 最多进行2轮Critic评估和重新搜索
        critic_round = 0
        
        while critic_round < max_critic_rounds:
            # 使用严格的Critic Prompt评估结果
            is_acceptable, feedback = await self._self_evaluate_result(
                user_message, result, domain, intent
            )
            
            if is_acceptable:
                print(f"✅ 自我评估通过（第{critic_round + 1}轮）")
                break
            else:
                critic_round += 1
                print(f"⚠️ 自我评估不通过（第{critic_round}轮），反馈：{feedback}")
                
                if critic_round >= max_critic_rounds:
                    print(f"⚠️ 已达到最大Critic轮数（{max_critic_rounds}），返回当前结果")
                    break
                
                # 根据反馈重新构建搜索关键词并搜索
                self.update_status(
                    f"🔄 Phase 3.4: 重新搜索（第{critic_round}轮）",
                    f"根据评估反馈重新构建搜索关键词...",
                    "running"
                )
                
                # 生成新的搜索关键词（基于反馈）
                new_search_query = await self._generate_refined_search_query(
                    user_message, feedback, domain, intent
                )
                
                if new_search_query:
                    # 执行新的搜索
                    self.update_memory(
                        "system",
                        f"【Critic反馈 - 第{critic_round}轮】\n{feedback}\n\n需要重新搜索，新的搜索关键词：{new_search_query}"
                    )
                    
                    # 调用web_search工具（同步方法，不需要await）
                    from ..tools.web_search import WebSearchTool
                    web_search_tool = WebSearchTool(self.config)
                    
                    # 构建context（如果有临时memory则使用，否则使用传入的context）
                    search_context = {}
                    if hasattr(self, 'memory') and self.memory:
                        search_context = {"messages": [msg.to_dict() for msg in self.memory.get_recent_messages(10)]}
                    else:
                        search_context = {"context": context}
                    
                    search_result = web_search_tool.execute(
                        user_input=new_search_query,
                        context=search_context
                    )
                    
                    # 将搜索结果添加到临时memory（如果存在）
                    if hasattr(self, 'memory') and self.memory:
                        self.update_memory(
                            "system",
                            f"【重新搜索的结果】\n{search_result[:2000]}"
                        )
                    
                    # 基于新的搜索结果重新生成回答
                    self.update_status(
                        "📝 Phase 3.5: 重新生成回答",
                        "基于新的搜索结果重新生成回答...",
                        "running"
                    )
                    
                    # 强制LLM基于新搜索结果生成回答
                    messages_dict = []
                    if hasattr(self, 'memory') and self.memory:
                        recent_messages = self.memory.get_recent_messages(30)
                        for msg in recent_messages:
                            if isinstance(msg, Message):
                                messages_dict.append(msg.to_dict())
                            elif isinstance(msg, dict):
                                messages_dict.append(msg)
                    else:
                        # 如果没有memory，构建基本消息
                        messages_dict = [
                            {"role": "user", "content": user_message},
                            {"role": "system", "content": f"【重新搜索的结果】\n{search_result[:2000]}"}
                        ]
                    
                    # 添加系统提示，要求基于新搜索结果生成改进的回答
                    improved_prompt = f"""请基于最新的搜索结果和Critic反馈，重新生成一个改进的回答。

Critic反馈：{feedback}

要求：
1. 必须引用具体的法条编号（如《民法典》第XX条）
2. 使用肯定、明确的表述，避免"可能"、"大概"等不确定词汇
3. 使用分点分析结构（1. 2. 3. 或 首先、其次、最后）
4. 按照法律意见书格式输出（【案情摘要】、【法律分析】、【法律依据】、【结论与建议】）

请生成改进后的回答："""
                    
                    messages_dict.append({"role": "user", "content": improved_prompt})
                    
                    try:
                        response = self.llm.chat(
                            messages=messages_dict,
                            system_prompt=self.system_prompt,
                            temperature=0.7,
                            max_tokens=self.config.llm_max_tokens
                        )
                        
                        if isinstance(response, dict):
                            result = response.get("content", "")
                        else:
                            result = str(response)
                        
                        # 将改进的回答添加到临时memory（如果存在）
                        if result and hasattr(self, 'memory') and self.memory:
                            self.update_memory("assistant", result)
                    except Exception as e:
                        print(f"[ERROR] 重新生成回答失败: {e}")
                        break
        
        # 6. 执行完成后，确保状态重置为IDLE（修复第二个query卡死问题）
        if self.state != AgentState.IDLE:
            print(f"[DEBUG] 执行完成后，重置Agent状态为IDLE")
            self.state = AgentState.IDLE
            self.current_step = 0
        
        # 7. 所有任务完成后，清理资源（包括Critic评估）
        # 注意：只有在execute_task完全完成后才清理，确保Critic评估可以使用所有信息
        try:
            if hasattr(self, 'cleanup'):
                await self.cleanup()
        except Exception as e:
            print(f"[WARNING] 清理资源时出错: {e}")
        
        return result
    
    async def _create_plan(
        self,
        user_message: str,
        domain: LegalDomain,
        intent: LegalIntent
    ) -> str:
        """
        创建精细化执行计划
        
        Args:
            user_message: 用户消息
            domain: 法律领域
            intent: 法律意图
            
        Returns:
            执行计划文本
        """
        # 根据意图类型生成不同的计划
        if intent == LegalIntent.QA_RETRIEVAL:
            return await self._create_qa_retrieval_plan(user_message, domain)
        elif intent == LegalIntent.CASE_ANALYSIS:
            return await self._create_case_analysis_plan(user_message, domain)
        elif intent == LegalIntent.DOC_DRAFTING:
            return await self._create_doc_drafting_plan(user_message, domain)
        elif intent == LegalIntent.CALCULATION:
            return await self._create_calculation_plan(user_message, domain)
        elif intent == LegalIntent.REVIEW_CONTRACT:
            return await self._create_review_contract_plan(user_message, domain)
        elif intent == LegalIntent.CLARIFICATION:
            return await self._create_clarification_plan(user_message, domain)
        else:
            return "执行任务"
    
    async def _create_qa_retrieval_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建QA检索计划 - 升级版：先理解再检索"""
        return """QA检索计划：
1. 【案情分析与关键词提取】：详细分析用户描述，提取核心事实（Fact）、法律诉求（Claim）以及关键实体（人名、金额、时间）。
2. 【关键词生成】：生成3-5个准确的法律专业术语或法条名称（Query Transformation）。
3. 【法条检索】：使用web_search搜索生成的关键词（如"民法典 离婚 赔偿"），寻找精确的法律条文。
4. 【总结回答】：结合案情和检索到的法条，生成专业回答。
5. 【自我检查】：检查是否引用了具体法条，如果没有，重新检索。"""

    async def _create_case_analysis_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建案情分析计划"""
        return """案情分析计划：
1. 【事实梳理与实体提取】：分析用户描述，梳理时间线，提取关键实体（人名、金额、时间、地点）。
2. 【法律定性】：判断属于什么法律关系（SOP分析）。
3. 【缺口分析】：识别缺失的关键信息，如果严重缺失，生成澄清问题。
4. 【检索验证】：针对争议焦点，使用web_search搜索相关法条和类案。
5. 【综合分析】：结合法条和事实，输出法律分析报告。"""
    
    async def _create_doc_drafting_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建起草文书计划"""
        return """起草文书计划：
1. 识别文书类型
2. 提取所需字段
3. 检查必填字段是否完整
4. 如果缺失，生成澄清问题
5. 使用模板生成文书"""
    
    async def _create_calculation_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建计算计划"""
        return """计算计划：
1. 识别计算类型
2. 提取计算参数
3. 检查必需参数
4. 构建计算公式（Python代码）
5. 使用python_executor执行计算
6. 格式化结果"""
    
    async def _create_review_contract_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建审查合同计划"""
        return """审查合同计划：
1. 提取合同文本（使用ocr工具或直接读取）
2. 解析合同结构
3. 识别风险点
4. 生成审查报告"""
    
    async def _create_clarification_plan(self, user_message: str, domain: LegalDomain) -> str:
        """创建澄清计划"""
        return """澄清计划：
1. 识别缺失信息
2. 生成友好的澄清问题"""
    
    async def _self_evaluate_result(
        self,
        user_message: str,
        result: str,
        domain: LegalDomain,
        intent: LegalIntent
    ) -> Tuple[bool, str]:
        """
        自我评估结果质量（Critic机制）
        
        Args:
            user_message: 用户消息
            result: 当前结果
            domain: 法律领域
            intent: 法律意图
            
        Returns:
            (is_acceptable, feedback) 元组
        """
        try:
            from ..prompt.core_agent_prompts import RESULT_EVALUATION_PROMPT
        except (ImportError, ValueError):
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
当前回答：
{result[:2000]}

请严格按照硬性标准评估这个结果。如果不通过，必须明确指出违反了哪条标准，并提供具体的修改指令。"""
        
        try:
            # 使用LLM进行评估（使用低温度以确保严格性）
            response = self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.0,  # 使用0温度，确保严格评估
                max_tokens=500
            )
            
            # 解析JSON响应
            import re
            import json
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
            
            return is_acceptable, feedback
            
        except Exception as e:
            print(f"[WARNING] 自我评估失败: {e}，默认认为结果可接受")
            return True, "评估失败，默认通过"
    
    async def _generate_refined_search_query(
        self,
        user_message: str,
        critic_feedback: str,
        domain: LegalDomain,
        intent: LegalIntent
    ) -> str:
        """
        根据Critic反馈生成改进的搜索关键词
        
        Args:
            user_message: 用户消息
            critic_feedback: Critic反馈
            domain: 法律领域
            intent: 法律意图
            
        Returns:
            改进的搜索关键词
        """
        prompt = f"""你是一个专业的法律搜索关键词生成助手。

用户问题：{user_message}
法律领域：{domain.value}
法律意图：{intent.value}

Critic反馈（需要改进的地方）：
{critic_feedback}

请根据Critic反馈，生成一个改进的搜索关键词。要求：
1. 如果反馈提到"缺少具体法条引用"，请生成包含具体法条名称的搜索词（如"民法典 第XX条"）
2. 如果反馈提到"不确定表述"，请生成更精确的法律术语
3. 搜索词格式：核心法律概念 + 用户具体场景关键词 + 规定/法条

示例：
- 如果反馈是"缺少具体法条引用"，可以生成："离婚登记 材料 户口本 民法典 第XX条 规定"
- 如果反馈是"不确定表述"，可以生成更精确的术语："离婚登记 必需材料 户口本 民法典 规定"

请只返回搜索关键词，不要返回其他内容："""
        
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            if isinstance(response, dict):
                query = response.get("content", "").strip()
            else:
                query = str(response).strip()
            
            # 清理可能的引号或多余格式
            query = query.strip('"').strip("'").strip()
            
            return query if query else None
            
        except Exception as e:
            print(f"[ERROR] 生成改进搜索关键词失败: {e}")
            return None
