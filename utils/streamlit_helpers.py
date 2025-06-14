"""
Streamlit 相关的辅助函数
"""

import streamlit as st
from datetime import datetime
from enum import Enum

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
        successful_searches = len([r for r in search_results if r.get('success')])
        markdown_content += f"- 成功搜索：{successful_searches}\n"
        total_citations = sum(len(r.get('citations', [])) for r in search_results)
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


def display_task_analysis(workflow_analysis, task_id):
    """显示任务分析结果"""
    if not workflow_analysis:
        return
    
    with st.expander(f"📊 任务分析结果 ({task_id[:8]})", expanded=False):
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
            st.text_area("分析推理", workflow_analysis.reasoning, height=100, disabled=True, key=f"reasoning_{task_id}")


def display_search_results(research_results):
    """显示搜索结果"""
    if not research_results or not research_results.get("search_results"):
        return
    
    search_results = research_results["search_results"]
    task_id = research_results.get("task_id", "default")
    
    with st.expander(f"🔍 搜索结果 ({len(search_results)}) ({task_id[:8]})", expanded=False):
        for i, result in enumerate(search_results, 1):
            with st.container():
                st.markdown(f"**搜索 {i}: {result.query}**")
                
                if result.success:
                    st.success(f"✅ 搜索成功 (耗时: {result.duration:.2f}秒)")
                    
                    if result.content:
                        content_preview = result.content[:200] + "..." if len(result.content) > 200 else result.content
                        st.text_area(f"内容预览", content_preview, height=100, disabled=True, key=f"content_{task_id}_{i}")
                    
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
    task_id = research_results.get("task_id", "default")
    
    if final_answer:
        # 添加标题和操作按钮行
        col1, col2 = st.columns([5, 1])
        
        with col1:
            st.markdown("### 🎯 研究结果")
        
        # 切换显示markdown内容的会话状态
        if f"show_markdown_{task_id}" not in st.session_state:
            st.session_state[f"show_markdown_{task_id}"] = False

        with col2:
            if st.button("📋 复制报告", help="生成完整的Markdown报告以供复制", key=f"copy_md_{task_id}"):
                st.session_state[f"show_markdown_{task_id}"] = not st.session_state[f"show_markdown_{task_id}"]

        # 根据状态显示或隐藏markdown预览
        if st.session_state.get(f"show_markdown_{task_id}", False):
            try:
                markdown_content = create_markdown_content(research_results)
                st.code(markdown_content, language="markdown")
                st.success("✅ Markdown报告已生成，请从上方复制代码块中的内容。")
            except Exception as e:
                st.error(f"❌ 生成Markdown失败: {str(e)}")
        
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
            with st.expander(f"🔬 分析过程 ({task_id[:8]})", expanded=False):
                # 使用tabs来避免嵌套expander问题
                tab1, tab2, tab3, tab4 = st.tabs([
                    f"搜索查询_{task_id}", 
                    f"搜索结果_{task_id}", 
                    f"分析反思_{task_id}", 
                    f"统计信息_{task_id}"
                ])
                
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
            with st.expander(f"📚 引用和来源 ({task_id[:8]})", expanded=False):
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