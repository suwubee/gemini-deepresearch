"""
辅助工具函数
包含文本处理、URL提取、引用格式化等功能
"""

import re
import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime


def clean_text(text: str) -> str:
    """清理文本，移除多余的空白字符"""
    if not text:
        return ""
    
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    
    return text


def extract_urls(text: str) -> List[str]:
    """从文本中提取URL链接"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return list(set(urls))  # 去重


def format_citations(text: str, citations: List[Dict]) -> str:
    """格式化引用，将引用信息插入到文本中"""
    if not citations:
        return text
    
    # 按位置倒序排列，避免插入时位置偏移
    citations_sorted = sorted(citations, key=lambda x: x.get('end_index', 0), reverse=True)
    
    formatted_text = text
    for citation in citations_sorted:
        start_idx = citation.get('start_index', 0)
        end_idx = citation.get('end_index', len(text))
        segments = citation.get('segments', [])
        
        if segments:
            citation_links = []
            for segment in segments:
                label = segment.get('label', 'Source')
                url = segment.get('value', '#')
                citation_links.append(f"[{label}]({url})")
            
            citation_text = ' ' + ' '.join(citation_links)
            formatted_text = formatted_text[:end_idx] + citation_text + formatted_text[end_idx:]
    
    return formatted_text


def extract_json_from_text(text: str) -> Optional[Dict]:
    """从文本中提取JSON对象"""
    if not text or not text.strip():
        return None
    
    try:
        # 尝试直接解析
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 查找JSON代码块
    json_pattern = r'```(?:json)?\s*(.*?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # 查找花括号包围的内容
    brace_pattern = r'\{.*?\}'
    match = re.search(brace_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def truncate_text(text: str, max_length: int = 1000) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    
    # 在单词边界截断
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:  # 如果最后一个空格位置合理
        truncated = truncated[:last_space]
    
    return truncated + "..."


def format_time_duration(seconds: float) -> str:
    """格式化时间长度"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:.0f}m {remaining_seconds:.1f}s"


def validate_api_key(api_key: str) -> bool:
    """验证API密钥格式"""
    if not api_key or api_key == "your_gemini_api_key_here":
        return False
    
    # 基本格式检查（Gemini API密钥通常以AIza开头）
    if len(api_key) < 20:
        return False
    
    return True


def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def create_search_summary(search_results: List[str], max_results: int = 3) -> str:
    """创建搜索结果摘要"""
    if not search_results:
        return "暂无搜索结果"
    
    summary_parts = []
    for i, result in enumerate(search_results[:max_results], 1):
        truncated = truncate_text(result, 200)
        summary_parts.append(f"{i}. {truncated}")
    
    if len(search_results) > max_results:
        summary_parts.append(f"... 还有 {len(search_results) - max_results} 条结果")
    
    return "\n\n".join(summary_parts)


def extract_key_points(text: str, max_points: int = 5) -> List[str]:
    """从文本中提取关键点"""
    # 简单的关键点提取（基于句子）
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    # 返回前几个较长的句子作为关键点
    key_points = sentences[:max_points]
    return key_points


async def run_with_timeout(coro, timeout_seconds: float = 30.0):
    """运行协程并设置超时"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"操作超时（{timeout_seconds}秒）")


def get_display_name(task_type: str) -> str:
    """获取任务类型的显示名称"""
    display_names = {
        "深度研究": "🔍 深度研究",
        "数据分析": "📊 数据分析", 
        "代码生成": "💻 代码生成",
        "文档写作": "📝 文档写作",
        "问答系统": "❓ 问答系统",
        "综合任务": "🔧 综合任务"
    }
    return display_names.get(task_type, f"🤖 {task_type}")


def format_step_description(step: str, description: str) -> str:
    """格式化步骤描述"""
    step_icons = {
        "分析查询": "🎯",
        "生成搜索查询": "🔍", 
        "执行网络搜索": "🌐",
        "分析反思": "🤔",
        "生成最终答案": "📝",
        "数据处理": "📊",
        "代码编写": "💻",
        "文档创建": "📄"
    }
    
    icon = step_icons.get(step, "⚡")
    return f"{icon} {step}: {description}"


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.steps = []
        self.current_step = 0
    
    def add_step(self, name: str, description: str):
        """添加步骤"""
        self.steps.append({
            "name": name,
            "description": description,
            "status": "pending",
            "start_time": None,
            "end_time": None
        })
    
    def start_step(self, step_index: int):
        """开始执行步骤"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index]["status"] = "running"
            self.steps[step_index]["start_time"] = datetime.now()
            self.current_step = step_index
    
    def complete_step(self, step_index: int):
        """完成步骤"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index]["status"] = "completed"
            self.steps[step_index]["end_time"] = datetime.now()
    
    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        if not self.steps:
            return 0.0
        
        completed = len([s for s in self.steps if s["status"] == "completed"])
        return (completed / len(self.steps)) * 100
    
    def get_elapsed_time(self) -> float:
        """获取总耗时（秒）"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_step_summary(self) -> str:
        """获取步骤摘要"""
        total = len(self.steps)
        completed = len([s for s in self.steps if s["status"] == "completed"])
        running = len([s for s in self.steps if s["status"] == "running"])
        
        return f"进度: {completed}/{total} 完成, {running} 进行中" 