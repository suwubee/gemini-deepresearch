"""
DeepSearch - 智能深度研究助手
基于 Streamlit 的主应用程序，支持实时进度显示
"""

import streamlit as st
import asyncio
import json
import time
import threading
import concurrent.futures
from datetime import datetime
from typing import Dict, Any
from enum import Enum
import queue

from streamlit_local_storage import LocalStorage

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

    # 尝试从LocalStorage加载数据
    localS = LocalStorage()
    initial_api_key = localS.getItem("api_key")
    if initial_api_key:
        st.session_state.api_key_to_load = initial_api_key

    initial_results = localS.getItem("research_results")
    if initial_results:
        st.session_state.research_results = initial_results


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
    
    localS = LocalStorage()
    
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
            
            # 如果是新的有效key，则保存到localStorage
            if api_key != api_key_from_storage:
                localS.setItem("api_key", api_key)
                st.session_state.api_key_to_load = api_key # 更新state
            
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
                            st.metric("API请求", summary.get("total_api_requests", 0))
                            st.metric("搜索次数", summary.get("total_searches", 0))
                            st.metric("错误数量", summary.get("total_errors", 0))
                    
                    # 立即保存按钮
                    if st.sidebar.button("💾 保存Debug日志"):
                        debug_logger.save_now()
                        st.sidebar.success("✅ Debug日志已保存")
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
    engine, user_query, max_search_rounds, effort_level, q, stop_event
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
            engine.research(user_query, max_search_rounds, effort_level)
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
            help="低强度: 1查询1轮次, 中强度: 3查询3轮次, 高强度: 5查询10轮次",
            disabled=st.session_state.is_researching
        )
    
    with col2:
        effort_to_rounds = {"low": 1, "medium": 3, "high": 10}
        effort_to_queries = {"low": 1, "medium": 3, "high": 5}
        max_search_rounds = effort_to_rounds[effort_level]
        initial_queries = effort_to_queries[effort_level]
        st.info(f"📊 自动配置: {initial_queries}个初始查询, 最多{max_search_rounds}轮搜索")
        
        with st.expander("⚙️ 高级设置", expanded=False):
            max_search_rounds = st.slider(
                "自定义最大搜索轮数", 1, 15, max_search_rounds,
                help="覆盖默认的搜索轮数设置",
                disabled=st.session_state.is_researching
            )
    
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
                        localS = LocalStorage()
                        serializable_results = json_serializable(st.session_state.research_results)
                        localS.setItem("research_results", serializable_results)

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

    # 显示最近一次完成的研究结果
    if st.session_state.research_complete and not st.session_state.is_researching:
        if st.session_state.current_task:
            result = st.session_state.current_task
            if result.get("success"):
                st.success("🎉 研究完成！")
                display_final_answer(result)
                display_search_results(result)
                display_task_analysis(result.get("workflow_analysis"), result.get("task_id"))
            else:
                st.error(f"研究失败: {result.get('error', '未知错误')}")
        
    # 显示历史研究结果
    if st.session_state.research_results:
        st.markdown("---")
        st.subheader("📜 研究历史记录")
        for i, result in enumerate(reversed(st.session_state.research_results)):
            task_id = result.get("task_id", f"history_{i}")
            with st.expander(f"**{result.get('user_query', '未知查询')}** - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({task_id[:20]})", expanded=(i==0)):
                if result.get("success"):
                    display_final_answer(result)
                    display_search_results(result)
                    display_task_analysis(result.get("workflow_analysis"), result.get("task_id"))
                else:
                    st.error(f"研究失败: {result.get('error', '未知错误')}")

    # 如果有错误，显示错误信息
    if st.session_state.research_error and not st.session_state.is_researching:
        st.error(f"❌ 研究失败: {st.session_state.research_error}")


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
        
        # 清除LocalStorage
        localS = LocalStorage()
        localS.removeItem("api_key")
        localS.removeItem("research_results")

        # 重置所有状态
        keys_to_reset = [
            "research_results", "current_task", "progress_messages",
            "is_researching", "research_complete", "research_error",
            "current_step", "progress_percentage", "research_started",
            "just_completed", "show_markdown_preview"
        ]
        for key in keys_to_reset:
            if key in st.session_state:
                if isinstance(st.session_state[key], list):
                    st.session_state[key] = []
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
    
    # 显示侧边栏
    sidebar_content()
    
    # 显示主界面
    research_interface()


if __name__ == "__main__":
    main() 