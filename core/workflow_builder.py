"""
动态工作流构建器
参考原始backend/src/agent/planner.py的设计
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import time

from .state_manager import TaskStatus, WorkflowAnalysis
from .api_client import GeminiApiClient
from utils.prompts import PromptTemplates
from utils.helpers import extract_json_from_text, safe_json_loads
from utils.debug_logger import get_debug_logger


class WorkflowStep:
    """工作流步骤"""
    
    def __init__(self, name: str, description: str, function: Callable, **kwargs):
        self.name = name
        self.description = description
        self.function = function
        self.kwargs = kwargs
        self.status = "pending"  # pending, running, completed, failed
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行步骤"""
        self.status = "running"
        self.start_time = datetime.now()
        
        try:
            # 合并上下文和步骤参数
            params = {**context, **self.kwargs}
            
            # 执行步骤函数
            if asyncio.iscoroutinefunction(self.function):
                self.result = await self.function(**params)
            else:
                self.result = self.function(**params)
            
            self.status = "completed"
            self.end_time = datetime.now()
            
            return self.result
            
        except Exception as e:
            self.status = "failed"
            self.end_time = datetime.now()
            self.error = str(e)
            raise e


class DynamicWorkflow:
    """动态工作流，包含步骤和配置"""
    def __init__(self, workflow_id: str, analysis: Dict[str, Any]):
        self.workflow_id = workflow_id
        self.analysis = analysis
        self.steps: List['WorkflowStep'] = []
        self.config = {
            "max_search_rounds": 3,
            "queries_per_round": 3,
            "stop_on_sufficient": True,
        }
    
    def add_step(self, step_name: str, step_function: Any, description: str):
        step = WorkflowStep(step_name, description, step_function)
        self.steps.append(step)


class DynamicWorkflowBuilder:
    """动态工作流构建器，参考原始planner"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = GeminiApiClient(api_key=api_key)
        self.debug_logger = get_debug_logger()

    async def build_workflow(self, user_query: str) -> DynamicWorkflow:
        """分析用户查询并构建动态工作流"""
        self.debug_logger.log_workflow_step(
            "build_workflow_start", "running", {"user_query": user_query}
        )
        
        try:
            prompt = PromptTemplates.task_analysis_prompt(user_query)
            
            # Debug: Log API request for task analysis
            request_id = f"task_analysis_{int(time.time() * 1000)}"
            self.debug_logger.log_api_request(
                "task_analysis", self.model_name, prompt, {}, request_id
            )

            response = await self.client.generate_content(
                model_name=self.model_name,
                prompt=prompt,
                temperature=0.1,
                max_output_tokens=2048,
            )
            
            # Debug: Log API response
            response_text = ""
            if "error" not in response:
                try:
                    response_text = response["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    pass
            
            self.debug_logger.log_api_response(request_id, response_text, response)

            if "error" in response:
                raise Exception(f"API Error: {response['error'].get('message', 'Unknown error')}")

            analysis = extract_json_from_text(response_text)
            
            if not analysis or "task_type" not in analysis:
                self.debug_logger.log_warning(
                    "TaskAnalysisWarning", 
                    "Failed to parse task analysis, using fallback.",
                    {"raw_response": response_text}
                )
                analysis = self._fallback_analysis()
            
            workflow = DynamicWorkflow(f"wf_{int(time.time())}", analysis)
            self._build_research_workflow(workflow, user_query, analysis)
            
            self.debug_logger.log_workflow_step(
                "build_workflow_complete", "completed", {"workflow_id": workflow.workflow_id, "steps_count": len(workflow.steps)}
            )
            
            return workflow
        
        except Exception as e:
            self.debug_logger.log_error(
                "WorkflowBuildError", str(e), {"user_query": user_query}
            )
            analysis = self._fallback_analysis()
            workflow = DynamicWorkflow(f"wf_fallback_{int(time.time())}", analysis)
            self._build_research_workflow(workflow, user_query, analysis)
            return workflow
    
    def _fallback_analysis(self) -> Dict[str, Any]:
        """提供一个备用的分析结果，以防AI分析失败"""
        return {
            "task_type": "Deep Research",
            "complexity": "Medium",
            "requires_search": True,
            "requires_multiple_rounds": True,
            "estimated_steps": 5,
            "estimated_time": "3-8 minutes",
            "reasoning": "Fallback due to analysis failure. Assuming standard research task."
        }

    def _build_research_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """根据分析结果构建具体的研究工作流步骤"""
        task_type = analysis.get("task_type", "Deep Research")
        
        # 简化逻辑：当前只实现一种深度研究工作流
        if task_type in ["Deep Research", "Comprehensive Task"]:
            workflow.add_step(
                "generate_search_queries", 
                self._generate_search_queries_step,
                "生成初始搜索查询"
            )
            workflow.add_step(
                "execute_search", 
                self._execute_search_step,
                "执行并行搜索"
            )
            workflow.add_step(
                "analyze_search_results", 
                self._analyze_search_results_step,
                "分析搜索结果并进行AI反思"
            )
            workflow.add_step(
                "supplementary_search",
                self._supplementary_search_step,
                "进行补充搜索以填补信息空白"
            )
            workflow.add_step(
                "generate_final_answer", 
                self._generate_final_answer_step,
                "综合所有信息生成最终研究报告"
            )
        else: # Q&A, Code Generation etc. use a simpler workflow
            workflow.add_step(
                "simple_search",
                self._simple_search_step,
                "执行单轮搜索"
            )
            workflow.add_step(
                "generate_simple_answer",
                self._generate_simple_answer_step,
                "根据搜索结果生成答案"
            )

    # 这些是占位符函数，实际的执行逻辑在ResearchEngine中
    async def _generate_search_queries_step(self, **kwargs): pass
    async def _execute_search_step(self, **kwargs): pass
    async def _analyze_search_results_step(self, **kwargs): pass
    async def _supplementary_search_step(self, **kwargs): pass
    async def _generate_final_answer_step(self, **kwargs): pass
    async def _simple_search_step(self, **kwargs): pass
    async def _generate_simple_answer_step(self, **kwargs): pass
    
    # 以后可以扩展用于其他任务类型
    async def _search_technical_info_step(self, **kwargs): pass
    async def _generate_code_step(self, **kwargs): pass
    async def _search_data_sources_step(self, **kwargs): pass
    async def _analyze_data_step(self, **kwargs): pass
    
    async def close(self):
        """关闭客户端会话"""
        await self.client.close() 