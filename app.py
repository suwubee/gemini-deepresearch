"""
DeepSearch - 智能深度研究助手
基于 Streamlit 的主应用程序，支持实时进度显示
"""

import streamlit as st
import asyncio
import json
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any
from enum import Enum

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
        "research_started": False,
        "just_completed": False,
        "debug_enabled": False,
        "show_markdown_preview": False
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # 尝试从LocalStorage加载数据
    try:
        localS = LocalStorage()
        
        # 加载API密钥
        initial_api_key = localS.getItem("api_key")
        if initial_api_key and initial_api_key.get("value"):
            st.session_state.api_key_to_load = initial_api_key["value"]

        # 加载研究历史记录
        initial_results = localS.getItem("research_results")
        if initial_results and initial_results.get("value"):
            try:
                loaded_results = initial_results["value"]
                if isinstance(loaded_results, list) and loaded_results:
                    st.session_state.research_results = loaded_results
                    if st.session_state.get("debug_enabled", False):
                        st.success(f"✅ 已加载 {len(loaded_results)} 条研究历史记录")
            except Exception as e:
                if st.session_state.get("debug_enabled", False):
                    st.error(f"解析LocalStorage研究历史数据失败: {e}")
                st.session_state.research_results = []
            
    except Exception as e:
        if st.session_state.get("debug_enabled", False):
            st.error(f"从LocalStorage加载数据失败: {e}")
        if "research_results" not in st.session_state:
            st.session_state.research_results = []


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
    api_key_from_storage = st.session_state.get("api_key_to_load", "")

    # 如果没有从secrets获取到，让用户输入
    api_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password",
        value=api_key_from_storage,
        help="请输入您的 Google Gemini API 密钥"
    )
    
    if api_key:
        if validate_and_setup_engine(api_key, model_name):
            st.session_state.api_key_validated = True
            st.sidebar.success("✅ API密钥配置成功")
            
            # 如果是新的有效key，则保存到localStorage
            if api_key != api_key_from_storage:
                try:
                    localS.setItem("api_key", api_key)
                    st.session_state.api_key_to_load = api_key
                    st.sidebar.info("🔐 API密钥已保存到浏览器")
                except Exception as e:
                    st.sidebar.warning(f"保存API密钥失败: {e}")
            
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
                    
                    summary = debug_logger.get_session_summary()
                    if summary:
                        with st.sidebar.expander("📊 Debug统计", expanded=False):
                            st.metric("API请求", summary.get("total_api_requests", 0))
                            st.metric("搜索次数", summary.get("total_searches", 0))
                            st.metric("错误数量", summary.get("total_errors", 0))
                    
                    if st.sidebar.button("💾 保存Debug日志"):
                        debug_logger.save_now()
                        st.sidebar.success("✅ Debug日志已保存")
        else:
            st.session_state.api_key_validated = False
            st.sidebar.error("❌ API密钥验证失败")
    else:
        st.session_state.api_key_validated = False
    
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


def research_interface():
    """研究主界面"""
    st.title("🔍 DeepSearch - 智能深度研究助手")
    st.markdown("### 智能深度研究助手")
    
    # 初始化线程池执行器
    if "executor" not in st.session_state:
        st.session_state.executor = ThreadPoolExecutor(max_workers=1)

    # 显示实时进度
    display_real_time_progress()

    # 研究输入区域
    with st.form("research_form"):
        user_query = st.text_area(
            "请输入您想要深度研究的问题:",
            height=100,
            placeholder="例如：分析人工智能在医疗领域的最新应用和发展趋势",
            disabled=st.session_state.is_researching
        )
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            max_search_rounds = st.slider(
                "搜索强度",
                min_value=1,
                max_value=10,
                value=3,
                help="控制搜索的深度和广度，数值越高结果越详细但耗时更长",
                disabled=st.session_state.is_researching
            )
        
        with col2:
            effort_level = st.selectbox(
                "研究强度",
                options=["low", "medium", "high"],
                index=1,
                format_func=lambda x: {"low": "🟢 轻度 (快速)", "medium": "🟡 中度 (平衡)", "high": "🔴 深度 (详细)"}[x],
                help="选择研究的详细程度",
                disabled=st.session_state.is_researching
            )
        
        # 按钮区域 - 使用更好的布局
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        
        with col_btn2:  # 居中放置按钮
            if not st.session_state.is_researching:
                # 检查是否有API密钥和用户输入
                button_disabled = not st.session_state.get("api_key_validated", False) or not user_query.strip()
                submitted = st.form_submit_button(
                    "🚀 开始研究",
                    disabled=button_disabled,
                    use_container_width=True,
                    type="primary"
                )
                
                # 显示提示信息
                if not st.session_state.get("api_key_validated", False):
                    st.error("⚠️ 请先在左侧配置API密钥")
                elif not user_query.strip():
                    st.info("💡 请输入研究问题")
            else:
                # 停止按钮
                if st.form_submit_button("⏹️ 停止研究", use_container_width=True, type="secondary"):
                    if "stop_event" in st.session_state and st.session_state.stop_event:
                        st.session_state.stop_event.set()
                        st.session_state.is_researching = False
                        st.info("正在停止研究...")
                        st.rerun()

    # 处理研究请求
    if 'submitted' in locals() and submitted and user_query.strip():
        if not st.session_state.research_engine:
            st.error("❌ 请先配置有效的API密钥")
        else:
            # 重置状态
            st.session_state.is_researching = True
            st.session_state.research_complete = False
            st.session_state.research_error = None
            st.session_state.progress_messages = []
            st.session_state.current_step = ""
            st.session_state.progress_percentage = 0
            st.session_state.research_started = True
            st.session_state.just_completed = False

            # 创建停止事件
            st.session_state.stop_event = threading.Event()

            # 创建队列用于线程间通信
            q = queue.Queue()
            st.session_state.result_queue = q

            # 在后台线程中启动研究
            future = st.session_state.executor.submit(
                run_research_in_background,
                st.session_state.research_engine,
                user_query,
                max_search_rounds,
                effort_level,
                q,
                st.session_state.stop_event
            )
            st.session_state.current_task_future = future

            st.rerun()

    # 处理后台任务结果
    if st.session_state.is_researching and "result_queue" in st.session_state:
        q = st.session_state.result_queue
        
        try:
            # 非阻塞地检查队列，处理所有可用的消息
            while not q.empty():
                item = q.get_nowait()
                
                if item["type"] == "progress":
                    st.session_state.progress_messages.append(item["message"])
                    st.session_state.progress_percentage = item["percentage"]
                elif item["type"] == "step":
                    st.session_state.current_step = item["message"]
                elif item["type"] == "result":
                    # 研究完成
                    st.session_state.is_researching = False
                    st.session_state.research_complete = True
                    st.session_state.current_task = item["data"]
                    st.session_state.research_results.append(item["data"])
                    st.session_state.just_completed = True
                    
                    # 保存到LocalStorage
                    try:
                        localS = LocalStorage()
                        serializable_results = json_serializable(st.session_state.research_results)
                        localS.setItem("research_results", serializable_results)
                        if st.session_state.get("debug_enabled", False):
                            task_id = item["data"].get("task_id", "未知")
                            st.write(f"🐛 调试信息 - task_id: '{task_id}', 长度: {len(str(task_id))}")
                            st.write(f"🐛 保存到LocalStorage成功，共{len(st.session_state.research_results)}条记录")
                    except Exception as e:
                        st.error(f"保存到LocalStorage失败: {e}")

                elif item["type"] == "error":
                    st.session_state.is_researching = False
                    st.session_state.research_error = item["message"]
                elif item["type"] == "info":
                    st.session_state.is_researching = False
                    st.info(item["message"])

            # 如果仍在研究中，安排下一次刷新
            if st.session_state.is_researching:
                time.sleep(0.1)
                st.rerun()
            elif st.session_state.just_completed:
                # 研究刚刚结束，刷新一次以显示最终结果
                st.rerun()
                
        except queue.Empty:
            # 队列为空，检查后台任务是否仍在运行
            if st.session_state.is_researching:
                future = st.session_state.get("current_task_future")
                if future and future.done():
                    # 任务已结束，但队列中没有消息，说明可能发生意外
                    try:
                        future.result() 
                        st.session_state.research_error = "研究意外终止，但未报告明确错误。"
                    except Exception as e:
                        st.session_state.research_error = f"研究任务在后台发生错误: {e}"
                    
                    st.session_state.is_researching = False
                    st.rerun()
                else:
                    # 任务仍在运行，队列为空是正常的，继续轮询
                    time.sleep(0.1)
                    st.rerun()

    # 显示历史研究结果
    if st.session_state.research_results:
        # 如果是刚刚完成，显示一个成功的提示
        if st.session_state.just_completed:
            st.success("🎉 研究完成！")
            st.session_state.just_completed = False

        st.markdown("---")
        st.subheader("📜 研究历史记录")
        for i, result in enumerate(reversed(st.session_state.research_results)):
            task_id = result.get("task_id", f"history_{i}")
            
            # 只在debug模式下显示调试信息
            if st.session_state.get("debug_enabled", False):
                st.write(f"🐛 历史记录 {i} - task_id: '{task_id}', 长度: {len(str(task_id))}")
            
            with st.expander(f"**{result.get('user_query', '未知查询')}** - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({task_id[:8]})", expanded=(i==0)):
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
        return

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
        try:
            localS = LocalStorage()
            localS.removeItem("research_results")
            st.sidebar.info("🗑️ 浏览器缓存已清除")
        except Exception as e:
            st.sidebar.warning(f"清除浏览器缓存失败: {e}")

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
        
        st.sidebar.success("✅ 会话已清空")
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