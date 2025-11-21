"""Streamlit前端应用"""
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
    from Agent.agent.agent import Agent
except ImportError:
    # 如果导入失败，尝试直接导入
    sys.path.insert(0, project_root)
    from config.config import Config
    from agent.agent import Agent

# 页面配置
st.set_page_config(
    page_title="Agent System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化session state
if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "system_info" not in st.session_state:
    st.session_state.system_info = {}
if "sources" not in st.session_state:
    st.session_state.sources = {}  # 存储每条消息的来源链接
if "execution_log" not in st.session_state:
    st.session_state.execution_log = []  # 存储执行日志


def init_agent():
    """初始化Agent"""
    try:
        config = Config()
        agent = Agent(
            name="legal_assistant",
            description="法律对话助手",
            system_prompt="你是一个专业的法律助手，请根据用户的问题提供准确、专业的回答。",
            config=config
        )
        return agent, None
    except Exception as e:
        return None, str(e)


def format_message(message: Dict[str, Any]) -> str:
    """格式化消息显示"""
    role = message.get("role", "")
    content = message.get("content", "")
    timestamp = message.get("timestamp", "")
    
    if role == "user":
        return f"**用户** ({timestamp}):\n{content}"
    elif role == "assistant":
        return f"**Agent** ({timestamp}):\n{content}"
    elif role == "system":
        return f"**系统** ({timestamp}):\n{content}"
    else:
        return f"**{role}** ({timestamp}):\n{content}"


def extract_urls_from_text(text: str) -> List[str]:
    """从文本中提取URL"""
    # URL正则表达式
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls


def extract_sources_from_response(response: str, context: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """从回复和上下文中提取来源信息"""
    sources = []
    
    # 从文本中提取URL
    urls = extract_urls_from_text(response)
    for url in urls:
        sources.append({
            "type": "url",
            "url": url,
            "title": url[:50] + "..." if len(url) > 50 else url
        })
    
    # 从context中提取RAG来源
    if context and context.get("rag_result"):
        rag_result = context.get("rag_result")
        if rag_result.get("sources"):
            for source in rag_result["sources"]:
                if isinstance(source, dict):
                    url = source.get("url", "")
                    title = source.get("title", "")
                    if url:
                        sources.append({
                            "type": "rag_source",
                            "url": url,
                            "title": title or url[:50] + "..." if len(url) > 50 else url,
                            "snippet": source.get("snippet", "")[:100]
                        })
    
    return sources


def display_sources(sources: List[Dict[str, Any]]):
    """显示来源链接"""
    if sources:
        # 使用可展开的容器显示来源
        with st.expander("🔗 信息来源（点击查看原文）", expanded=True):
            for i, source in enumerate(sources, 1):
                source_type = source.get("type", "url")
                url = source.get("url", "")
                title = source.get("title", url)
                snippet = source.get("snippet", "")
                
                if url:
                    # 使用markdown显示链接（可点击）
                    if snippet:
                        st.markdown(f"**来源 {i}**: [{title}]({url})")
                        st.caption(f"{snippet}...")
                    else:
                        st.markdown(f"**来源 {i}**: [{title}]({url})")
                    
                    # 添加分隔线（除了最后一个）
                    if i < len(sources):
                        st.divider()


def display_execution_log(log_entries: List[Dict[str, Any]]):
    """显示执行日志"""
    if log_entries:
        with st.expander("📊 执行日志（详细流程）", expanded=True):
            for i, entry in enumerate(log_entries, 1):
                stage = entry.get("stage", "")
                status = entry.get("status", "")
                message = entry.get("message", "")
                elapsed_time = entry.get("elapsed_time", 0)
                details = entry.get("details", {})
                
                # 显示阶段信息
                status_icon = "✅" if status == "success" else "⏳" if status == "running" else "❌"
                st.markdown(f"**{i}. {status_icon} {stage}**")
                
                if message:
                    st.write(f"   {message}")
                
                if elapsed_time > 0:
                    st.caption(f"   耗时: {elapsed_time:.2f}秒")
                
                # 显示详细信息
                if details:
                    with st.expander(f"查看详情", expanded=False):
                        for key, value in details.items():
                            if key == "tool_results" and isinstance(value, list):
                                st.write(f"**{key}**:")
                                for tool_result in value:
                                    st.write(f"  - **{tool_result.get('tool', 'unknown')}**: {tool_result.get('result_preview', '')}")
                            elif isinstance(value, (dict, list)):
                                st.json(value)
                            else:
                                st.write(f"**{key}**: {value}")
                
                if i < len(log_entries):
                    st.divider()


def display_conversation():
    """显示对话历史"""
    if st.session_state.messages:
        # 使用chat_message显示对话
        for idx, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("timestamp"):
                    st.caption(f"时间: {msg['timestamp']}")
                
                # 显示来源链接（如果有，只对assistant消息显示）
                if msg["role"] == "assistant":
                    msg_id = f"msg_{idx}"
                    if msg_id in st.session_state.sources:
                        st.divider()
                        display_sources(st.session_state.sources[msg_id])


def display_system_info():
    """显示系统信息"""
    if st.session_state.system_info:
        st.subheader("📊 系统信息")
        
        # Agent状态
        if "agent_state" in st.session_state.system_info:
            st.write("**Agent状态**:", st.session_state.system_info["agent_state"])
        
        # 意图信息
        if "intent" in st.session_state.system_info:
            st.write("**识别意图**:", st.session_state.system_info["intent"])
        
        # 工具使用
        if "tools_used" in st.session_state.system_info:
            st.write("**使用工具**:", ", ".join(st.session_state.system_info["tools_used"]) if st.session_state.system_info["tools_used"] else "无")
        
        # 记忆统计
        if "memory_stats" in st.session_state.system_info:
            memory_stats = st.session_state.system_info["memory_stats"]
            st.write("**短期记忆**:", f"{memory_stats.get('short_term', 0)} 条消息")
            st.write("**长期记忆**:", f"{memory_stats.get('long_term', 0)} 条记录")


def log_execution_stage(stage: str, status: str, message: str = "", elapsed_time: float = 0, details: Dict = None):
    """记录执行阶段"""
    log_entry = {
        "stage": stage,
        "status": status,
        "message": message,
        "elapsed_time": elapsed_time,
        "details": details or {},
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    st.session_state.execution_log.append(log_entry)
    return log_entry


def process_message(user_input: str):
    """处理用户消息"""
    if not st.session_state.agent:
        st.error("Agent未初始化，请先初始化Agent")
        return
    
    try:
        # 清空执行日志
        st.session_state.execution_log = []
        
        # 添加用户消息到历史
        user_msg = {
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages.append(user_msg)
        
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # 处理消息
        with st.chat_message("assistant"):
            # 创建执行日志显示区域
            log_container = st.container()
            
            # 运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            response = None
            error_occurred = False
            error_message = None
            
            try:
                # 阶段1: 识别用户意图
                stage_start = time.time()
                log_execution_stage(
                    "阶段1: 理解Query - 识别用户意图",
                    "running",
                    f"正在分析用户输入: '{user_input[:50]}...'",
                    0,
                    {"model": "LLM (qwen3-max)", "function": "intent_recognizer.recognize()"}
                )
                
                conversation_history = [msg for msg in st.session_state.messages[-5:]]
                intent = st.session_state.agent.intent_recognizer.recognize(
                    user_input,
                    st.session_state.agent.state,
                    conversation_history
                )
                
                elapsed = time.time() - stage_start
                log_execution_stage(
                    "阶段1: 理解Query - 识别用户意图",
                    "success",
                    f"识别结果: {intent}",
                    elapsed,
                    {"intent": intent, "model": "LLM (qwen3-max)"}
                )
                
                # 阶段2: 检索相关记忆
                stage_start = time.time()
                log_execution_stage(
                    "阶段2: 检索相关记忆",
                    "running",
                    "正在从向量数据库中检索相关记忆...",
                    0,
                    {"model": "Embedding (text-embedding-v4)", "function": "memory_manager.retrieve_relevant_memory()"}
                )
                
                session_id = f"session_{len(st.session_state.agent.memory.messages)}"
                relevant_memory = st.session_state.agent.memory_manager.retrieve_relevant_memory(
                    user_input,
                    session_id
                )
                
                elapsed = time.time() - stage_start
                memory_count = len(relevant_memory.get("long_term", [])) if isinstance(relevant_memory, dict) else 0
                log_execution_stage(
                    "阶段2: 检索相关记忆",
                    "success",
                    f"检索到 {memory_count} 条相关记忆",
                    elapsed,
                    {"memory_count": memory_count, "model": "Embedding (text-embedding-v4)"}
                )
                
                # 阶段3: RAG检索（如果需要）
                rag_result = None
                needs_rag = st.session_state.agent._should_use_rag(user_input, intent)
                if needs_rag:
                    stage_start = time.time()
                    rag_type = "legal" if st.session_state.agent._is_legal_query(user_input) else "web"
                    log_execution_stage(
                        f"阶段3: RAG检索 ({rag_type})",
                        "running",
                        f"正在使用{rag_type} RAG检索相关信息...",
                        0,
                        {"rag_type": rag_type, "model": "Embedding + LLM", "function": "rag_manager.retrieve_and_generate()"}
                    )
                    
                    try:
                        if rag_type == "legal":
                            rag_result = st.session_state.agent.rag_manager.retrieve_and_generate(
                                query=user_input,
                                rag_type="legal",
                                top_k=5
                            )
                        else:
                            rag_result = st.session_state.agent.rag_manager.retrieve_and_generate(
                                query=user_input,
                                rag_type="web",
                                top_k=5
                            )
                        
                        elapsed = time.time() - stage_start
                        source_count = len(rag_result.get("sources", [])) if rag_result else 0
                        log_execution_stage(
                            f"阶段3: RAG检索 ({rag_type})",
                            "success",
                            f"检索到 {source_count} 个来源",
                            elapsed,
                            {"rag_type": rag_type, "source_count": source_count, "answer_source": rag_result.get("answer_source") if rag_result else None}
                        )
                    except Exception as e:
                        elapsed = time.time() - stage_start
                        log_execution_stage(
                            f"阶段3: RAG检索 ({rag_type})",
                            "error",
                            f"RAG检索失败: {str(e)}",
                            elapsed,
                            {"error": str(e)}
                        )
                
                # 阶段4: 工具调用（如果需要）
                stage_start = time.time()
                log_execution_stage(
                    "阶段4: 工具调用",
                    "running",
                    "正在判断是否需要调用工具...",
                    0,
                    {"function": "tool_selector.select_tools()"}
                )
                
                # 调用process_message（内部会处理工具调用）
                response = loop.run_until_complete(
                    st.session_state.agent.process_message(user_input)
                )
                
                elapsed = time.time() - stage_start
                
                # 检查是否使用了工具（从记忆中获取）
                tools_used = []
                tool_results_summary = []
                if hasattr(st.session_state.agent, 'memory'):
                    for msg in st.session_state.agent.memory.messages[-10:]:
                        # 检查assistant消息中的tool_calls
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if isinstance(tool_call, dict):
                                    tool_name = tool_call.get('function', {}).get('name', '')
                                    if tool_name:
                                        tools_used.append(tool_name)
                        # 检查tool消息（工具执行结果）
                        if hasattr(msg, 'role') and (msg.role == 'tool' or (isinstance(msg.role, str) and msg.role == 'tool')):
                            tool_name = getattr(msg, 'name', '') or ''
                            tool_content = getattr(msg, 'content', '') or ''
                            if tool_name:
                                tools_used.append(tool_name)
                                # 提取工具结果摘要
                                if tool_content:
                                    result_preview = tool_content[:100] + "..." if len(tool_content) > 100 else tool_content
                                    tool_results_summary.append({
                                        "tool": tool_name,
                                        "result_preview": result_preview
                                    })
                
                if tools_used:
                    unique_tools = list(set(tools_used))
                    details = {
                        "tools": unique_tools,
                        "model": "LLM (qwen3-max)",
                        "function": "toolcall.think() + toolcall.act()"
                    }
                    if tool_results_summary:
                        details["tool_results"] = tool_results_summary
                    log_execution_stage(
                        "阶段4: 工具调用",
                        "success",
                        f"调用了工具: {', '.join(unique_tools)}",
                        elapsed,
                        details
                    )
                else:
                    log_execution_stage(
                        "阶段4: 工具调用",
                        "success",
                        "无需调用工具",
                        elapsed,
                        {}
                    )
                
                # 阶段5: 生成最终回复
                stage_start = time.time()
                log_execution_stage(
                    "阶段5: 汇总输出 - 生成最终回复",
                    "running",
                    "正在使用LLM生成最终回复...",
                    0,
                    {"model": "LLM (qwen3-max)", "function": "_generate_response()"}
                )
                
                # response已经在process_message中生成
                elapsed = time.time() - stage_start
                log_execution_stage(
                    "阶段5: 汇总输出 - 生成最终回复",
                    "success",
                    f"生成回复成功，长度: {len(response)} 字符",
                    elapsed,
                    {"response_length": len(response), "model": "LLM (qwen3-max)"}
                )
                
                # 阶段6: 保存记忆
                stage_start = time.time()
                log_execution_stage(
                    "阶段6: 保存对话记忆",
                    "running",
                    "正在保存对话到记忆系统...",
                    0,
                    {"function": "memory_manager.save_conversation()"}
                )
                
                # 记忆保存已经在process_message中完成
                elapsed = time.time() - stage_start
                log_execution_stage(
                    "阶段6: 保存对话记忆",
                    "success",
                    "对话已保存到短期和长期记忆",
                    elapsed,
                    {}
                )
                
            except TimeoutError as e:
                error_occurred = True
                error_message = f"⏱️ 超时错误: {str(e)}\n\n系统已自动重试，如果问题持续，请稍后再试。"
                log_execution_stage(
                    "错误处理",
                    "error",
                    f"超时错误: {str(e)}",
                    0,
                    {"error_type": "TimeoutError", "error": str(e)}
                )
            except Exception as e:
                error_occurred = True
                error_message = f"❌ 处理错误: {str(e)}\n\n系统已自动重试，如果问题持续，请检查网络连接或联系管理员。"
                log_execution_stage(
                    "错误处理",
                    "error",
                    f"处理错误: {str(e)}",
                    0,
                    {"error_type": type(e).__name__, "error": str(e)}
                )
            finally:
                loop.close()
            
            # 显示执行日志
            with log_container:
                display_execution_log(st.session_state.execution_log)
            
            # 显示回复或错误
            if error_occurred:
                st.error(error_message)
                if response:
                    st.warning("⚠️ 部分回复已生成，但可能不完整：")
                    st.markdown(response)
            else:
                # 显示回复
                st.markdown(response)
                
                # 提取来源信息
                sources = []
                try:
                    # 从回复文本中提取URL（包括markdown格式的链接）
                    # 提取普通URL
                    urls = extract_urls_from_text(response)
                    for url in urls:
                        sources.append({
                            "type": "url",
                            "url": url,
                            "title": url[:50] + "..." if len(url) > 50 else url
                        })
                    
                    # 提取markdown格式的链接 [title](url)
                    markdown_link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
                    markdown_links = re.findall(markdown_link_pattern, response)
                    for title, url in markdown_links:
                        # 检查是否是http链接
                        if url.startswith('http://') or url.startswith('https://'):
                            # 提取snippet（如果回复中有相关信息）
                            snippet = ""
                            # 尝试从回复中找到相关的snippet
                            url_index = response.find(url)
                            if url_index > 0:
                                # 获取URL前后的文本作为snippet
                                start = max(0, url_index - 50)
                                end = min(len(response), url_index + len(url) + 50)
                                snippet = response[start:end].replace(url, "").strip()[:100]
                            
                            sources.append({
                                "type": "url",
                                "url": url,
                                "title": title,
                                "snippet": snippet
                            })
                    
                    # 去重（基于URL）
                    seen_urls = set()
                    unique_sources = []
                    for source in sources:
                        url = source.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            unique_sources.append(source)
                    sources = unique_sources
                    
                except Exception as e:
                    print(f"Warning: Failed to extract sources: {e}")
                
                # 显示来源链接（在回复下方，如果有来源信息）
                if sources:
                    st.divider()
                    display_sources(sources)
                
                # 添加回复到历史
                assistant_msg = {
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                msg_idx = len(st.session_state.messages)
                st.session_state.messages.append(assistant_msg)
                
                # 保存来源信息
                if sources:
                    st.session_state.sources[f"msg_{msg_idx}"] = sources
                
                # 更新系统信息
                update_system_info()
    
    except Exception as e:
        st.error(f"处理消息时出错: {str(e)}")
        import traceback
        with st.expander("错误详情"):
            st.code(traceback.format_exc())


def update_system_info():
    """更新系统信息"""
    if st.session_state.agent:
        try:
            # Agent状态
            agent_state = st.session_state.agent.state.value if hasattr(st.session_state.agent.state, 'value') else str(st.session_state.agent.state)
            
            # 意图信息（从最近的消息中获取）
            intent = "unknown"
            if st.session_state.messages:
                last_user_msg = None
                for msg in reversed(st.session_state.messages):
                    if msg["role"] == "user":
                        last_user_msg = msg["content"]
                        break
                
                if last_user_msg:
                    try:
                        intent = st.session_state.agent.intent_recognizer.recognize(
                            last_user_msg,
                            st.session_state.agent.state,
                            [m for m in st.session_state.messages[-5:]]
                        )
                    except:
                        pass
            
            # 工具使用（从记忆中获取）
            tools_used = []
            if hasattr(st.session_state.agent, 'memory'):
                for msg in st.session_state.agent.memory.messages[-10:]:
                    # 检查assistant消息中的tool_calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get('function', {}).get('name', '')
                                if tool_name:
                                    tools_used.append(tool_name)
                    # 检查tool消息
                    if hasattr(msg, 'role') and (msg.role == 'tool' or (isinstance(msg.role, str) and msg.role == 'tool')):
                        tool_name = getattr(msg, 'name', '') or ''
                        if tool_name:
                            tools_used.append(tool_name)
            
            # 记忆统计
            short_term_count = len(st.session_state.agent.memory.messages) if hasattr(st.session_state.agent, 'memory') else 0
            long_term_count = 0
            try:
                long_term_count = st.session_state.agent.memory_manager.vector_db.count_memories()
            except:
                pass
            
            st.session_state.system_info = {
                "agent_state": agent_state,
                "intent": intent,
                "tools_used": list(set(tools_used)),
                "memory_stats": {
                    "short_term": short_term_count,
                    "long_term": long_term_count
                }
            }
        except Exception as e:
            st.warning(f"更新系统信息时出错: {str(e)}")


def main():
    """主函数"""
    # 标题
    st.title("🤖 Agent System")
    st.markdown("一个完整的智能Agent系统，包含工具系统、记忆系统、上下文管理、意图识别、RAG检索等功能")
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 系统设置")
        
        # 初始化Agent按钮
        if st.button("🚀 初始化Agent", use_container_width=True):
            with st.spinner("正在初始化Agent..."):
                agent, error = init_agent()
                if agent:
                    st.session_state.agent = agent
                    st.success("Agent初始化成功！")
                    st.session_state.system_info = {}
                    st.session_state.execution_log = []
                    update_system_info()
                else:
                    st.error(f"Agent初始化失败: {error}")
        
        # Agent状态
        if st.session_state.agent:
            st.success("✅ Agent已初始化")
            st.divider()
            
            # 系统信息
            display_system_info()
            
            # 清空对话按钮
            if st.button("🗑️ 清空对话", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.session_state.sources = {}
                st.session_state.execution_log = []
                if st.session_state.agent:
                    st.session_state.agent.memory.clear()
                st.rerun()
            
            # 重置Agent按钮
            if st.button("🔄 重置Agent", use_container_width=True):
                st.session_state.agent = None
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.session_state.system_info = {}
                st.session_state.sources = {}
                st.session_state.execution_log = []
                st.rerun()
        else:
            st.warning("⚠️ Agent未初始化")
            st.info("请点击上方按钮初始化Agent")
        
        st.divider()
        
        # 配置信息
        st.subheader("📋 配置信息")
        st.write("**LLM模型**: qwen3-max")
        st.write("**Embedding模型**: text-embedding-v4")
        st.write("**向量数据库**: ChromaDB")
        st.write("**LLM超时**: 120秒")
        st.write("**Embedding超时**: 300秒")
        
        # 环境变量检查
        st.subheader("🔍 环境检查")
        dashscope_key = os.getenv("DASHSCOPE_API_KEY", "未设置")
        if dashscope_key != "未设置":
            st.success(f"✅ DASHSCOPE_API_KEY: {dashscope_key[:20]}...")
        else:
            st.error("❌ DASHSCOPE_API_KEY未设置")
    
    # 主界面
    if not st.session_state.agent:
        st.info("👈 请在侧边栏初始化Agent后开始对话")
        st.markdown("""
        ### 使用说明
        
        1. 点击侧边栏的"🚀 初始化Agent"按钮
        2. 等待Agent初始化完成
        3. 在下方输入框中输入问题
        4. 查看Agent的回复和执行日志
        
        ### 功能特性
        
        - 💬 多轮对话：支持连续对话，保持上下文
        - 🔍 意图识别：自动识别用户意图
        - 🛠️ 工具调用：自动选择合适的工具
        - 💾 记忆管理：短期记忆和长期记忆
        - 📊 执行日志：详细显示每个阶段的执行过程和耗时
        - 🔗 来源链接：显示信息来源，方便验证
        """)
    else:
        # 显示对话历史
        display_conversation()
        
        # 输入框
        user_input = st.chat_input("请输入您的问题...")
        
        if user_input:
            process_message(user_input)
            st.rerun()
        
        # 显示系统信息（在底部）
        if st.session_state.system_info:
            with st.expander("📊 详细系统信息", expanded=False):
                display_system_info()
                
                # 显示最近的对话统计
                if st.session_state.messages:
                    st.subheader("📈 对话统计")
                    user_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
                    assistant_count = sum(1 for m in st.session_state.messages if m["role"] == "assistant")
                    st.write(f"用户消息: {user_count} 条")
                    st.write(f"Agent回复: {assistant_count} 条")
                    st.write(f"总计: {len(st.session_state.messages)} 条")
                    
                    # 显示最近的工具使用
                    if st.session_state.system_info.get("tools_used"):
                        st.subheader("🛠️ 工具使用历史")
                        for tool in st.session_state.system_info["tools_used"]:
                            st.write(f"- {tool}")


if __name__ == "__main__":
    main()
