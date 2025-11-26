"""Streamlit前端应用 - 增强版：实时状态 + 聚合详情页"""
import streamlit as st
import sys
import os
import asyncio
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
os.chdir(project_root)

try:
    from Agent.config.config import Config
    from Agent.flow.legal_flow import LegalFlow
    from Agent.agent.core_agent import CoreAgent
except ImportError:
    # 如果导入失败，尝试直接导入
    sys.path.insert(0, project_root)
    from config.config import Config
    from flow.legal_flow import LegalFlow
    from agent.core_agent import CoreAgent

# 页面配置
st.set_page_config(
    page_title="Legal Agent System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 样式优化
st.markdown("""
<style>
    .stStatus { border-radius: 10px; }
    .process-step { 
        padding: 12px; 
        border-left: 4px solid #e0e0e0; 
        margin-left: 10px; 
        margin-bottom: 12px;
        border-radius: 4px;
    }
    .process-step.think { 
        border-color: #4A90E2; 
        background-color: #f0f7ff; 
    }
    .process-step.tool_call { 
        border-color: #F5A623; 
        background-color: #fffaf0; 
    }
    .process-step.critic { 
        border-color: #7ED321; 
        background-color: #f6ffed; 
    }
    .process-step.stage { 
        border-color: #9B59B6; 
        background-color: #f9f3ff; 
    }
    .step-title { 
        font-weight: bold; 
        font-size: 0.95em; 
        margin-bottom: 6px; 
        color: #2c3e50;
    }
    .step-content { 
        font-size: 0.85em; 
        color: #555; 
        line-height: 1.5;
    }
    .step-meta {
        font-size: 0.75em;
        color: #999;
        margin-top: 4px;
    }
    .source-card {
        padding: 10px;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        margin-bottom: 8px;
        background-color: #fafbfc;
        transition: all 0.2s;
    }
    .source-card:hover {
        background-color: #f3f4f6;
        border-color: #4A90E2;
    }
    .metric-card {
        text-align: center;
        padding: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 初始化session state
if "legal_flow" not in st.session_state:
    st.session_state.legal_flow = None
if "core_agent" not in st.session_state:
    st.session_state.core_agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []


def init_legal_flow():
    """初始化LegalFlow（多Agent法律系统）"""
    try:
        config = Config()
        core_agent = CoreAgent(config=config)
        legal_flow = LegalFlow(core_agent=core_agent, config=config)
        return legal_flow, core_agent, None
    except Exception as e:
        return None, None, str(e)


def extract_urls_from_text(text: str) -> List[str]:
    """从文本中提取URL"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls


def log_execution_step(
    step_type: str,
    stage: str,
    status: str,
    message: str = "",
    elapsed_time: float = 0,
    details: Dict = None
):
    """记录执行步骤"""
    return {
        "step_type": step_type,
        "stage": stage,
        "status": status,
        "message": message,
        "elapsed_time": elapsed_time,
        "details": details or {},
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }


def extract_execution_details_from_agent(core_agent: CoreAgent) -> List[Dict[str, Any]]:
    """从Agent的memory中提取详细的执行信息（包括子Agent的执行步骤）"""
    log_entries = []
    
    try:
        # 首先尝试从子Agent的memory中提取（更详细）
        if hasattr(core_agent, 'sub_agents') and core_agent.sub_agents:
            print(f"[DEBUG] Found {len(core_agent.sub_agents)} sub_agents")
            # 获取最近使用的子Agent（通常是最后一个）
            sub_agent_list = list(core_agent.sub_agents.items())
            if sub_agent_list:
                # 使用最后一个子Agent（最近使用的）
                agent_key, sub_agent = sub_agent_list[-1]
                print(f"[DEBUG] 从子Agent提取日志: {agent_key}")
                
                if hasattr(sub_agent, 'memory') and sub_agent.memory and hasattr(sub_agent.memory, 'messages'):
                    messages = sub_agent.memory.messages
                    print(f"[DEBUG] 子Agent memory消息数: {len(messages)}")
                    current_step = 0
                    
                    for i, msg in enumerate(messages):
                        # 检查是否是assistant消息（包含think内容或tool_calls）
                        if hasattr(msg, 'role') and msg.role == 'assistant':
                            # 检查是否有tool_calls
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                # 这是一个think步骤，产生了tool_calls
                                current_step += 1
                                think_content = getattr(msg, 'content', '') or ''
                                
                                # 提取tool_calls详情
                                tool_calls_details = []
                                for tool_call in msg.tool_calls:
                                    if isinstance(tool_call, dict):
                                        func = tool_call.get('function', {})
                                        args_str = func.get('arguments', '{}')
                                        # 尝试解析arguments
                                        try:
                                            import json
                                            args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
                                        except:
                                            args_dict = args_str
                                        
                                        tool_calls_details.append({
                                            "name": func.get('name', ''),
                                            "arguments": args_dict
                                        })
                                
                                log_entries.append(log_execution_step(
                                    step_type="think",
                                    stage=f"Step {current_step}: Think (生成工具调用)",
                                    status="success",
                                    message=think_content[:200] + "..." if len(think_content) > 200 else think_content,
                                    elapsed_time=0,
                                    details={
                                        "tool_calls": tool_calls_details,
                                        "step_info": {
                                            "step": current_step,
                                            "max_steps": getattr(sub_agent, 'max_steps', 10)
                                        }
                                    }
                                ))
                            elif hasattr(msg, 'content') and msg.content:
                                # 这是一个think步骤，但没有tool_calls（可能是最终回答）
                                think_content = msg.content
                                # 检查是否是最终回答（在tool消息之后）
                                has_tool_before = any(
                                    hasattr(m, 'role') and m.role == 'tool' 
                                    for m in messages[:i]
                                )
                                if has_tool_before and len(think_content) > 50:
                                    current_step += 1
                                    log_entries.append(log_execution_step(
                                        step_type="think",
                                        stage=f"Step {current_step}: Think (生成最终回答)",
                                        status="success",
                                        message=think_content[:300] + "..." if len(think_content) > 300 else think_content,
                                        elapsed_time=0,
                                        details={
                                            "step_info": {
                                                "step": current_step,
                                                "max_steps": getattr(sub_agent, 'max_steps', 10)
                                            }
                                        }
                                    ))
                        
                        # 检查是否是tool消息（工具执行结果）
                        elif hasattr(msg, 'role') and msg.role == 'tool':
                            tool_name = getattr(msg, 'name', '') or ''
                            tool_content = getattr(msg, 'content', '') or ''
                            
                            if tool_name:
                                log_entries.append(log_execution_step(
                                    step_type="tool_call",
                                    stage=f"Step {current_step}: Act (执行工具: {tool_name})",
                                    status="success",
                                    message=f"工具 {tool_name} 执行完成",
                                    elapsed_time=0,
                                    details={
                                        "tool_result": {
                                            "tool": tool_name,
                                            "result": tool_content[:1000] + "..." if len(tool_content) > 1000 else tool_content
                                        }
                                    }
                                ))
                    
                    # 如果从子Agent提取到了信息，直接返回
                    if log_entries:
                        print(f"[DEBUG] 从子Agent提取到 {len(log_entries)} 条日志")
                        return log_entries
                else:
                    print(f"[DEBUG] 子Agent没有memory或messages属性")
        else:
            print("[DEBUG] No sub_agents found or empty")
        
        # 如果子Agent没有信息，从CoreAgent的memory中提取
        if hasattr(core_agent, 'memory') and core_agent.memory and hasattr(core_agent.memory, 'messages'):
            messages = core_agent.memory.messages
            print(f"[DEBUG] 从CoreAgent memory提取，消息数: {len(messages)}")
            current_step = 0
            
            for i, msg in enumerate(messages):
                if hasattr(msg, 'role') and msg.role == 'assistant':
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        current_step += 1
                        think_content = getattr(msg, 'content', '') or ''
                        
                        tool_calls_details = []
                        for tool_call in msg.tool_calls:
                            if isinstance(tool_call, dict):
                                func = tool_call.get('function', {})
                                args_str = func.get('arguments', '{}')
                                try:
                                    import json
                                    args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
                                except:
                                    args_dict = args_str
                                
                                tool_calls_details.append({
                                    "name": func.get('name', ''),
                                    "arguments": args_dict
                                })
                        
                        log_entries.append(log_execution_step(
                            step_type="think",
                            stage=f"Step {current_step}: Think (生成工具调用)",
                            status="success",
                            message=think_content[:200] + "..." if len(think_content) > 200 else think_content,
                            elapsed_time=0,
                            details={
                                "tool_calls": tool_calls_details,
                                "step_info": {
                                    "step": current_step,
                                    "max_steps": getattr(core_agent, 'max_steps', 10)
                                }
                            }
                        ))
                
                elif hasattr(msg, 'role') and msg.role == 'tool':
                    tool_name = getattr(msg, 'name', '') or ''
                    tool_content = getattr(msg, 'content', '') or ''
                    
                    if tool_name:
                        log_entries.append(log_execution_step(
                            step_type="tool_call",
                            stage=f"Step {current_step}: Act (执行工具: {tool_name})",
                            status="success",
                            message=f"工具 {tool_name} 执行完成",
                            elapsed_time=0,
                            details={
                                "tool_result": {
                                    "tool": tool_name,
                                    "result": tool_content[:1000] + "..." if len(tool_content) > 1000 else tool_content
                                }
                            }
                        ))
        else:
            print(f"[DEBUG] CoreAgent没有memory或messages属性")
    
    except Exception as e:
        print(f"[ERROR] extract_execution_details_from_agent failed: {e}")
        import traceback
        traceback.print_exc()
    
    if not log_entries:
        print("[DEBUG] No log entries extracted, returning empty list")
    else:
        print(f"[DEBUG] Extracted {len(log_entries)} log entries")
    
    return log_entries


def render_execution_timeline(log_entries: List[Dict[str, Any]], message_idx: int = 0):
    """在可展开区域中渲染漂亮的执行时间轴
    
    Args:
        log_entries: 日志条目列表
        message_idx: 消息索引（用于生成唯一的key，避免多个消息间的重复）
    """
    if not log_entries:
        st.info("📝 暂无执行细节")
        return

    # 1. 概览统计
    total_time = sum(entry.get("elapsed_time", 0) for entry in log_entries)
    tools_called = set()
    think_steps = 0
    
    for entry in log_entries:
        if entry.get("step_type") == "think":
            think_steps += 1
        if entry.get("details", {}).get("tool_result"):
            tools_called.add(entry["details"]["tool_result"]["tool"])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⏱️ 总耗时", f"{total_time:.2f}s" if total_time > 0 else "N/A")
    with col2:
        st.metric("💭 思考步骤", think_steps)
    with col3:
        st.metric("🛠️ 工具调用", len(tools_called))

    st.divider()

    # 2. 详细步骤渲染
    for i, entry in enumerate(log_entries, 1):
        step_type = entry.get("step_type", "stage")
        status = entry.get("status", "")
        message = entry.get("message", "")
        details = entry.get("details", {})
        timestamp = entry.get("timestamp", "")
        
        # 定义图标
        icon_map = {
            "stage": "📍", "think": "💭", "act": "⚡", 
            "tool_call": "🛠️", "critic": "🔍", "error": "❌"
        }
        icon = icon_map.get(step_type, "📝")
        
        # CSS class
        css_class = f"process-step {step_type}"
        
        # 渲染内容块
        st.markdown(f"""
        <div class="{css_class}">
            <div class="step-title">{icon} {entry.get('stage', 'Step')}</div>
            <div class="step-content">{message}</div>
            <div class="step-meta">🕐 {timestamp}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 详情展示（如果有）
        if details:
            # 工具调用详情
            if "tool_calls" in details and details["tool_calls"]:
                with st.expander("🔧 查看工具调用参数", expanded=False):
                    for tool_idx, tool in enumerate(details["tool_calls"]):
                        st.write(f"**Tool**: `{tool.get('name', 'unknown')}`")
                        if tool.get('arguments'):
                            st.json(tool['arguments'])
            
            # 工具结果详情
            if "tool_result" in details:
                with st.expander("📊 查看工具返回结果", expanded=False):
                    tool_result = details["tool_result"]
                    st.caption(f"🛠️ **Tool**: {tool_result.get('tool', 'unknown')}")
                    result_text = tool_result.get('result', '')
                    if len(result_text) > 500:
                        # 使用消息索引、步骤索引和时间戳生成唯一的key，确保跨消息的唯一性
                        timestamp_hash = hash(timestamp) % 10000 if timestamp else 0
                        unique_key = f"tool_result_msg{message_idx}_step{i}_{tool_result.get('tool', 'unknown')}_{timestamp_hash}"
                        st.text_area("Result", result_text, height=200, key=unique_key)
                    else:
                        st.code(result_text, language="text")
            
            # Critic 反馈
            if "critic_feedback" in details:
                feedback = details["critic_feedback"]
                if feedback.get("is_acceptable"):
                    st.success("✅ Critic评估：通过")
                else:
                    st.warning(f"⚠️ Critic评估：不通过")
                    st.caption(f"反馈: {feedback.get('feedback', '')}")
            
            # 实体识别结果
            if "entities" in details and details["entities"]:
                st.caption(f"🏷️ **识别实体**: {details['entities']}")


def render_sources(response_text: str):
    """提取并渲染来源链接"""
    # 提取 Markdown 格式的链接
    markdown_links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', response_text)
    
    # 提取普通 URL
    plain_urls = extract_urls_from_text(response_text)
    
    # 合并并去重
    sources = []
    seen_urls = set()
    
    # 优先使用 markdown 链接（有标题）
    for title, url in markdown_links:
        if url.startswith(('http://', 'https://')) and url not in seen_urls:
            seen_urls.add(url)
            sources.append({"title": title, "url": url})
    
    # 添加普通 URL
    for url in plain_urls:
        if url not in seen_urls:
            seen_urls.add(url)
            sources.append({"title": url[:50] + "..." if len(url) > 50 else url, "url": url})
    
    if sources:
        st.markdown("### 📚 参考资料")
        for src in sources:
            st.markdown(f"""
            <div class="source-card">
                <a href="{src['url']}" target="_blank" style="text-decoration:none; color:#0366d6;">
                    🔗 {src['title']}
                </a>
            </div>
            """, unsafe_allow_html=True)


def process_message(user_input: str):
    """处理用户消息：实时状态更新 + 最终聚合展示"""
    if not st.session_state.legal_flow or not st.session_state.core_agent:
        st.error("LegalFlow未初始化，请先初始化系统")
        return
    
    try:
        # 1. 记录用户消息
        user_msg = {
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages.append(user_msg)
        
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # 2. 生成回复
        # 创建状态显示容器
        status_container = st.empty()
        
        # 创建异步循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        response = None
        execution_logs = []
        error_occurred = False
        error_message = None
        
        # 创建状态更新回调函数（使用共享状态对象）
        status_info = {"label": "🚀 系统启动中...", "message": "", "state": "running"}
        
        def status_callback(stage: str, message: str, state: str = "running"):
            """状态更新回调函数"""
            status_info["label"] = stage
            status_info["message"] = message
            status_info["state"] = state
        
        # 使用 st.status 进行实时状态更新
        with status_container.status("🚀 系统启动中...", expanded=True) as status:
            try:
                # 执行核心逻辑（传递回调函数）
                # 由于Streamlit的限制，状态更新会在execute内部进行，但UI更新需要等待
                response = loop.run_until_complete(
                    st.session_state.legal_flow.execute(user_input, status_callback)
                )
                
                # 确保有响应
                if not response or response.strip() == "":
                    response = "抱歉，系统未能生成有效回答。请稍后重试或咨询专业律师。"
                    error_occurred = True
                    error_message = "系统未能生成有效回答"
                
                # 提取执行日志
                try:
                    execution_logs = extract_execution_details_from_agent(st.session_state.core_agent)
                except Exception as e:
                    print(f"[WARNING] 提取执行日志失败: {e}")
                    execution_logs = []
                
                # 完成 - 显示最终状态
                if not error_occurred:
                    final_label = status_info.get("label", "✅ 回答生成完毕")
                    status.update(label=final_label, state="complete", expanded=False)
                else:
                    status.update(label="⚠️ 部分完成", state="error", expanded=False)
                
            except TimeoutError as e:
                error_occurred = True
                error_message = f"⏱️ 超时错误: {str(e)}"
                response = "抱歉，处理超时。请稍后重试或咨询专业律师。"
                status.update(label="❌ 执行超时", state="error")
            except Exception as e:
                error_occurred = True
                error_message = f"❌ 处理错误: {str(e)}"
                response = f"抱歉，系统在处理您的问题时遇到了技术问题：{str(e)}。请稍后重试或咨询专业律师。"
                status.update(label="❌ 发生错误", state="error")
                import traceback
                print(f"[ERROR] 处理消息时发生异常:")
                traceback.print_exc()
            finally:
                loop.close()
        
        # 3. 保存助手消息到session_state（关键：在rerun之前保存）
        if response:
            assistant_msg = {
                "role": "assistant",
                "content": response,
                "logs": execution_logs,
                "error_occurred": error_occurred,
                "error_message": error_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.messages.append(assistant_msg)
            print(f"[DEBUG] 已保存助手消息到session_state，消息数: {len(st.session_state.messages)}")
    
    except Exception as e:
        st.error(f"处理消息时出错: {str(e)}")
        import traceback
        with st.expander("错误详情"):
            st.code(traceback.format_exc())


def display_conversation():
    """显示对话历史（包含执行流程）"""
    if st.session_state.messages:
        for idx, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                # 如果是assistant消息且有错误，先显示错误信息
                if msg["role"] == "assistant" and msg.get("error_occurred"):
                    st.error(msg.get("error_message", "处理过程中发生错误"))
                    if msg.get("content"):
                        st.warning("⚠️ 部分回复已生成，但可能不完整：")
                
                # 显示消息内容
                st.markdown(msg["content"])
                if msg.get("timestamp"):
                    st.caption(f"⏰ {msg['timestamp']}")
                
                # 如果是assistant消息，显示来源和执行流程
                if msg["role"] == "assistant":
                    # 显示来源链接
                    if msg.get("content"):
                        render_sources(msg["content"])
                    
                    # 显示完整执行流程（从保存的logs或重新提取）
                    logs_to_display = msg.get("logs", [])
                    
                    # 如果没有保存的logs，尝试重新提取（仅针对最新的消息）
                    if not logs_to_display and idx == len(st.session_state.messages) - 1:
                        if st.session_state.core_agent:
                            try:
                                logs_to_display = extract_execution_details_from_agent(st.session_state.core_agent)
                                # 保存提取的logs
                                msg["logs"] = logs_to_display
                            except Exception as e:
                                print(f"Warning: Failed to extract logs: {e}")
                    
                    if logs_to_display:
                        with st.expander("🕵️ 查看完整思维链与执行流程 (Full Process)", expanded=False):
                            # 显示识别信息
                            if st.session_state.core_agent and hasattr(st.session_state.core_agent, 'state_memory'):
                                try:
                                    mem = st.session_state.core_agent.state_memory.get()
                                    domain = mem.get('domain', '未知')
                                    intent = mem.get('intent', '未知')
                                    entities = mem.get('entities', {})
                                    
                                    st.info(f"📋 **任务识别**: 领域 `{domain}` | 意图 `{intent}`")
                                    
                                    # 显示关键实体
                                    if entities:
                                        entity_parts = []
                                        if entities.get("persons"):
                                            entity_parts.append(f"👤 当事人: {', '.join(entities['persons'])}")
                                        if entities.get("amounts"):
                                            entity_parts.append(f"💰 金额: {', '.join(entities['amounts'])}")
                                        if entities.get("dates"):
                                            entity_parts.append(f"📅 时间: {', '.join(entities['dates'])}")
                                        if entities.get("locations"):
                                            entity_parts.append(f"📍 地点: {', '.join(entities['locations'])}")
                                        if entity_parts:
                                            st.caption(" | ".join(entity_parts))
                                    
                                    st.divider()
                                except Exception as e:
                                    print(f"Warning: Failed to display state memory: {e}")
                            
                            # 渲染时间轴（传递消息索引以确保key唯一）
                            render_execution_timeline(logs_to_display, message_idx=idx)
                    else:
                        # 如果没有logs，显示一个提示
                        with st.expander("🕵️ 查看完整思维链与执行流程 (Full Process)", expanded=False):
                            st.info("📝 暂无执行细节（可能是旧消息或执行过程中出现异常）")


def main():
    """主函数"""
    st.title("⚖️ Legal Agent System")
    st.markdown("多Agent法律助手系统 - 实时状态追踪 + 完整流程展示")
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 控制台")
        
        # 初始化按钮
        if st.button("🚀 初始化系统", use_container_width=True):
            with st.spinner("正在加载模型..."):
                legal_flow, core_agent, error = init_legal_flow()
                if legal_flow and core_agent:
                    st.session_state.legal_flow = legal_flow
                    st.session_state.core_agent = core_agent
                    st.success("✅ 系统就绪！")
                else:
                    st.error(f"❌ 初始化失败: {error}")
        
        # 系统状态
        if st.session_state.legal_flow and st.session_state.core_agent:
            st.success("✅ 系统已初始化")
            
            # 显示配置信息
            with st.expander("📋 系统配置", expanded=False):
                st.write("**LLM模型**: qwen-max")
                st.write("**Embedding**: text-embedding-v4")
                st.write("**工具选择**: Native Function Calling")
                st.write("**最大步数**: 10步")
            
            st.divider()
            
            # 清空对话按钮
            if st.button("🗑️ 清空对话历史", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_history = []
                if st.session_state.core_agent:
                    st.session_state.core_agent.memory.clear()
                    if hasattr(st.session_state.core_agent, 'state_memory'):
                        st.session_state.core_agent.state_memory.clear()
                st.rerun()
            
            # 重置系统按钮
            if st.button("🔄 重置系统", use_container_width=True):
                st.session_state.legal_flow = None
                st.session_state.core_agent = None
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.rerun()
        else:
            st.warning("⚠️ 系统未初始化")
            st.info("请点击上方按钮初始化系统")
        
        st.divider()
        
        # 环境检查
        st.subheader("🔍 环境检查")
        dashscope_key = os.getenv("DASHSCOPE_API_KEY", "未设置")
        if dashscope_key != "未设置":
            st.success(f"✅ API Key: {dashscope_key[:20]}...")
        else:
            st.error("❌ DASHSCOPE_API_KEY 未设置")
    
    # 主界面
    if not st.session_state.legal_flow or not st.session_state.core_agent:
        st.info("👈 请在侧边栏初始化系统后开始对话")
        st.markdown("""
        ### 💡 使用说明
        
        1. 点击侧边栏的 "🚀 初始化系统" 按钮
        2. 等待系统加载完成
        3. 在下方输入框中输入法律相关问题
        4. **查看实时状态**：系统会显示当前执行的阶段（意图识别、工具调用等）
        5. **查看完整流程**：点击回答下方的"查看完整思维链"查看详细执行过程
        
        ### ✨ 功能特性
        
        - 🎯 **多Agent架构**: CoreAgent路由 + SpecializedAgent执行 + Critic评估
        - 📊 **实时状态显示**: 显示当前执行阶段和进度
        - 🔍 **智能识别**: 自动识别法律领域、意图和关键实体
        - 💭 **完整流程追踪**: 展示每个think-act循环的详细步骤
        - 🛠️ **复合搜索词**: 生成"法律术语+具体场景"的精准搜索词
        - 📚 **来源链接**: 自动提取并展示参考资料链接
        - 🕵️ **聚合详情页**: 在回答下方展示完整的决策过程
        
        ### 📖 支持的法律领域
        
        - 劳动法 (Labor_Law)
        - 婚姻家事 (Family_Law)
        - 合同纠纷 (Contract_Law)
        - 公司法 (Corporate_Law)
        - 刑法 (Criminal_Law)
        - 程序性问题 (Procedural_Query)
        """)
    else:
        # 显示对话历史
        display_conversation()
        
        # 输入框
        user_input = st.chat_input("请输入您的法律问题...")
        
        if user_input:
            process_message(user_input)
            st.rerun()


if __name__ == "__main__":
    main()
