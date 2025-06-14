"""
DeepSearch - 智能深度研究助手
基于 Streamlit 的主应用程序，支持实时进度显示
"""

import streamlit as st
import asyncio
import json
import os
import time
import threading
import concurrent.futures
from datetime import datetime
from typing import Dict, Any
from enum import Enum
import queue

# from streamlit_local_storage import LocalStorage  # 暂时禁用，有bug
import streamlit.components.v1 as components

class SafeLocalStorage:
    """安全的LocalStorage实现，使用session state作为主要存储"""
    
    def __init__(self):
        self._cache = {}
        self._cache_file = ".streamlit_cache.json"
    
    def _load_from_file_cache(self):
        """从文件缓存加载数据"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_to_file_cache(self, data):
        """保存数据到文件缓存"""
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def getItem(self, key, default=None):
        """从session state或文件缓存获取数据"""
        # 首先检查session state缓存
        session_key = f"ls_{key}"
        if session_key in st.session_state:
            cached_value = st.session_state[session_key]
            if cached_value is not None and cached_value != "null" and str(cached_value).strip() != "":
                return cached_value
        
        # 如果session state中没有，尝试从文件缓存加载
        if not hasattr(st.session_state, '_file_cache_loaded'):
            file_cache = self._load_from_file_cache()
            if file_cache:
                for cache_key, cache_value in file_cache.items():
                    if cache_value is not None and str(cache_value).strip() != "":
                        st.session_state[f"ls_{cache_key}"] = cache_value
                st.session_state._file_cache_loaded = True
                
                # 再次检查session state
                if session_key in st.session_state:
                    cached_value = st.session_state[session_key]
                    if cached_value is not None and cached_value != "null" and str(cached_value).strip() != "":
                        return cached_value
        
        # 如果都没有，返回默认值
        return default
    
    def setItem(self, key, value):
        """向LocalStorage、session state和文件缓存保存数据"""
        try:
            # 缓存到session state
            session_key = f"ls_{key}"
            st.session_state[session_key] = value
            self._cache[key] = value
            
            # 保存到文件缓存
            try:
                file_cache = self._load_from_file_cache()
                file_cache[key] = value
                self._save_to_file_cache(file_cache)
            except Exception:
                pass  # 文件缓存失败不影响主要功能
            
            # 使用HTML/JS方法保存到浏览器LocalStorage
            if isinstance(value, str):
                # 对于JSON字符串，需要更仔细的转义
                escaped_value = (value.replace('\\', '\\\\')
                               .replace("'", "\\'")
                               .replace('"', '\\"')
                               .replace('\n', '\\n')
                               .replace('\r', '\\r')
                               .replace('\t', '\\t'))
            else:
                escaped_value = str(value).replace("'", "\\'").replace('"', '\\"')
            
            html_code = f"""
            <script>
                try {{
                    localStorage.setItem('{key}', '{escaped_value}');
                    console.log('Saved to localStorage:', '{key}');
                }} catch (e) {{
                    console.error('LocalStorage save error:', e);
                }}
            </script>
            """
            components.html(html_code, height=0)
            
            return True
        except Exception as e:
            st.warning(f"保存到LocalStorage失败: {e}")
            return False
    
    def removeItem(self, key):
        """从LocalStorage、session state和文件缓存删除数据"""
        try:
            # 从缓存中删除
            if key in self._cache:
                del self._cache[key]
            
            # 从session state中删除
            session_key = f"ls_{key}"
            if session_key in st.session_state:
                del st.session_state[session_key]
            
            # 从文件缓存中删除
            try:
                file_cache = self._load_from_file_cache()
                if key in file_cache:
                    del file_cache[key]
                    self._save_to_file_cache(file_cache)
            except Exception:
                pass  # 文件缓存失败不影响主要功能
            
            # 使用HTML/JS方法从浏览器LocalStorage中删除
            html_code = f"""
            <script>
                try {{
                    localStorage.removeItem('{key}');
                    console.log('Removed from localStorage:', '{key}');
                }} catch (e) {{
                    console.error('LocalStorage remove error:', e);
                }}
            </script>
            """
            components.html(html_code, height=0)
            
            return True
        except Exception as e:
            st.warning(f"从LocalStorage删除失败: {e}")
            return False

# 导入核心组件
from core.research_engine import ResearchEngine
from core.state_manager import TaskStatus
from utils.debug_logger import enable_debug, disable_debug, get_debug_logger
from utils.streamlit_helpers import (
    json_serializable,
    create_markdown_content,
    display_task_analysis,
    display_search_results,
    display_final_answer,
)

# 页面配置
st.set_page_config(
    page_title="🔍 DeepSearch",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 可用的模型列表（基于测试结果更新）
AVAILABLE_MODELS = {
    "gemini-2.0-flash": "🚀 Gemini 2.0 Flash - 便宜最快",
    "gemini-2.5-flash-preview-05-20": "⚡ Gemini 2.5 Flash - 最新功能",
    "gemini-2.5-pro-preview-06-05": "💫 Gemini 2.5 Pro - 0605最新"
}

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .thinking-box {
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 10px;
        background-color: #f0f8ff;
        border-left: 4px solid #4169e1;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.8; }
        50% { opacity: 1; }
        100% { opacity: 0.8; }
    }
    
    .progress-step {
        padding: 0.5rem;
        margin: 0.2rem 0;
        border-radius: 5px;
        background-color: #f8f9fa;
        border-left: 3px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """初始化会话状态"""
    defaults = {
        "research_engine": None,
        "current_task": None,
        "research_results": [],
        "progress_messages": [],
        "api_key_validated": False,
        "is_researching": False,
        "current_step": "",
        "progress_percentage": 0,
        "model_name": "gemini-2.0-flash",
        "research_complete": False,
        "research_error": None,
        "research_started": False,  # 添加执行标记
        "just_completed": False,    # 刚刚完成标记
        "debug_enabled": False,     # debug模式开关
        "show_markdown_preview": False  # markdown预览开关
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # 初始化LocalStorage数据加载
    initialize_from_localstorage()

    # 尝试从LocalStorage加载API密钥
    try:
        if "ls_api_key" not in st.session_state:
            localS = SafeLocalStorage()
            initial_api_key = localS.getItem("api_key")
            st.session_state.ls_api_key = initial_api_key
        else:
            initial_api_key = st.session_state.ls_api_key
            
        if (initial_api_key and 
            initial_api_key != "null" and 
            initial_api_key != None and
            str(initial_api_key).strip() != ""):
            st.session_state.api_key_to_load = initial_api_key
    except Exception:
        pass  # 忽略LocalStorage加载错误


def initialize_from_localstorage():
    """在应用启动时从浏览器LocalStorage加载数据到session state"""
    if 'localstorage_initialized' not in st.session_state:
        # 创建一个唯一的会话ID来标识这次加载
        session_id = str(hash(str(st.session_state)))[-8:]
        
        # 创建JavaScript代码来读取LocalStorage并通过URL参数传递数据
        html_code = f"""
        <script>
            function loadFromLocalStorage() {{
                try {{
                    // 读取API密钥
                    const apiKey = localStorage.getItem('api_key');
                    if (apiKey && apiKey !== 'null' && apiKey.trim() !== '') {{
                        console.log('Found API key in localStorage, length:', apiKey.length);
                        // 将API密钥存储到一个隐藏的meta标签中
                        let metaApiKey = document.querySelector('meta[name="ls-api-key"]');
                        if (!metaApiKey) {{
                            metaApiKey = document.createElement('meta');
                            metaApiKey.name = 'ls-api-key';
                            document.head.appendChild(metaApiKey);
                        }}
                        metaApiKey.content = apiKey;
                    }}
                    
                    // 读取研究结果
                    const researchResults = localStorage.getItem('research_results');
                    if (researchResults && researchResults !== 'null' && researchResults.trim() !== '') {{
                        console.log('Found research results in localStorage, length:', researchResults.length);
                        // 将研究结果存储到一个隐藏的meta标签中
                        let metaResults = document.querySelector('meta[name="ls-research-results"]');
                        if (!metaResults) {{
                            metaResults = document.createElement('meta');
                            metaResults.name = 'ls-research-results';
                            document.head.appendChild(metaResults);
                        }}
                        metaResults.content = researchResults;
                    }}
                    
                    console.log('LocalStorage data loaded to meta tags');
                }} catch (e) {{
                    console.error('Error loading LocalStorage:', e);
                }}
            }}
            
            // 页面加载完成后执行加载
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', loadFromLocalStorage);
            }} else {{
                loadFromLocalStorage();
            }}
        </script>
        """
        
        components.html(html_code, height=0)
        st.session_state['localstorage_initialized'] = True


def validate_and_setup_engine(api_key: str, model_name: str) -> bool:
    """验证API密钥并设置引擎"""
    if not api_key or len(api_key) < 10:
        return False
    
    try:
        if (st.session_state.research_engine is None or 
            st.session_state.model_name != model_name):
            
            engine = ResearchEngine(api_key, model_name)
            st.session_state.research_engine = engine
            st.session_state.model_name = model_name
            
        return True
    except Exception as e:
        st.error(f"API密钥验证失败: {str(e)}")
        return False


def setup_api_key():
    """设置API密钥和模型选择"""
    st.sidebar.header("🔧 配置")
    
    localS = SafeLocalStorage()
    
    # 模型选择
    model_name = st.sidebar.selectbox(
        "选择模型",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
        format_func=lambda x: AVAILABLE_MODELS[x],
        help="选择要使用的Gemini模型版本"
    )
    
    # 优先使用 state 中预加载的 key
    api_key_from_storage = st.session_state.get("api_key_to_load")
    
    # 如果没有从secrets获取到，让用户输入
    api_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password",
        value=api_key_from_storage or "",
        help="请输入您的 Google Gemini API 密钥"
    )
    
    if api_key:
        if validate_and_setup_engine(api_key, model_name):
            st.session_state.api_key_validated = True
            st.sidebar.success("✅ API密钥配置成功")
            
            # 总是保存有效的API密钥到localStorage（确保持久化）
            try:
                localS.setItem("api_key", api_key)
                st.session_state.api_key_to_load = api_key # 更新state
                st.session_state.ls_api_key = api_key # 更新缓存
            except Exception as e:
                st.sidebar.warning(f"⚠️ 保存API密钥失败: {e}")
            
            # 显示模型配置详情
            if st.session_state.research_engine:
                model_config = st.session_state.research_engine.model_config
                with st.sidebar.expander("📋 模型配置详情", expanded=False):
                    st.text(f"🔍 搜索: {model_config.search_model}")
                    st.text(f"📊 分析: {model_config.task_analysis_model}")
                    st.text(f"🤔 反思: {model_config.reflection_model}")
                    st.text(f"📝 答案: {model_config.answer_model}")
            
            # Debug开关
            st.sidebar.divider()
            st.sidebar.subheader("🐛 Debug模式")
            
            debug_enabled = st.sidebar.checkbox(
                "启用调试模式",
                value=st.session_state.debug_enabled,
                help="启用后将记录所有API请求和响应到JSON文件，用于调试"
            )
            
            if debug_enabled != st.session_state.debug_enabled:
                st.session_state.debug_enabled = debug_enabled
                if debug_enabled:
                    enable_debug("debug_logs")
                    st.sidebar.success("🐛 Debug模式已启用")
                    st.sidebar.info("📁 日志将保存到 debug_logs/ 目录")
                else:
                    disable_debug()
                    st.sidebar.info("🐛 Debug模式已禁用")
            
            if debug_enabled:
                debug_logger = get_debug_logger()
                if debug_logger.current_session:
                    st.sidebar.text(f"📝 会话ID: {debug_logger.current_session}")
                    
                    # 显示会话摘要
                    summary = debug_logger.get_session_summary()
                    if summary:
                        with st.sidebar.expander("📊 Debug统计", expanded=False):
                            # API请求统计
                            api_stats = summary.get("api_requests", {})
                            st.markdown("**🔗 API请求统计**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("总请求", api_stats.get("total", 0))
                                st.metric("成功", api_stats.get("successful", 0))
                            with col2:
                                st.metric("失败", api_stats.get("failed", 0))
                            
                            # 按类型统计
                            by_type = api_stats.get("by_type", {})
                            if by_type:
                                st.markdown("**请求类型分布:**")
                                for req_type, count in by_type.items():
                                    st.text(f"• {req_type}: {count}")
                            
                            # 按模型统计
                            by_model = api_stats.get("by_model", {})
                            if by_model:
                                st.markdown("**模型使用分布:**")
                                for model, count in by_model.items():
                                    st.text(f"• {model}: {count}")
                            
                            st.divider()
                            
                            # 搜索统计
                            search_stats = summary.get("searches", {})
                            st.markdown("**🔍 搜索统计**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("总搜索", search_stats.get("total", 0))
                                st.metric("成功", search_stats.get("successful", 0))
                            with col2:
                                st.metric("失败", search_stats.get("failed", 0))
                                st.metric("总引用", search_stats.get("total_citations", 0))
                            
                            st.divider()
                            
                            # 工作流统计
                            workflow_stats = summary.get("workflow", {})
                            st.markdown("**⚙️ 工作流统计**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("总步骤", workflow_stats.get("total_steps", 0))
                                st.metric("已完成", workflow_stats.get("completed_steps", 0))
                            with col2:
                                st.metric("失败", workflow_stats.get("failed_steps", 0))
                            
                            # 步骤序列
                            step_sequence = workflow_stats.get("step_sequence", [])
                            if step_sequence:
                                st.markdown("**执行序列:**")
                                for i, step in enumerate(step_sequence, 1):
                                    st.text(f"{i}. {step}")
                            
                            # 步骤耗时
                            step_durations = workflow_stats.get("step_durations", {})
                            if step_durations:
                                st.markdown("**步骤耗时:**")
                                for step, duration in step_durations.items():
                                    if duration > 0:
                                        st.text(f"• {step}: {duration:.2f}s")
                            
                            st.divider()
                            
                            # 会话信息
                            session_duration = summary.get("session_duration", 0)
                            if session_duration > 0:
                                st.metric("会话时长", f"{session_duration:.2f}s")
                            
                            # 错误统计
                            error_stats = summary.get("errors", {})
                            if error_stats.get("total", 0) > 0:
                                st.markdown("**❌ 错误统计**")
                                st.metric("错误总数", error_stats.get("total", 0))
                                by_error_type = error_stats.get("by_type", {})
                                if by_error_type:
                                    for error_type, count in by_error_type.items():
                                        st.text(f"• {error_type}: {count}")
                    
                    # 立即保存按钮
                    if st.sidebar.button("💾 保存Debug日志"):
                        debug_logger.save_now()
                        st.sidebar.success("✅ Debug日志已保存")
                    
                    # 查看详细日志按钮
                    if st.sidebar.button("📋 查看详细日志"):
                        st.session_state.show_debug_details = True
        else:
            st.session_state.api_key_validated = False
            st.sidebar.error("❌ API密钥验证失败")
    
    return st.session_state.api_key_validated


def display_real_time_progress():
    """显示实时进度"""
    if st.session_state.is_researching and st.session_state.progress_messages:
        
        # 显示当前步骤
        if st.session_state.current_step:
            st.markdown(f'''
            <div class="thinking-box">
                🤔 <strong>{st.session_state.current_step}</strong>
            </div>
            ''', unsafe_allow_html=True)
        
        # 显示进度条
        if st.session_state.progress_percentage > 0:
            st.progress(st.session_state.progress_percentage / 100)
        
        # 显示思考过程
        with st.expander("📝 思考过程", expanded=True):
            for i, msg in enumerate(st.session_state.progress_messages, 1):
                st.markdown(f'<div class="progress-step">{i}. {msg}</div>', 
                          unsafe_allow_html=True)


def run_research_in_background(
    engine, user_query, max_search_rounds, effort_level, num_search_queries, q, stop_event
):
    """在后台线程中运行研究任务"""
    try:
        # 为这个线程创建一个新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def progress_callback(message, percentage):
            if stop_event.is_set():
                engine.stop_research()
                raise Exception("用户请求停止")
            q.put({"type": "progress", "message": message, "percentage": percentage})

        def step_callback(message):
            if stop_event.is_set():
                engine.stop_research()
                raise Exception("用户请求停止")
            q.put({"type": "step", "message": message})
            
        def error_callback(message):
            q.put({"type": "error", "message": message})

        engine.set_callbacks(
            progress_callback=progress_callback,
            step_callback=step_callback,
            error_callback=error_callback,
        )
        
        # 重置引擎的停止标记
        engine.reset_stop_flag()

        # 运行异步研究方法
        results = loop.run_until_complete(
            engine.research(user_query, max_search_rounds, effort_level, num_search_queries)
        )
        q.put({"type": "result", "data": results})
        
    except Exception as e:
        if "用户请求停止" not in str(e):
            error_msg = f"研究过程中发生严重错误: {str(e)}"
            q.put({"type": "error", "message": error_msg})
        # 如果是用户停止，回调中已经处理了，这里不需要重复发送消息


def research_interface():
    """研究主界面"""
    st.title("🔍 DeepSearch - 智能深度研究助手")
    st.markdown("### 智能深度研究助手")
    
    # 初始化线程池执行器
    if "executor" not in st.session_state:
        st.session_state.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    # 查询输入
    user_query = st.text_area(
        "请输入您的研究问题:",
        height=100,
        placeholder="例如: 分析2024年人工智能发展趋势...",
        help="请描述您想要深入研究的问题或主题",
        disabled=st.session_state.is_researching
    )
    
    # 研究参数设置
    col1, col2 = st.columns(2)
    with col1:
        effort_level = st.selectbox(
            "研究强度",
            ["low", "medium", "high"],
            index=1,
            format_func=lambda x: {"low": "🟢 低强度", "medium": "🟡 中强度", "high": "🔴 高强度"}[x],
            help="低强度: 1轮×3查询, 中强度: 3轮×5查询, 高强度: 5轮×10查询",
            disabled=st.session_state.is_researching
        )
    
    with col2:
        # 根据强度显示配置信息
        effort_configs = {
            "low": {"rounds": "1轮(最多3轮)", "queries": 3, "time": "1-5分钟"},
            "medium": {"rounds": 3, "queries": 5, "time": "4-10分钟"},
            "high": {"rounds": 5, "queries": 10, "time": "8-20分钟"}
        }
        config = effort_configs[effort_level]
        
        st.info(f"""
        📊 **当前配置**
        - 🔄 搜索轮数: {config['rounds']}轮
        - 🔍 每轮查询: {config['queries']}个
        - ⏱️ 预计时间: {config['time']}
        """)
        
        # 设置默认值，但允许用户在高级设置中覆盖
        default_max_rounds = {"low": 3, "medium": 3, "high": 5}[effort_level]
        max_search_rounds = default_max_rounds
        num_search_queries = config['queries']
        
        with st.expander("⚙️ 高级设置", expanded=False):
            max_search_rounds = st.slider(
                "自定义最大搜索轮数", 1, 10, default_max_rounds,
                help="覆盖默认的搜索轮数设置",
                disabled=st.session_state.is_researching
            )
            
            num_search_queries = st.slider(
                "自定义每轮查询数量", 1, 15, config['queries'],
                help="覆盖默认的每轮查询数量",
                disabled=st.session_state.is_researching
            )
            
            st.info(f"💡 **说明**: 低强度默认1轮搜索，信息不足时自动补充，最多3轮")
    
    # 开始/停止研究按钮
    if not st.session_state.is_researching:
        if st.button("🚀 开始研究", type="primary", disabled=not user_query.strip()):
            if not st.session_state.research_engine:
                st.error("研究引擎未初始化，请检查API密钥配置")
            else:
                st.session_state.is_researching = True
                st.session_state.research_complete = False
                st.session_state.research_error = None
                st.session_state.progress_messages = ["🚀 研究任务已启动..."]
                st.session_state.current_step = "初始化..."
                st.session_state.progress_percentage = 0
                st.session_state.research_results = []
                st.session_state.just_completed = False

                q = queue.Queue()
                stop_event = threading.Event()
                st.session_state.queue = q
                st.session_state.stop_event = stop_event

                st.session_state.current_task_future = st.session_state.executor.submit(
                    run_research_in_background,
                    st.session_state.research_engine,
                    user_query,
                    max_search_rounds,
                    effort_level,
                    num_search_queries,
                    q,
                    stop_event,
                )
                st.rerun()
    else:
        if st.button("⏹️ 停止研究", type="secondary"):
            if "stop_event" in st.session_state:
                st.session_state.stop_event.set()
            # 状态将在队列处理器中重置

    # 研究进行中，处理队列更新
    if st.session_state.is_researching:
        display_real_time_progress()

        if "queue" in st.session_state:
            try:
                while not st.session_state.queue.empty():
                    item = st.session_state.queue.get_nowait()
                    if item["type"] == "progress":
                        msg = f"[{item['percentage']:.1f}%] {item['message']}"
                        st.session_state.progress_messages.append(msg)
                        st.session_state.progress_percentage = item["percentage"]
                    elif item["type"] == "step":
                        st.session_state.current_step = item["message"]
                        st.session_state.progress_messages.append(f"⚡ {item['message']}")
                    elif item["type"] == "result":
                        st.session_state.is_researching = False
                        st.session_state.research_complete = True
                        st.session_state.current_task = item["data"]
                        st.session_state.research_results.append(item["data"])
                        st.session_state.just_completed = True
                        
                        # 保存到LocalStorage
                        try:
                            localS = SafeLocalStorage()
                            serializable_results = json_serializable(st.session_state.research_results)
                            # 转换为JSON字符串
                            json_string = json.dumps(serializable_results, ensure_ascii=False)
                            success = localS.setItem("research_results", json_string)
                            if success:
                                # 更新缓存
                                st.session_state.ls_research_results = json_string
                            else:
                                st.warning("⚠️ 保存历史记录到LocalStorage失败")
                        except Exception as e:
                            st.warning(f"⚠️ 保存历史记录失败: {e}")
                            import traceback
                            st.error(f"详细错误: {traceback.format_exc()}")

                    elif item["type"] == "error":
                        st.session_state.is_researching = False
                        st.session_state.research_error = item["message"]
                    elif item["type"] == "info": # 用于处理用户停止等情况
                        st.session_state.is_researching = False
                        st.info(item["message"])

                # 如果仍在研究中，安排下一次刷新
                if st.session_state.is_researching:
                    time.sleep(0.1)
                    st.rerun()
                else: # 研究刚刚结束，刷新一次以显示最终结果
                    st.rerun()
            except queue.Empty:
                # 队列为空，检查后台任务是否仍在运行
                if st.session_state.is_researching:
                    future = st.session_state.get("current_task_future")
                    if future and future.done():
                        # 任务已结束，但队列中没有消息，说明可能发生意外
                        try:
                            # 尝试获取结果，这会重新引发在线程中发生的任何异常
                            future.result() 
                            # 如果没有异常，但走到了这里，说明逻辑有问题
                            st.session_state.research_error = "研究意外终止，但未报告明确错误。"
                        except Exception as e:
                            # 捕获到后台任务的异常
                            st.session_state.research_error = f"研究任务在后台发生错误: {e}"
                        
                        st.session_state.is_researching = False
                        st.rerun()
                    else:
                        # 任务仍在运行，队列为空是正常的，继续轮询
                        time.sleep(0.1)
                        st.rerun()

    # 显示历史研究结果
    if st.session_state.research_results:
        # 如果有刚完成的研究，显示成功提示
        if st.session_state.just_completed:
            st.success("🎉 研究完成！")
            st.session_state.just_completed = False # 重置标记，避免重复显示
        
        st.markdown("---")
        st.subheader("📜 研究历史记录")
        for i, result in enumerate(reversed(st.session_state.research_results)):
            task_id = result.get("task_id", f"history_{i}")
            # 从task_id中提取时间戳，如果失败则使用当前时间
            try:
                if task_id.startswith("task_") and len(task_id) >= 20:
                    timestamp_str = task_id[5:20]  # 提取 YYYYMMDD_HHMMSS 部分
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    time_display = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    time_display = "未知时间"
            except:
                time_display = "未知时间"
            
            with st.expander(f"**{result.get('user_query', '未知查询')}** - {time_display} ({task_id[:20]})", expanded=(i==0)):
                if result.get("success"):
                    display_final_answer(result, index=i)
                    display_search_results(result)
                    display_task_analysis(result.get("workflow_analysis"), result.get("task_id"))
                else:
                    st.error(f"研究失败: {result.get('error', '未知错误')}")

    # 如果有错误，显示错误信息
    if st.session_state.research_error and not st.session_state.is_researching:
        st.error(f"❌ 研究失败: {st.session_state.research_error}")
    
    # 显示详细Debug日志
    if st.session_state.get("show_debug_details", False):
        st.markdown("---")
        st.subheader("🐛 详细Debug日志")
        
        from utils.debug_logger import get_debug_logger
        debug_logger = get_debug_logger()
        
        if debug_logger.enabled and debug_logger.session_data:
            # 创建标签页
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 API请求", "🔍 搜索结果", "⚙️ 工作流步骤", "❌ 错误日志", "📊 会话信息"])
            
            with tab1:
                st.markdown("### API请求详情")
                api_requests = debug_logger.session_data.get("api_requests", [])
                if api_requests:
                    for i, req in enumerate(api_requests):
                        with st.expander(f"请求 {i+1}: {req.get('request_type', 'unknown')} - {req.get('context', '')}", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text(f"时间: {req.get('timestamp', 'N/A')}")
                                st.text(f"请求ID: {req.get('request_id', 'N/A')}")
                                st.text(f"模型: {req.get('model', 'N/A')}")
                                st.text(f"类型: {req.get('request_type', 'N/A')}")
                                st.text(f"上下文: {req.get('context', 'N/A')}")
                            with col2:
                                st.text(f"Prompt长度: {req.get('full_prompt_length', 0)}")
                                response = req.get('response', {})
                                if response:
                                    st.text(f"响应长度: {response.get('full_response_length', 0)}")
                                    st.text(f"耗时: {response.get('duration', 0):.2f}s")
                                    st.text(f"状态: {response.get('status', 'N/A')}")
                            
                            # 显示完整prompt和响应
                            if st.checkbox(f"显示完整内容 - 请求{i+1}", key=f"show_full_req_{i}"):
                                st.text_area("完整Prompt:", req.get('full_prompt', ''), height=200, key=f"prompt_{i}")
                                if response and response.get('full_response'):
                                    st.text_area("完整响应:", response.get('full_response', ''), height=200, key=f"response_{i}")
                else:
                    st.info("暂无API请求记录")
            
            with tab2:
                st.markdown("### 搜索结果详情")
                search_results = debug_logger.session_data.get("search_results", [])
                if search_results:
                    for i, search in enumerate(search_results):
                        with st.expander(f"搜索 {i+1}: {search.get('query', 'unknown')[:50]}...", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text(f"时间: {search.get('timestamp', 'N/A')}")
                                st.text(f"查询: {search.get('query', 'N/A')}")
                                st.text(f"类型: {search.get('search_type', 'N/A')}")
                                st.text(f"成功: {search.get('success', False)}")
                            with col2:
                                st.text(f"内容长度: {search.get('content_length', 0)}")
                                st.text(f"引用数: {search.get('citations_count', 0)}")
                                st.text(f"URL数: {search.get('urls_count', 0)}")
                                st.text(f"耗时: {search.get('duration', 0):.2f}s")
                            
                            # 显示完整搜索结果
                            if st.checkbox(f"显示完整结果 - 搜索{i+1}", key=f"show_full_search_{i}"):
                                full_result = search.get('full_result', {})
                                st.json(full_result)
                else:
                    st.info("暂无搜索记录")
            
            with tab3:
                st.markdown("### 工作流步骤详情")
                workflow_steps = debug_logger.session_data.get("workflow_steps", [])
                if workflow_steps:
                    for i, step in enumerate(workflow_steps):
                        step_name = step.get('step_name', 'unknown')
                        step_status = step.get('step_status', 'unknown')
                        duration = step.get('duration', 0)
                        
                        status_icon = {"completed": "✅", "running": "🔄", "failed": "❌", "info": "ℹ️", "decision": "🤔"}.get(step_status, "❓")
                        
                        with st.expander(f"步骤 {i+1}: {status_icon} {step_name} [{duration:.2f}s]", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text(f"时间: {step.get('timestamp', 'N/A')}")
                                st.text(f"步骤名: {step_name}")
                                st.text(f"状态: {step_status}")
                                if step.get('step_index') is not None:
                                    st.text(f"步骤索引: {step.get('step_index', 0) + 1}/{step.get('total_steps', 0)}")
                            with col2:
                                st.text(f"耗时: {duration:.2f}s")
                                if step.get('error_message'):
                                    st.text(f"错误: {step.get('error_message', '')}")
                            
                            # 显示输入输出数据
                            if st.checkbox(f"显示详细数据 - 步骤{i+1}", key=f"show_step_data_{i}"):
                                if step.get('full_input'):
                                    st.text("输入数据:")
                                    st.json(step.get('input_summary', {}))
                                if step.get('full_output'):
                                    st.text("输出数据:")
                                    st.json(step.get('output_summary', {}))
                else:
                    st.info("暂无工作流步骤记录")
            
            with tab4:
                st.markdown("### 错误日志")
                errors = debug_logger.session_data.get("errors", [])
                if errors:
                    for i, error in enumerate(errors):
                        with st.expander(f"错误 {i+1}: {error.get('error_type', 'unknown')}", expanded=False):
                            st.text(f"时间: {error.get('timestamp', 'N/A')}")
                            st.text(f"类型: {error.get('error_type', 'N/A')}")
                            st.text(f"消息: {error.get('error_message', 'N/A')}")
                            
                            if error.get('context'):
                                st.text("上下文:")
                                st.json(error.get('context', {}))
                            
                            if error.get('stacktrace'):
                                st.text("堆栈跟踪:")
                                st.code(error.get('stacktrace', ''), language='python')
                else:
                    st.info("暂无错误记录")
            
            with tab5:
                st.markdown("### 会话信息")
                session_info = debug_logger.session_data.get("session_info", {})
                if session_info:
                    st.json(session_info)
                
                st.markdown("### 研究结果")
                research_results = debug_logger.session_data.get("research_results", [])
                if research_results:
                    for i, result in enumerate(research_results):
                        with st.expander(f"研究结果 {i+1}: {result.get('user_query', 'unknown')[:50]}...", expanded=False):
                            st.text(f"时间: {result.get('timestamp', 'N/A')}")
                            st.text(f"用户查询: {result.get('user_query', 'N/A')}")
                            st.text(f"答案长度: {result.get('final_answer_length', 0)}")
                            st.text(f"成功: {result.get('success', False)}")
                            
                            if result.get('metadata'):
                                st.text("元数据:")
                                st.json(result.get('metadata', {}))
                else:
                    st.info("暂无研究结果记录")
        else:
            st.info("Debug模式未启用或暂无数据")
        
        # 关闭按钮
        if st.button("❌ 关闭详细日志"):
            st.session_state.show_debug_details = False
            st.rerun()


def export_results():
    """导出研究结果"""
    if not st.session_state.research_results:
        st.sidebar.warning("没有可导出的研究结果。")
        return

    st.sidebar.subheader("📤 导出结果")

    # 默认导出最近一次的结果
    latest_result = st.session_state.research_results[-1]
    
    try:
        # 使用 json_serializable 处理枚举等特殊类型
        json_data = json.dumps(json_serializable(latest_result), indent=4, ensure_ascii=False)
        
        task_id = latest_result.get("task_id", "research_results")
        file_name = f"{task_id}.json"

        st.sidebar.download_button(
            label="📥 下载JSON格式结果",
            data=json_data,
            file_name=file_name,
            mime="application/json",
            help="将最近一次的研究结果导出为JSON文件"
        )

        markdown_content = create_markdown_content(latest_result)
        md_file_name = f"{task_id}.md"

        st.sidebar.download_button(
            label="📝 下载Markdown格式报告",
            data=markdown_content,
            file_name=md_file_name,
            mime="text/markdown",
            help="将最近一次的研究结果导出为Markdown文件"
        )
    except Exception as e:
        st.sidebar.error(f"导出失败: {e}")


def sidebar_content():
    """侧边栏内容"""
    st.sidebar.title("DeepSearch")

    # API密钥和模型配置
    if not setup_api_key():
        st.warning("⚠️ 请先配置有效的 Gemini API 密钥")
        st.markdown("""
        ### 如何获取 Gemini API 密钥:
        1. 访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
        2. 创建新的 API 密钥
        3. 将密钥输入到左侧配置栏中
        
        ### 配置文件方式:
        在项目根目录创建 `.streamlit/secrets.toml` 文件:
        ```toml
        [secrets]
        GEMINI_API_KEY = "your_api_key_here"
        ```
        """)
        return # 如果没有有效API密钥，则不显示侧边栏的其余部分

    st.sidebar.divider()
    
    # 会话统计
    st.sidebar.markdown("### 📊 会话统计")
    if st.session_state.research_engine:
        stats = st.session_state.research_engine.state_manager.get_session_statistics()
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("总任务数", stats.get("total_tasks", 0))
            st.metric("总搜索数", stats.get("total_searches", 0))
        with col2:
            st.metric("成功任务", stats.get("successful_tasks", 0))
            session_duration = stats.get("session_duration", 0)
            st.metric("会话时长", f"{session_duration/60:.1f}分钟")

    # 导出结果
    if st.session_state.research_results:
        st.sidebar.divider()
        export_results()

    st.sidebar.divider()

    # 清空会话按钮
    if st.sidebar.button("🗑️ 清空会话", disabled=st.session_state.is_researching):
        if st.session_state.research_engine:
            st.session_state.research_engine.clear_session()
        
        # 清除LocalStorage中的研究结果，但保留API key
        localS = SafeLocalStorage()
        localS.removeItem("research_results")

        # 重置所有状态
        keys_to_reset = [
            "research_results", "current_task", "progress_messages",
            "is_researching", "research_complete", "research_error",
            "current_step", "progress_percentage", "research_started",
            "just_completed", "show_markdown_preview", "history_loaded",
            "first_load_message_shown", "ls_research_results", "ls_api_key"
        ]
        for key in keys_to_reset:
            if key in st.session_state:
                if isinstance(st.session_state[key], list):
                    st.session_state[key] = []
                elif isinstance(st.session_state[key], bool):
                    st.session_state[key] = False
                else:
                    st.session_state[key] = None
        
        if "current_research_id" in st.session_state:
            del st.session_state.current_research_id
        
        st.sidebar.success("会话已清空")
        st.rerun()


def main():
    """主函数"""
    # 最重要：首先初始化会话状态
    initialize_session_state()
    
    # 延迟加载历史记录（确保LocalStorage已准备好）
    if "history_loaded" not in st.session_state:
        st.session_state.history_loaded = False
    
    if not st.session_state.history_loaded:
        try:
            localS = SafeLocalStorage()
            
            # 使用session state缓存LocalStorage的值，避免重复调用
            if "ls_research_results" not in st.session_state:
                initial_results = localS.getItem("research_results")
                st.session_state.ls_research_results = initial_results
                # 调试信息
                if st.session_state.get("debug_enabled", False):
                    st.info(f"🔍 从LocalStorage加载: {type(initial_results)} = {str(initial_results)[:100]}...")
            else:
                initial_results = st.session_state.ls_research_results
            
            # 只有当LocalStorage返回有效数据且当前没有历史记录时才加载
            if (initial_results and 
                initial_results != "null" and 
                initial_results != None and 
                str(initial_results).strip() != "" and
                len(st.session_state.research_results) == 0):
                
                try:
                    if isinstance(initial_results, str):
                        parsed_results = json.loads(initial_results)
                    else:
                        parsed_results = initial_results
                    
                    if isinstance(parsed_results, list) and len(parsed_results) > 0:
                        st.session_state.research_results = parsed_results
                        # 只在第一次加载时显示消息，避免每次刷新都显示
                        if "first_load_message_shown" not in st.session_state:
                            st.success(f"✅ 已加载 {len(parsed_results)} 条历史记录")
                            st.session_state.first_load_message_shown = True
                except (json.JSONDecodeError, TypeError) as e:
                    st.warning(f"⚠️ 历史记录格式错误，已清空: {e}")
                    localS.removeItem("research_results")
                    # 清除缓存
                    if "ls_research_results" in st.session_state:
                        del st.session_state.ls_research_results
            
            st.session_state.history_loaded = True
        except Exception as e:
            st.warning(f"⚠️ 加载历史记录时出错: {e}")
            st.session_state.history_loaded = True
    
    # 显示侧边栏
    sidebar_content()
    
    # 显示主界面
    research_interface()


if __name__ == "__main__":
    main() 