"""
深度研究引擎核心
简化版本，移除复杂逻辑和死循环问题
"""

import asyncio
import traceback
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from .state_manager import StateManager
from .workflow_builder import DynamicWorkflowBuilder, DynamicWorkflow
from .search_agent import SearchAgent
from .model_config import get_model_config, set_user_model
from utils.debug_logger import get_debug_logger
from utils.prompts import PromptTemplates
from utils.helpers import extract_json_from_text


class ResearchEngine:
    """简化的深度研究引擎核心"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash", api_provider: str = "gemini"):
        set_user_model(model_name)
        self.model_config = get_model_config()
        self.api_provider = api_provider
        
        # 初始化核心组件 
        self.workflow_builder = DynamicWorkflowBuilder(api_key, self.model_config.task_analysis_model, api_provider)
        self.search_agent = SearchAgent(api_key, self.model_config.search_model, api_provider)
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
        """简化的研究流程"""
        try:
            self._stop_research = False
            task_id = self.state_manager.start_new_task(user_query)
            self._notify_progress("开始研究...", 0)
            
            if self._stop_research: 
                return {"success": False, "error": "用户终止"}
            
            # 简化流程：直接进行搜索和答案生成
            self._notify_step(f"🎯 开始 {effort_level} 强度研究")
            self._notify_progress("生成搜索查询...", 20)
            
            # 1. 生成搜索查询
            queries = await self._generate_search_queries(user_query, num_search_queries)
            if self._stop_research: 
                return {"success": False, "error": "用户终止"}
            
            # 2. 执行搜索
            self._notify_progress("执行搜索...", 40)
            search_results = await self._execute_searches(queries)
            if self._stop_research: 
                return {"success": False, "error": "用户终止"}
            
            # 3. 检查是否需要补充搜索
            if max_search_rounds > 1 and effort_level != "low":
                self._notify_progress("分析搜索结果...", 60)
                additional_queries = await self._analyze_and_get_follow_up(user_query, max_search_rounds - 1)
                if additional_queries and not self._stop_research:
                    self._notify_progress("执行补充搜索...", 70)
                    additional_results = await self._execute_searches(additional_queries)
            
            # 4. 生成最终答案
            if self._stop_research: 
                return {"success": False, "error": "用户终止"}
            
            self._notify_progress("生成最终报告...", 80)
            final_answer = await self._generate_final_answer(user_query)
            
            # 完成任务
            self.state_manager.complete_task({"final_answer": final_answer})
            self._notify_progress("研究完成！", 100)
            
            result = {
                "success": True, 
                "task_id": task_id, 
                "final_answer": final_answer,
                **self.state_manager.get_task_summary()
            }
            
            return result
            
        except Exception as e:
            error_msg = f"研究过程中发生错误: {e}"
            self.state_manager.fail_task(error_msg)
            self.debug_logger.log_error("ResearchError", error_msg, {"user_query": user_query}, traceback.format_exc())
            if self.error_callback: 
                self.error_callback(error_msg)
            return {"success": False, "error": error_msg}

    async def _generate_search_queries(self, user_query: str, num_queries: int) -> List[str]:
        """生成搜索查询"""
        try:
            self._notify_step(f"🔍 生成 {num_queries} 个搜索查询...")
            queries = await self.search_agent.generate_search_queries(user_query, num_queries)
            
            if queries and len(queries) > 0:
                queries_text = "\n".join([f"  • {q}" for q in queries])
                self._notify_step(f"✅ 生成查询完成:\n{queries_text}")
                return queries
            else:
                self._notify_step("⚠️ 查询生成失败，使用原始查询")
                return [user_query]
                
        except Exception as e:
            self._notify_step(f"⚠️ 查询生成错误: {e}，使用原始查询")
            return [user_query]

    async def _execute_searches(self, queries: List[str]) -> List[Dict[str, Any]]:
        """执行搜索"""
        try:
            self._notify_step(f"🌐 执行 {len(queries)} 个搜索...")
            results = await self.search_agent.batch_search(queries)
            
            # 统计和保存结果
            successful = 0
            for query, result in zip(queries, results):
                if result.get("success"):
                    self.state_manager.add_search_result(query, result)
                    successful += 1
            
            self._notify_step(f"✅ 搜索完成: {successful}/{len(queries)} 成功")
            return results
            
        except Exception as e:
            self._notify_step(f"❌ 搜索失败: {e}")
            return []

    async def _analyze_and_get_follow_up(self, user_query: str, remaining_rounds: int) -> List[str]:
        """分析结果并获取后续查询"""
        if remaining_rounds <= 0:
            return []
            
        try:
            content_list = self.state_manager.get_search_content_list()
            if not content_list:
                return []
            
            self._notify_step("🤔 分析搜索结果...")
            prompt = PromptTemplates.reflection_prompt(user_query, content_list)
            model = self.model_config.get_model_for_task("reflection")
            
            response = await self.search_agent.client.generate_content(
                model_name=model,
                prompt=prompt,
                temperature=0.1,
                max_output_tokens=2048
            )
            
            if "error" in response:
                self._notify_step("⚠️ 分析失败，跳过补充搜索")
                return []
            
            response_text = response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            reflection = extract_json_from_text(response_text)
            
            if reflection and isinstance(reflection, dict):
                is_sufficient = reflection.get("is_sufficient", True)
                follow_up_queries = reflection.get("follow_up_queries", [])
                
                if is_sufficient:
                    self._notify_step("✅ 信息充足，无需补充搜索")
                    return []
                
                if follow_up_queries:
                    self._notify_step(f"📋 识别到 {len(follow_up_queries)} 个补充查询")
                    return follow_up_queries[:3]  # 限制数量
            
            return []
            
        except Exception as e:
            self._notify_step(f"⚠️ 分析错误: {e}，跳过补充搜索")
            return []

    async def _generate_final_answer(self, user_query: str) -> str:
        """生成最终答案"""
        try:
            self._notify_step("📝 生成最终报告...")
            all_content = self.state_manager.get_search_content_list(include_citations=True)
            
            if not all_content:
                return "抱歉，未能找到有效信息来回答您的问题。"

            prompt = PromptTemplates.answer_synthesis_prompt(user_query, all_content)
            model = self.model_config.get_model_for_task("answer")
            
            response = await self.search_agent.client.generate_content(
                model_name=model,
                prompt=prompt,
                temperature=0.1,
                max_output_tokens=4096
            )
            
            if "error" in response:
                raise Exception(f"API错误: {response['error'].get('message', 'Unknown error')}")
            
            final_answer = response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            if final_answer:
                self._notify_step("✅ 最终报告生成完成")
                return final_answer
            else:
                # 回退：使用搜索内容的简单拼接
                self._notify_step("⚠️ AI生成失败，使用搜索内容")
                return "\n\n---\n\n".join(self.state_manager.get_search_content_list())
                
        except Exception as e:
            self._notify_step(f"⚠️ 报告生成失败: {e}")
            # 回退：使用搜索内容的简单拼接
            content_list = self.state_manager.get_search_content_list()
            if content_list:
                return "\n\n---\n\n".join(content_list)
            else:
                return "抱歉，研究过程中遇到问题，未能生成有效报告。"

    def _notify_progress(self, message: str, percentage: float):
        """通知进度"""
        if self.progress_callback: 
            self.progress_callback(message, percentage)
    
    def _notify_step(self, message: str):
        """通知步骤"""
        if self.step_callback: 
            self.step_callback(message)
    
    async def close_clients(self):
        """关闭客户端"""
        await self.search_agent.close()
        await self.workflow_builder.close()

    def get_current_task_info(self): 
        """获取当前任务信息"""
        return self.state_manager.get_task_summary()
        
    def clear_session(self):
        """清除会话"""
        self.state_manager.clear_session()
        self.search_agent.clear_history() 