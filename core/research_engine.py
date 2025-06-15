"""
研究引擎核心
整合工作流构建、搜索代理、状态管理，实现完整的深度研究功能
"""

import asyncio
import time
import traceback
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from .workflow_builder import DynamicWorkflowBuilder, DynamicWorkflow
from .search_agent import SearchAgent
from .state_manager import StateManager
from .model_config import get_model_config, set_user_model
from utils.prompts import PromptTemplates
from utils.helpers import extract_json_from_text
from utils.debug_logger import get_debug_logger


class ResearchEngine:
    """深度研究引擎核心"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        set_user_model(model_name)
        self.model_config = get_model_config()
        
        # 初始化核心组件
        self.workflow_builder = DynamicWorkflowBuilder(api_key, self.model_config.task_analysis_model)
        self.search_agent = SearchAgent(api_key, self.model_config.search_model)
        self.state_manager = StateManager()
        self.debug_logger = get_debug_logger()
        
        self.progress_callback: Optional[Callable] = None
        self.step_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self._stop_research = False
    
    def set_callbacks(self, progress_callback=None, step_callback=None, error_callback=None):
        if progress_callback: self.progress_callback = progress_callback
        if step_callback: self.step_callback = step_callback
        if error_callback: self.error_callback = error_callback
    
    def stop_research(self):
        self._stop_research = True
        self._notify_step("🛑 研究已终止...")

    async def research(self, user_query: str, max_search_rounds: int = 3, effort_level: str = "medium", num_search_queries: int = 3) -> Dict[str, Any]:
        try:
            self._stop_research = False
            task_id = self.state_manager.start_new_task(user_query)
            self._notify_progress("开始分析任务...", 0)
            
            if self._stop_research: return {"success": False, "error": "用户终止"}
            
            workflow = await self.workflow_builder.build_workflow(user_query)
            self.state_manager.set_workflow_analysis(workflow.analysis)
            self._adjust_workflow_by_effort(workflow, effort_level, max_search_rounds, num_search_queries)
            self._inject_research_functions(workflow)
            
            context = {
                "user_query": user_query,
                "workflow": workflow
            }
            
            final_context = await self._execute_workflow(context)
            
            self.state_manager.complete_task(final_context)
            self._notify_progress("研究完成！", 100)
            
            return {"success": True, "task_id": task_id, **self.state_manager.get_task_summary()}
            
        except Exception as e:
            error_msg = f"研究过程中发生错误: {e}"
            self.state_manager.fail_task(error_msg)
            self.debug_logger.log_error("ResearchError", error_msg, {"user_query": user_query}, traceback.format_exc())
            if self.error_callback: self.error_callback(error_msg)
            return {"success": False, "error": error_msg}

    def _adjust_workflow_by_effort(self, workflow: DynamicWorkflow, effort: str, rounds: int, queries: int):
        config_map = {
            "low": {"max_search_rounds": 1, "queries_per_round": 1},
            "high": {"max_search_rounds": 5, "queries_per_round": 5},
            "medium": {"max_search_rounds": 3, "queries_per_round": 3}
        }
        workflow.config.update(config_map.get(effort, config_map["medium"]))
        workflow.config["max_search_rounds"] = rounds
        workflow.config["queries_per_round"] = queries

    def _inject_research_functions(self, workflow: DynamicWorkflow):
        step_map = {
            "generate_search_queries": self._step_generate_queries,
            "execute_search": self._step_execute_search,
            "analyze_search_results": self._step_analyze_results,
            "supplementary_search": self._step_supplementary_search,
            "generate_final_answer": self._step_generate_answer,
            "simple_search": self._step_execute_search,
            "generate_simple_answer": self._step_generate_answer,
        }
        for step in workflow.steps:
            step.function = step_map.get(step.name)

    async def _execute_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        workflow: DynamicWorkflow = context["workflow"]
        for i, step in enumerate(workflow.steps):
            if self._stop_research or not step.function: break
            
            self._notify_step(f"步骤 {i+1}/{len(workflow.steps)}: {step.description}")
            context = await step.function(context)
            
            if context.get("is_sufficient") and step.name != 'generate_final_answer':
                self._notify_step("信息充足，流程提前结束。")
                break
        
        if "final_answer" not in context:
            context = await self._step_generate_answer(context)
            
        return context

    async def _step_generate_queries(self, context: Dict[str, Any]) -> Dict[str, Any]:
        workflow: DynamicWorkflow = context["workflow"]
        queries = await self.search_agent.generate_search_queries(
            context["user_query"], workflow.config["queries_per_round"]
        )
        self.state_manager.add_search_queries(queries)
        
        # 详细输出搜索关键词
        queries_text = "\n".join([f"  • {q}" for q in queries])
        self._notify_step(f"🔍 生成搜索查询 ({len(queries)} 个):\n{queries_text}")
        
        return {**context, "search_queries": queries}

    async def _step_execute_search(self, context: Dict[str, Any]) -> Dict[str, Any]:
        queries = context.get("search_queries", [context["user_query"]])
        self._notify_step(f"🌐 开始搜索 {len(queries)} 个查询...")
        
        results = await self.search_agent.batch_search(queries)
        
        # 统计搜索结果
        successful_searches = 0
        total_results = 0
        
        for q, res in zip(queries, results):
            if res.get("success"):
                self.state_manager.add_search_result(q, res)
                successful_searches += 1
                # 统计搜索结果数量
                if "search_results" in res:
                    total_results += len(res.get("search_results", []))
        
        # 详细输出搜索结果统计
        self._notify_step(f"✅ 搜索完成: {successful_searches}/{len(queries)} 个查询成功，共获得 {total_results} 条结果")
        
        return {**context, "search_results": results, "current_round": 1}

    async def _step_analyze_results(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = PromptTemplates.reflection_prompt(context["user_query"], self.state_manager.get_search_content_list())
        model = self.model_config.get_model_for_task("reflection")
        try:
            response = await self.search_agent.client.generate_content(model, prompt)
            reflection = extract_json_from_text(response["candidates"][0]["content"]["parts"][0]["text"])
            if not reflection: raise ValueError("Parsing reflection failed")
        except Exception as e:
            self._notify_step(f"分析失败: {e}")
            reflection = {"is_sufficient": True, "knowledge_gap": "Analysis failed", "follow_up_queries": []}
        
        self.state_manager.add_reflection_result(reflection)
        return {**context, **reflection}

    async def _step_supplementary_search(self, context: Dict[str, Any]) -> Dict[str, Any]:
        workflow: DynamicWorkflow = context["workflow"]
        current_round = context.get("current_round", 1)
        
        while current_round < workflow.config["max_search_rounds"]:
            if context.get("is_sufficient"): 
                self._notify_step("ℹ️ 信息已充足，跳过后续搜索轮次")
                break
            
            queries = context.get("follow_up_queries", [])
            if not queries: 
                self._notify_step("ℹ️ 无需补充搜索查询，结束搜索")
                break
            
            # 显示补充搜索的查询
            queries_text = "\n".join([f"  • {q}" for q in queries])
            self._notify_step(f"🔄 第 {current_round + 1} 轮补充搜索 ({len(queries)} 个查询):\n{queries_text}")
            
            context["search_queries"] = queries
            context = await self._step_execute_search(context)
            context = await self._step_analyze_results(context)
            current_round += 1
            context["current_round"] = current_round
            
        return context

    async def _step_generate_answer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._notify_step("生成最终报告...")
        all_content = self.state_manager.get_search_content_list(include_citations=True)
        if not all_content:
            return {**context, "final_answer": "抱歉，未能找到有效信息。"}

        prompt = PromptTemplates.answer_synthesis_prompt(context["user_query"], all_content)
        model = self.model_config.get_model_for_task("answer")
        try:
            response = await self.search_agent.client.generate_content(model, prompt)
            final_answer = response["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            self._notify_step(f"AI合成失败: {e}")
            final_answer = "\n\n---\n\n".join(self.state_manager.get_search_content_list())
        
        return {**context, "final_answer": final_answer}

    def _notify_progress(self, message: str, percentage: float):
        if self.progress_callback: self.progress_callback(message, percentage)
    
    def _notify_step(self, message: str):
        if self.step_callback: self.step_callback(message)
    
    async def close_clients(self):
        await self.search_agent.close()
        await self.workflow_builder.close()

    def get_current_task_info(self): return self.state_manager.get_task_summary()
    def clear_session(self):
        self.state_manager.clear_session()
        self.search_agent.clear_history() 