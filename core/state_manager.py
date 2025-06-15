"""
状态管理器
管理应用的会话状态、进度跟踪和数据流
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    SEARCHING = "searching"
    REFLECTING = "reflecting"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SearchResult:
    """搜索结果数据类"""
    query: str
    content: str
    citations: List[Dict]
    urls: List[str]
    has_grounding: bool
    duration: float
    timestamp: datetime
    success: bool = True
    error: str = ""


@dataclass
class TaskProgress:
    """任务进度数据类"""
    task_id: str
    user_query: str
    status: TaskStatus
    current_step: str
    total_steps: int
    completed_steps: int
    start_time: datetime
    estimated_completion: Optional[datetime] = None
    progress_percentage: float = 0.0
    error_message: str = ""


@dataclass
class WorkflowAnalysis:
    """工作流分析结果"""
    task_type: str
    complexity: str
    requires_search: bool
    requires_multiple_rounds: bool
    estimated_steps: int
    estimated_time: str
    reasoning: str
    workflow_steps: List[Dict]


class StateManager:
    """状态管理器"""
    
    def __init__(self):
        # 当前会话状态
        self.current_task: Optional[TaskProgress] = None
        self.workflow_analysis: Optional[WorkflowAnalysis] = None
        
        # 搜索相关状态
        self.search_results: List[SearchResult] = []
        self.search_history: List[str] = []
        self.current_search_round = 0
        self.max_search_rounds = 3
        
        # 步骤执行状态
        self.step_results: Dict[str, Any] = {}
        self.execution_context: Dict[str, Any] = {}
        
        # 分析过程保存（参考原始backend结构）
        self.analysis_process: List[Dict[str, Any]] = []
        self.web_research_results: List[str] = []
        self.reflection_results: List[Dict[str, Any]] = []
        
        # 会话历史
        self.conversation_history: List[Dict[str, Any]] = []
        self.task_history: List[TaskProgress] = []
        
        # 配置和设置
        self.settings = {
            "max_search_results": 10,
            "search_timeout": 30,
            "reflection_threshold": 0.7,
            "max_iterations": 5,
            "auto_save": True
        }
        
        # 统计信息
        self.statistics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "total_searches": 0,
            "average_task_duration": 0.0,
            "session_start_time": datetime.now()
        }
    
    # 任务管理
    def start_new_task(self, user_query: str, task_id: str = None) -> str:
        """开始新任务"""
        if task_id is None:
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 保存当前任务到历史
        if self.current_task:
            self.task_history.append(self.current_task)
        
        # 创建新任务
        self.current_task = TaskProgress(
            task_id=task_id,
            user_query=user_query,
            status=TaskStatus.PENDING,
            current_step="初始化",
            total_steps=0,
            completed_steps=0,
            start_time=datetime.now()
        )
        
        # 重置相关状态
        self.reset_task_state()
        
        # 更新统计
        self.statistics["total_tasks"] += 1
        
        return task_id
    
    def update_task_progress(self, 
                           status: TaskStatus = None,
                           current_step: str = None,
                           completed_steps: int = None,
                           total_steps: int = None,
                           progress_percentage: float = None,
                           error_message: str = None):
        """更新任务进度"""
        if not self.current_task:
            return
        
        if status:
            self.current_task.status = status
        if current_step:
            self.current_task.current_step = current_step
        if completed_steps is not None:
            self.current_task.completed_steps = completed_steps
        if total_steps is not None:
            self.current_task.total_steps = total_steps
        if progress_percentage is not None:
            self.current_task.progress_percentage = progress_percentage
        if error_message:
            self.current_task.error_message = error_message
        
        # 计算预估完成时间
        if self.current_task.completed_steps > 0 and self.current_task.total_steps > 0:
            elapsed = (datetime.now() - self.current_task.start_time).total_seconds()
            remaining_steps = self.current_task.total_steps - self.current_task.completed_steps
            if remaining_steps > 0:
                estimated_time_per_step = elapsed / self.current_task.completed_steps
                estimated_remaining = estimated_time_per_step * remaining_steps
                self.current_task.estimated_completion = datetime.now() + timedelta(seconds=estimated_remaining)
    
    def complete_task(self, final_result: Any = None):
        """完成任务"""
        if not self.current_task:
            return
        
        self.current_task.status = TaskStatus.COMPLETED
        self.current_task.progress_percentage = 100.0
        
        # 更新统计
        self.statistics["successful_tasks"] += 1
        
        # 计算平均任务时长
        task_duration = (datetime.now() - self.current_task.start_time).total_seconds()
        total_duration = self.statistics["average_task_duration"] * (self.statistics["successful_tasks"] - 1)
        self.statistics["average_task_duration"] = (total_duration + task_duration) / self.statistics["successful_tasks"]
        
        # 保存最终结果
        if final_result:
            self.execution_context["final_result"] = final_result
    
    def fail_task(self, error_message: str):
        """任务失败"""
        if not self.current_task:
            return
        
        self.current_task.status = TaskStatus.FAILED
        self.current_task.error_message = error_message
    
    def reset_task_state(self):
        """重置任务相关状态"""
        self.search_results.clear()
        self.search_history.clear()
        self.current_search_round = 0
        self.step_results.clear()
        self.execution_context.clear()
        self.workflow_analysis = None
        
        # 重置分析过程
        self.analysis_process.clear()
        self.web_research_results.clear()
        self.reflection_results.clear()
    
    # 工作流分析管理
    def set_workflow_analysis(self, analysis: Dict[str, Any]):
        """设置工作流分析结果"""
        self.workflow_analysis = WorkflowAnalysis(
            task_type=analysis.get("task_type", "问答系统"),
            complexity=analysis.get("complexity", "中等"),
            requires_search=analysis.get("requires_search", True),
            requires_multiple_rounds=analysis.get("requires_multiple_rounds", False),
            estimated_steps=analysis.get("estimated_steps", 3),
            estimated_time=analysis.get("estimated_time", "1-3分钟"),
            reasoning=analysis.get("reasoning", ""),
            workflow_steps=analysis.get("workflow_steps", [])
        )
        
        # 更新任务进度
        if self.current_task:
            self.current_task.total_steps = self.workflow_analysis.estimated_steps
    
    # 搜索结果管理
    def add_search_queries(self, queries: List[str]):
        """添加搜索查询到历史"""
        for query in queries:
            if query and query not in self.search_history:
                self.search_history.append(query)
    
    def get_search_queries(self) -> List[str]:
        """获取搜索查询历史"""
        return self.search_history.copy()
    
    def add_search_result(self, query: str, result: Dict[str, Any]):
        """添加搜索结果"""
        search_result = SearchResult(
            query=query,
            content=result.get("content", ""),
            citations=result.get("citations", []),
            urls=result.get("urls", []),
            has_grounding=result.get("has_grounding", False),
            duration=result.get("duration", 0.0),
            timestamp=datetime.now(),
            success=result.get("success", True),
            error=result.get("error", "")
        )
        
        self.search_results.append(search_result)
        
        # 添加到搜索历史
        if query and query not in self.search_history:
            self.search_history.append(query)
        
        # 更新统计
        self.statistics["total_searches"] += 1
    
    def get_successful_search_results(self) -> List[SearchResult]:
        """获取成功的搜索结果"""
        return [r for r in self.search_results if r.success]
    
    def get_search_content_list(self, include_citations: bool = False) -> List[str]:
        """获取搜索内容列表"""
        if include_citations:
            content_list = []
            for r in self.search_results:
                if r.success and r.content:
                    content = r.content
                    if r.citations:
                        # 添加引用信息
                        citations_text = "\n\n引用来源:\n"
                        for i, citation in enumerate(r.citations[:3], 1):  # 最多显示3个引用
                            title = citation.get('title', '未知标题')
                            url = citation.get('url', citation.get('uri', ''))
                            citations_text += f"{i}. {title}\n   {url}\n"
                        content += citations_text
                    content_list.append(content)
            return content_list
        else:
            return [r.content for r in self.search_results if r.success and r.content]
    
    def get_all_citations(self) -> List[Dict]:
        """获取所有引用"""
        all_citations = []
        for result in self.search_results:
            if result.success:
                all_citations.extend(result.citations)
        return all_citations
    
    def get_unique_urls(self) -> List[str]:
        """获取去重的URL列表"""
        all_urls = []
        for result in self.search_results:
            if result.success:
                all_urls.extend(result.urls)
        return list(set(all_urls))
    
    # 分析过程管理（参考原始backend结构）
    def add_web_research_result(self, result: str):
        """添加网络搜索结果到分析过程"""
        self.web_research_results.append(result)
    
    def add_reflection_result(self, reflection: Dict[str, Any]):
        """添加反思分析结果"""
        self.reflection_results.append(reflection)
    
    def get_analysis_process(self) -> Dict[str, Any]:
        """获取完整的分析过程"""
        return {
            "search_queries": self.search_history,
            "web_research_results": self.web_research_results,
            "reflection_results": self.reflection_results,
            "search_results_count": len(self.search_results),
            "successful_searches": len(self.get_successful_search_results())
        }
    
    # 步骤结果管理
    def save_step_result(self, step_name: str, result: Any):
        """保存步骤结果"""
        self.step_results[step_name] = {
            "result": result,
            "timestamp": datetime.now(),
            "step_index": len(self.step_results)
        }
    
    def get_step_result(self, step_name: str) -> Any:
        """获取步骤结果"""
        step_data = self.step_results.get(step_name)
        return step_data["result"] if step_data else None
    
    def get_latest_step_result(self) -> Any:
        """获取最新步骤结果"""
        if not self.step_results:
            return None
        
        latest_step = max(self.step_results.values(), key=lambda x: x["timestamp"])
        return latest_step["result"]
    
    # 上下文管理
    def update_context(self, **kwargs):
        """更新执行上下文"""
        self.execution_context.update(kwargs)
    
    def get_context(self, key: str = None) -> Any:
        """获取上下文"""
        if key:
            return self.execution_context.get(key)
        return self.execution_context.copy()
    
    # 会话历史管理
    def add_to_conversation(self, role: str, content: str, metadata: Dict = None):
        """添加到对话历史"""
        conversation_entry = {
            "role": role,  # user, assistant, system
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        self.conversation_history.append(conversation_entry)
    
    def get_conversation_history(self, limit: int = None) -> List[Dict]:
        """获取对话历史"""
        if limit:
            return self.conversation_history[-limit:]
        return self.conversation_history.copy()
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
    
    # 设置管理
    def update_settings(self, **kwargs):
        """更新设置"""
        self.settings.update(kwargs)
    
    def get_setting(self, key: str, default=None):
        """获取设置"""
        return self.settings.get(key, default)
    
    # 统计和监控
    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        session_duration = (datetime.now() - self.statistics["session_start_time"]).total_seconds()
        
        return {
            **self.statistics,
            "session_duration": session_duration,
            "current_task_status": self.current_task.status.value if self.current_task else None,
            "search_results_count": len(self.search_results),
            "successful_searches": len(self.get_successful_search_results()),
            "conversation_length": len(self.conversation_history)
        }
    
    def get_task_summary(self) -> Dict[str, Any]:
        """获取当前任务摘要"""
        if not self.current_task:
            return {}
        
        return {
            "task_id": self.current_task.task_id,
            "user_query": self.current_task.user_query,
            "status": self.current_task.status.value,
            "current_step": self.current_task.current_step,
            "progress": f"{self.current_task.completed_steps}/{self.current_task.total_steps}",
            "progress_percentage": self.current_task.progress_percentage,
            "elapsed_time": (datetime.now() - self.current_task.start_time).total_seconds(),
            "workflow_type": self.workflow_analysis.task_type if self.workflow_analysis else "未知",
            "search_count": len(self.search_results),
            "error_message": self.current_task.error_message
        }
    
    # 数据导出
    def export_session_data(self) -> Dict[str, Any]:
        """导出会话数据"""
        return {
            "current_task": asdict(self.current_task) if self.current_task else None,
            "workflow_analysis": asdict(self.workflow_analysis) if self.workflow_analysis else None,
            "search_results": [asdict(r) for r in self.search_results],
            "conversation_history": self.conversation_history,
            "statistics": self.statistics,
            "settings": self.settings,
            "export_timestamp": datetime.now().isoformat()
        }
    
    def export_task_results(self) -> Dict[str, Any]:
        """导出任务结果"""
        return {
            "task_summary": self.get_task_summary(),
            "search_results": [asdict(r) for r in self.get_successful_search_results()],
            "step_results": self.step_results,
            "final_result": self.execution_context.get("final_result"),
            "citations": self.get_all_citations(),
            "urls": self.get_unique_urls()
        }
    
    # 清理和重置
    def cleanup_old_data(self, days_to_keep: int = 7):
        """清理旧数据"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # 清理旧的任务历史
        self.task_history = [
            task for task in self.task_history 
            if task.start_time > cutoff_date
        ]
        
        # 清理旧的搜索结果
        self.search_results = [
            result for result in self.search_results
            if result.timestamp > cutoff_date
        ]
        
        # 清理旧的对话历史
        self.conversation_history = [
            conv for conv in self.conversation_history
            if conv["timestamp"] > cutoff_date
        ]
    
    def clear_session(self):
        """清除会话数据"""
        # 清除当前任务
        self.current_task = None
        self.workflow_analysis = None
        
        # 清除搜索相关数据
        self.search_results.clear()
        self.search_history.clear()
        self.current_search_round = 0
        
        # 清除步骤和上下文数据
        self.step_results.clear()
        self.execution_context.clear()
        
        # 清除对话历史
        self.conversation_history.clear()
        
        # 重置统计信息（保留会话开始时间）
        session_start = self.statistics["session_start_time"]
        self.statistics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "total_searches": 0,
            "average_task_duration": 0.0,
            "session_start_time": session_start
        }
    
    def reset_session(self):
        """重置整个会话"""
        self.__init__()  # 重新初始化 