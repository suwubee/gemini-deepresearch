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

# 导入核心组件
from core.research_engine import ResearchEngine
from core.state_manager import TaskStatus
from utils.debug_logger import enable_debug, disable_debug, get_debug_logger

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


def json_serializable(obj):
    """将对象转换为JSON可序列化的格式"""
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        return {k: json_serializable(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, (list, tuple)):
        return [json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: json_serializable(v) for k, v in obj.items()}
    else:
        return obj


def create_markdown_content(research_results):
    """创建markdown格式的研究内容"""
    if not research_results or not research_results.get("success"):
        return "# 研究结果\n\n没有可用的研究结果。"
    
    user_query = research_results.get("user_query", "未知查询")
    final_answer = research_results.get("final_answer", "")
    
    # 构建markdown内容
    markdown_content = f"""# 🔍 研究报告

## 📋 研究主题
{user_query}

## 🎯 研究结果
{final_answer}

---

"""
    
    # 添加引用来源
    citations = research_results.get("citations", [])
    if citations:
        markdown_content += "## 📚 引用来源\n\n"
        for i, citation in enumerate(citations[:10], 1):
            title = citation.get("title", f"来源 {i}")
            url = citation.get("url", "#")
            markdown_content += f"{i}. [{title}]({url})\n"
        markdown_content += "\n"
    
    # 添加搜索统计
    search_results = research_results.get("search_results", [])
    if search_results:
        markdown_content += f"## 📊 研究统计\n\n"
        markdown_content += f"- 搜索次数：{len(search_results)}\n"
        successful_searches = len([r for r in search_results if r.success])
        markdown_content += f"- 成功搜索：{successful_searches}\n"
        total_citations = sum(len(r.citations) for r in search_results)
        markdown_content += f"- 总引用数：{total_citations}\n\n"
    
    # 添加任务摘要
    task_summary = research_results.get("task_summary", {})
    if task_summary:
        markdown_content += "## ⚙️ 任务信息\n\n"
        if "task_id" in task_summary:
            markdown_content += f"- 任务ID：{task_summary['task_id']}\n"
        if "duration" in task_summary:
            duration = task_summary["duration"]
            markdown_content += f"- 执行时长：{duration:.1f}秒\n"
        if "status" in task_summary:
            status = task_summary["status"]
            if isinstance(status, Enum):
                status = status.value
            markdown_content += f"- 执行状态：{status}\n"
    
    # 添加生成时间
    markdown_content += f"\n---\n\n*报告生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}*\n"
    markdown_content += "*由 🔍 DeepSearch 智能研究助手生成*"
    
    return markdown_content


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
    
    # 模型选择
    model_name = st.sidebar.selectbox(
        "选择模型",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
        format_func=lambda x: AVAILABLE_MODELS[x],
        help="选择要使用的Gemini模型版本"
    )
    
    # 尝试从secrets获取API密钥
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except:
        pass
    
    # 如果没有从secrets获取到，让用户输入
    if not api_key:
        api_key = st.sidebar.text_input(
            "Gemini API Key",
            type="password",
            help="请输入您的 Google Gemini API 密钥"
        )
    else:
        st.sidebar.success("✅ 已从配置文件加载API密钥")
        masked_key = api_key[:8] + "*" * max(0, len(api_key) - 12) + api_key[-4:] if len(api_key) > 12 else api_key
        st.sidebar.text(f"当前密钥: {masked_key}")
    
    if api_key:
        if validate_and_setup_engine(api_key, model_name):
            st.session_state.api_key_validated = True
            st.sidebar.success("✅ API密钥验证成功")
            st.sidebar.info(f"🤖 用户选择模型: {AVAILABLE_MODELS[model_name]}")
            
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


def run_research_sync(user_query: str, max_search_rounds: int, effort_level: str, 
                      progress_callback=None, step_callback=None):
    """同步方式运行研究"""
    try:
        # 检查研究引擎
        if not st.session_state.research_engine:
            return {"success": False, "error": "研究引擎未初始化"}
        
        # 如果没有提供回调函数，使用默认的
        if not progress_callback:
            def progress_callback(message, percentage):
                # 检查停止标记
                if st.session_state.get("stop_research", False):
                    # 通知研究引擎停止
                    if st.session_state.research_engine:
                        st.session_state.research_engine.stop_research()
                    raise Exception("用户停止了研究")
                    
                msg = f"[{percentage:.1f}%] {message}"
                st.session_state.progress_messages.append(msg)
                st.session_state.progress_percentage = percentage
                print(msg)
        
        if not step_callback:
            def step_callback(message):
                # 检查停止标记
                if st.session_state.get("stop_research", False):
                    # 通知研究引擎停止
                    if st.session_state.research_engine:
                        st.session_state.research_engine.stop_research()
                    raise Exception("用户停止了研究")
                    
                msg = f"⚡ {message}"
                st.session_state.progress_messages.append(msg)
                st.session_state.current_step = message
                print(msg)
        
        engine = st.session_state.research_engine
        engine.set_progress_callback(progress_callback)
        engine.set_step_callback(step_callback)
        
        # 开始研究
        progress_callback("开始研究任务", 5)
        
        # 使用带超时的异步执行，避免Streamlit超时
        try:
            # 设置较长的超时时间，适应高token输出
            timeout_seconds = 600  # 10分钟超时，适应大型研究任务
            
            # 创建新的事件循环，避免与Streamlit冲突
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                research_results = loop.run_until_complete(
                    asyncio.wait_for(
                        engine.research(
                            user_query,
                            max_search_rounds=max_search_rounds,
                            effort_level=effort_level
                        ),
                        timeout=timeout_seconds
                    )
                )
                return research_results
                
            finally:
                loop.close()
                
        except asyncio.TimeoutError:
            error_msg = f"研究任务超时（{timeout_seconds}秒），请尝试缩小研究范围或降低复杂度"
            print(f"Timeout Error: {error_msg}")
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            # 其他异常的fallback处理
            try:
                # 最后的fallback：简单同步方式
                research_results = asyncio.run(
                    engine.research(
                        user_query,
                        max_search_rounds=max_search_rounds,
                        effort_level=effort_level
                    )
                )
                return research_results
            except Exception as e2:
                raise e2
        
    except Exception as e:
        error_msg = f"研究过程中发生错误: {str(e)}"
        print(f"Error: {error_msg}")
        return {"success": False, "error": error_msg}


def display_task_analysis(workflow_analysis):
    """显示任务分析结果"""
    if not workflow_analysis:
        return
    
    with st.expander("📊 任务分析结果", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("任务类型", workflow_analysis.task_type)
            st.metric("复杂度", workflow_analysis.complexity)
            st.metric("预估步骤", workflow_analysis.estimated_steps)
        
        with col2:
            st.metric("需要搜索", "是" if workflow_analysis.requires_search else "否")
            st.metric("多轮搜索", "是" if workflow_analysis.requires_multiple_rounds else "否")
            st.metric("预估时间", workflow_analysis.estimated_time)
        
        if workflow_analysis.reasoning:
            st.text_area("分析推理", workflow_analysis.reasoning, height=100, disabled=True)


def display_search_results(research_results):
    """显示搜索结果"""
    if not research_results or not research_results.get("search_results"):
        return
    
    search_results = research_results["search_results"]
    
    with st.expander(f"🔍 搜索结果 ({len(search_results)})", expanded=False):
        for i, result in enumerate(search_results, 1):
            with st.container():
                st.markdown(f"**搜索 {i}: {result.query}**")
                
                if result.success:
                    st.success(f"✅ 搜索成功 (耗时: {result.duration:.2f}秒)")
                    
                    if result.content:
                        content_preview = result.content[:200] + "..." if len(result.content) > 200 else result.content
                        st.text_area(f"内容预览", content_preview, height=100, disabled=True, key=f"content_{i}")
                    
                    if result.citations:
                        st.markdown("**引用来源:**")
                        citations_list = result.citations or []
                        for j, citation in enumerate(citations_list[:3]):
                            title = citation.get("title", "未知标题")
                            url = citation.get("url", "#")
                            st.markdown(f"- [{title}]({url})")
                else:
                    st.error(f"❌ 搜索失败: {result.error}")
                
                st.divider()


def display_final_answer(research_results):
    """显示最终答案"""
    final_answer = research_results.get("final_answer", "")
    
    if final_answer:
        # 添加标题和操作按钮行
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown("### 🎯 研究结果")
        
        with col2:
            # 复制markdown按钮
            if st.button("📋 复制Markdown", help="复制研究结果的markdown格式到剪贴板"):
                try:
                    markdown_content = create_markdown_content(research_results)
                    # 使用streamlit的内置功能来复制到剪贴板
                    st.code(markdown_content, language="markdown")
                    st.success("✅ Markdown内容已生成，请手动复制上方代码块中的内容")
                except Exception as e:
                    st.error(f"❌ 生成Markdown失败: {str(e)}")
        
        with col3:
            # 查看markdown预览按钮
            if st.button("👁️ 预览Markdown", help="查看完整的markdown格式预览"):
                st.session_state.show_markdown_preview = not st.session_state.get("show_markdown_preview", False)
        
        # 显示markdown预览（如果启用）
        if st.session_state.get("show_markdown_preview", False):
            with st.expander("📄 Markdown预览", expanded=True):
                try:
                    markdown_content = create_markdown_content(research_results)
                    st.markdown("**生成的Markdown内容：**")
                    st.code(markdown_content, language="markdown")
                    st.markdown("**渲染效果预览：**")
                    st.markdown(markdown_content)
                except Exception as e:
                    st.error(f"❌ 预览失败: {str(e)}")
        
        # 显示主要研究结果
        st.markdown(final_answer)
        
        # 从StateManager获取引用和来源
        if st.session_state.research_engine:
            citations = st.session_state.research_engine.state_manager.get_all_citations()
            urls = st.session_state.research_engine.state_manager.get_unique_urls()
            analysis_process = st.session_state.research_engine.state_manager.get_analysis_process()
        else:
            citations = []
            urls = []
            analysis_process = {}
        
        # 显示分析过程（参考原始backend结构）
        if analysis_process:
            with st.expander("🔬 分析过程", expanded=False):
                # 使用tabs来避免嵌套expander问题
                tab1, tab2, tab3, tab4 = st.tabs(["搜索查询", "搜索结果", "分析反思", "统计信息"])
                
                with tab1:
                    # 显示搜索查询
                    search_queries = analysis_process.get("search_queries", [])
                    if search_queries:
                        st.markdown("**搜索查询:**")
                        for i, query in enumerate(search_queries, 1):
                            st.markdown(f"{i}. {query}")
                    else:
                        st.info("暂无搜索查询记录")
                
                with tab2:
                    # 显示网络搜索结果
                    web_research_results = analysis_process.get("web_research_results", [])
                    if web_research_results:
                        st.markdown("**网络搜索结果:**")
                        for i, result in enumerate(web_research_results, 1):
                            st.markdown(f"**搜索结果 {i}:**")
                            # 使用代码块显示而不是嵌套expander
                            st.code(result, language=None)
                            st.divider()
                    else:
                        st.info("暂无搜索结果记录")
                
                with tab3:
                    # 显示反思分析
                    reflection_results = analysis_process.get("reflection_results", [])
                    if reflection_results:
                        st.markdown("**分析反思:**")
                        for i, reflection in enumerate(reflection_results, 1):
                            st.markdown(f"**分析 {i}:**")
                            st.json(reflection)
                            st.divider()
                    else:
                        st.info("暂无分析反思记录")
                
                with tab4:
                    # 显示统计信息
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("搜索结果数", analysis_process.get("search_results_count", 0))
                    with col2:
                        st.metric("成功搜索数", analysis_process.get("successful_searches", 0))
        
        # 引用和来源
        if citations or urls:
            with st.expander("📚 引用和来源", expanded=False):
                if citations:
                    st.markdown("**引用来源:**")
                    for i, citation in enumerate(citations, 1):
                        title = citation.get("title", f"来源 {i}")
                        url = citation.get("url", "#")
                        # 不再显示"Source from"，直接显示网页标题
                        
                        # 修复：如果URL是redirect链接，尝试映射到实际域名
                        if "vertexaisearch.cloud.google.com" in url:
                            # 根据标题尝试推导原始URL
                            if title and title != f"来源 {i}":
                                clean_title = title.split('.')[0].lower()
                                domain_map = {
                                    'bondcap': 'bondcap.com',
                                    'zdnet': 'zdnet.com',
                                    'techcrunch': 'techcrunch.com',
                                    'reuters': 'reuters.com',
                                    'bloomberg': 'bloomberg.com',
                                    'cnbc': 'cnbc.com',
                                    'forbes': 'forbes.com',
                                    'marketwatch': 'marketwatch.com'
                                }
                                for key, domain in domain_map.items():
                                    if key in clean_title:
                                        url = f"https://{domain}"
                                        break
                        
                        st.markdown(f"**{i}. [{title}]({url})**")
                        st.divider()
                
                if urls:
                    st.markdown("**相关链接:**")
                    urls_list = urls or []
                    for url in urls_list[:10]:
                        st.markdown(f"- {url}")


def research_interface():
    """研究界面"""
    st.markdown('<h1 class="main-header">🔍 DeepSearch</h1>', unsafe_allow_html=True)
    st.markdown("### 智能深度研究助手")
    
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
        # 根据effort级别自动设置max_search_rounds（参考原始frontend规格）
        effort_to_rounds = {"low": 1, "medium": 3, "high": 10}
        effort_to_queries = {"low": 1, "medium": 3, "high": 5}
        
        max_search_rounds = effort_to_rounds[effort_level]
        initial_queries = effort_to_queries[effort_level]
        
        st.info(f"📊 自动配置: {initial_queries}个初始查询, 最多{max_search_rounds}轮搜索")
        
        # 显示高级设置的折叠选项
        with st.expander("⚙️ 高级设置", expanded=False):
            custom_rounds = st.slider(
                "自定义最大搜索轮数",
                min_value=1,
                max_value=15,
                value=max_search_rounds,
                help="覆盖默认的搜索轮数设置",
                disabled=st.session_state.is_researching
            )
            
            if custom_rounds != max_search_rounds:
                max_search_rounds = custom_rounds
                st.warning(f"⚠️ 已覆盖默认设置，使用 {custom_rounds} 轮搜索")
    
    # 开始/停止研究按钮
    if not st.session_state.is_researching:
        if st.button("🚀 开始研究", type="primary", disabled=not user_query.strip()):
            if not st.session_state.research_engine:
                st.error("研究引擎未初始化，请检查API密钥配置")
                return
            
            # 严格检查：避免重复启动
            if st.session_state.get("research_started", False):
                st.warning("⚠️ 研究任务已经在进行中，请勿重复点击")
                return
            
            if st.session_state.get("is_researching", False):
                st.warning("⚠️ 研究正在进行中，请等待完成或点击停止")
                return
            
            # 检查是否刚刚完成研究，防止意外重启
            if st.session_state.get("just_completed", False):
                st.info("✅ 上次研究已完成，如需新研究请再次点击")
                st.session_state.just_completed = False
                return
            
            # 开始研究
            st.session_state.is_researching = True
            st.session_state.progress_messages = []
            st.session_state.current_step = "初始化研究..."
            st.session_state.progress_percentage = 0
            st.session_state.research_complete = False
            st.session_state.research_error = None
            
            # 重置停止标记
            st.session_state.stop_research = False
            
            # 添加执行标记，避免重复执行
            st.session_state.research_started = True
            
            # 添加唯一任务ID，防止重复
            import uuid
            st.session_state.current_research_id = str(uuid.uuid4())
            
            print(f"🚀 启动新研究任务: {st.session_state.current_research_id}")
            
            # 不要调用 st.rerun()，避免重复触发按钮
            # st.rerun()
    else:
        if st.button("⏹️ 停止研究", type="secondary"):
            print("🛑 用户点击停止研究按钮")
            
            # 设置停止标记
            st.session_state.stop_research = True
            st.session_state.is_researching = False
            st.session_state.current_step = ""
            st.session_state.progress_percentage = 0
            st.session_state.research_started = False
            
            # 清理研究相关状态
            if "current_research_id" in st.session_state:
                del st.session_state.current_research_id
            
            # 停止时可以安全地使用 st.rerun()，因为停止后不会重新触发
            st.rerun()
    
    # 执行研究（如果正在研究中且尚未开始执行）
    if (st.session_state.is_researching and 
        not st.session_state.research_complete and 
        st.session_state.get("research_started", False) and
        not st.session_state.get("just_completed", False)):  # 确保没有刚刚完成
        
        # 检查是否被用户停止
        if not st.session_state.is_researching:
            st.info("🛑 研究已被用户停止")
            return
        
        # 检查是否有有效的研究ID（防止重复执行）
        if not st.session_state.get("current_research_id"):
            st.warning("⚠️ 无效的研究会话，请重新开始")
            st.session_state.is_researching = False
            st.session_state.research_started = False
            return
        
        print(f"🔄 执行研究任务: {st.session_state.current_research_id}")
        
        st.info("🔄 正在进行深度研究，请稍候...")
        
        # 创建进度显示容器
        progress_container = st.container()
        step_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            current_step_text = st.empty()
        
        with step_container:
            messages_container = st.empty()
        
        # 直接同步执行研究
        try:
            # 添加一个状态消息
            st.session_state.progress_messages.append("⚡ 正在初始化研究引擎...")
            
            # 更新进度显示回调
            def progress_callback(message, percentage):
                # 检查停止标记
                if st.session_state.get("stop_research", False):
                    # 通知研究引擎停止
                    if st.session_state.research_engine:
                        st.session_state.research_engine.stop_research()
                    raise Exception("用户停止了研究")
                    
                msg = f"[{percentage:.1f}%] {message}"
                st.session_state.progress_messages.append(msg)
                st.session_state.progress_percentage = percentage
                print(msg)
                
                # 实时更新进度条
                progress_bar.progress(percentage / 100)
                current_step_text.info(f"📝 {message}")
                
                # 更新消息列表
                with messages_container:
                    with st.expander("📝 详细进度", expanded=True):
                        for i, msg in enumerate(st.session_state.progress_messages[-10:], 1):
                            st.text(f"{i}. {msg}")
            
            def step_callback(message):
                # 检查停止标记
                if st.session_state.get("stop_research", False):
                    # 通知研究引擎停止
                    if st.session_state.research_engine:
                        st.session_state.research_engine.stop_research()
                    raise Exception("用户停止了研究")
                    
                msg = f"⚡ {message}"
                st.session_state.progress_messages.append(msg)
                st.session_state.current_step = message
                print(msg)
                
                current_step_text.info(f"🔄 {message}")
            
            # 直接调用研究函数
            research_results = run_research_sync(user_query, max_search_rounds, effort_level, 
                                               progress_callback, step_callback)
            
            # 研究完成
            st.session_state.is_researching = False
            st.session_state.research_complete = True
            st.session_state.research_started = False  # 重置执行标记
            
            if research_results.get("success"):
                st.session_state.current_task = research_results
                st.session_state.research_results.append(research_results)
                progress_bar.progress(1.0)
                current_step_text.success("🎉 研究完成！")
                
                # 设置完成标记，防止重新启动
                st.session_state.just_completed = True
                
                # 不要调用 st.rerun()，避免意外重新触发研究
                print(f"✅ 研究任务完成: {st.session_state.get('current_research_id', 'unknown')}")
            else:
                st.session_state.research_error = research_results.get('error', '未知错误')
                current_step_text.error(f"研究失败: {st.session_state.research_error}")
                
        except Exception as e:
            st.session_state.is_researching = False
            st.session_state.research_started = False  # 重置执行标记
            
            error_msg = str(e)
            if "用户停止了研究" in error_msg:
                current_step_text.warning("🛑 研究已被用户停止")
                st.session_state.research_error = None
            else:
                st.session_state.research_error = error_msg
                current_step_text.error(f"执行研究时发生错误: {error_msg}")
                import traceback
                st.text(traceback.format_exc())
    
    # 显示结果
    if st.session_state.current_task and st.session_state.current_task.get("success"):
        display_task_analysis(st.session_state.current_task.get("workflow_analysis"))
        display_final_answer(st.session_state.current_task)
        display_search_results(st.session_state.current_task)


def sidebar_content():
    """侧边栏内容"""
    st.sidebar.markdown("### 📊 会话统计")
    
    if st.session_state.research_engine:
        stats = st.session_state.research_engine.state_manager.get_session_statistics()
        
        st.sidebar.metric("总任务数", stats.get("total_tasks", 0))
        st.sidebar.metric("成功任务", stats.get("successful_tasks", 0))
        st.sidebar.metric("总搜索次数", stats.get("total_searches", 0))
        
        session_duration = stats.get("session_duration", 0)
        st.sidebar.metric("会话时长", f"{session_duration/60:.1f}分钟")
    
    # 历史研究结果
    if st.session_state.research_results:
        st.sidebar.markdown("### 📚 历史结果")
        
        for i, result in enumerate(reversed(st.session_state.research_results[-5:]), 1):
            with st.sidebar.expander(f"研究 {len(st.session_state.research_results) - i + 1}"):
                query = result.get("user_query", "")
                query_preview = query[:50] + "..." if len(query) > 50 else query
                st.text(query_preview)
                
                if result.get("success"):
                    st.success("✅ 成功")
                else:
                    st.error("❌ 失败")
    
    # 清空会话按钮
    if st.sidebar.button("🗑️ 清空会话", disabled=st.session_state.is_researching):
        if st.session_state.research_engine:
            st.session_state.research_engine.clear_session()
        
        # 重置所有状态
        for key in ["research_results", "current_task", "progress_messages"]:
            if key in st.session_state:
                if isinstance(st.session_state[key], list):
                    st.session_state[key] = []
                else:
                    st.session_state[key] = None
        
        st.session_state.is_researching = False
        st.session_state.research_complete = False
        st.session_state.research_error = None
        st.session_state.current_step = ""
        st.session_state.progress_percentage = 0
        st.session_state.research_started = False
        st.session_state.just_completed = False
        st.session_state.show_markdown_preview = False
        if "current_research_id" in st.session_state:
            del st.session_state.current_research_id
        
        st.sidebar.success("会话已清空")


def export_results():
    """导出结果功能"""
    if st.session_state.current_task and st.session_state.current_task.get("success"):
        st.sidebar.markdown("### 📤 导出结果")
        
        if st.sidebar.button("导出JSON"):
            try:
                export_data = st.session_state.research_engine.export_results()
                # 使用自定义序列化函数处理枚举类型
                serializable_data = json_serializable(export_data)
                json_string = json.dumps(serializable_data, ensure_ascii=False, indent=2)
                
                st.sidebar.download_button(
                    label="下载研究结果",
                    data=json_string,
                    file_name=f"research_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                st.sidebar.success("✅ JSON导出准备完成")
            except Exception as e:
                st.sidebar.error(f"❌ 导出失败: {str(e)}")
        
        # 添加Markdown导出功能
        if st.sidebar.button("导出Markdown"):
            try:
                markdown_content = create_markdown_content(st.session_state.current_task)
                
                st.sidebar.download_button(
                    label="下载Markdown报告",
                    data=markdown_content,
                    file_name=f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
                st.sidebar.success("✅ Markdown导出准备完成")
            except Exception as e:
                st.sidebar.error(f"❌ Markdown导出失败: {str(e)}")


def main():
    """主函数"""
    # 最重要：首先初始化会话状态
    initialize_session_state()
    
    # 设置API密钥
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
    
    # 显示主界面
    research_interface()
    
    # 显示侧边栏内容
    sidebar_content()
    
    # 导出功能
    export_results()


if __name__ == "__main__":
    main() 