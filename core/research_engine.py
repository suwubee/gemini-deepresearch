"""
研究引擎核心
整合工作流构建、搜索代理、状态管理，实现完整的深度研究功能
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from .workflow_builder import DynamicWorkflowBuilder, DynamicWorkflow, WorkflowStep
from .search_agent import SearchAgent
from .state_manager import StateManager, TaskStatus
from .model_config import ModelConfiguration, get_model_config, set_user_model
from utils.prompts import PromptTemplates
from utils.helpers import extract_json_from_text


class ResearchEngine:
    """深度研究引擎核心"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        
        # 设置用户选择的模型，但搜索功能将固定使用gemini-2.0-flash
        set_user_model(model_name)
        self.model_config = get_model_config()
        
        print(f"🤖 模型配置:")
        print(f"  搜索模型: {self.model_config.search_model} (固定)")
        print(f"  任务分析模型: {self.model_config.task_analysis_model}")
        print(f"  反思模型: {self.model_config.reflection_model}")
        print(f"  答案生成模型: {self.model_config.answer_model}")
        
        # 初始化核心组件，使用对应的模型
        self.workflow_builder = DynamicWorkflowBuilder(api_key, self.model_config.task_analysis_model)
        self.search_agent = SearchAgent(api_key, self.model_config.search_model)
        self.state_manager = StateManager()
        
        # 进度回调函数
        self.progress_callback: Optional[Callable] = None
        self.step_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        
        # 停止控制标记
        self._stop_research = False
    
    def set_callbacks(self, progress_callback=None, step_callback=None, error_callback=None):
        """设置回调函数"""
        if progress_callback:
            self.progress_callback = progress_callback
        if step_callback:
            self.step_callback = step_callback
        if error_callback:
            self.error_callback = error_callback
    
    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def set_step_callback(self, callback: Callable):
        """设置步骤回调函数"""
        self.step_callback = callback
    
    def set_error_callback(self, callback: Callable):
        """设置错误回调函数"""
        self.error_callback = callback
    
    def stop_research(self):
        """停止当前研究"""
        self._stop_research = True
        self._notify_step("🛑 收到停止指令，正在终止研究...")
    
    def reset_stop_flag(self):
        """重置停止标记"""
        self._stop_research = False
    
    async def research(self, user_query: str, 
                      max_search_rounds: int = 3,
                      effort_level: str = "medium") -> Dict[str, Any]:
        """
        执行深度研究
        
        Args:
            user_query: 用户查询
            max_search_rounds: 最大搜索轮数
            effort_level: 努力级别 (low, medium, high)
            
        Returns:
            研究结果字典
        """
        try:
            # 重置停止标记
            self._stop_research = False
            
            # 1. 开始新任务
            task_id = self.state_manager.start_new_task(user_query)
            self._notify_progress("开始分析任务...", 0)
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 2. 分析任务并构建工作流
            workflow = await self._analyze_and_build_workflow(user_query, effort_level)
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 3. 替换工作流步骤函数为实际实现，并调整查询数量
            self._inject_research_functions(workflow, max_search_rounds, effort_level)
            
            # 4. 执行工作流
            self.state_manager.update_task_progress(status=TaskStatus.ANALYZING)
            result = await self._execute_workflow(workflow, user_query, max_search_rounds)
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 5. 完成任务
            self.state_manager.complete_task(result)
            self._notify_progress("研究完成！", 100)
            
            return {
                "success": True,
                "task_id": task_id,
                "user_query": user_query,
                "final_answer": result.get("final_answer", ""),
                "search_results": self.state_manager.get_successful_search_results(),
                "citations": self.state_manager.get_all_citations(),
                "urls": self.state_manager.get_unique_urls(),
                "workflow_analysis": self.state_manager.workflow_analysis,
                "task_summary": self.state_manager.get_task_summary(),
                "statistics": self.state_manager.get_session_statistics()
            }
            
        except Exception as e:
            # 处理错误
            error_msg = f"研究过程中发生错误: {str(e)}"
            self.state_manager.fail_task(error_msg)
            
            if self.error_callback:
                self.error_callback(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "task_summary": self.state_manager.get_task_summary()
            }
    
    async def _analyze_and_build_workflow(self, user_query: str, effort_level: str) -> DynamicWorkflow:
        """分析任务并构建工作流"""
        self._notify_step("正在分析任务类型...")
        self._notify_progress("开始任务分析", 10)
        
        try:
            workflow = await self.workflow_builder.analyze_task_and_build_workflow(user_query)
            
            # 保存工作流分析到状态管理器
            self.state_manager.set_workflow_analysis(workflow.config)
            self._notify_progress("任务分析完成", 20)
            
            # 根据努力级别调整参数
            self._adjust_workflow_by_effort(workflow, effort_level)
            
            task_type = workflow.config.get("task_type", "Q&A System")
            complexity = workflow.config.get("complexity", "Medium")
            estimated_steps = len(workflow.steps)  # 使用实际步骤数
            
            print(f"🔍 工作流详情: 类型={task_type}, 复杂度={complexity}, 实际步骤={estimated_steps}")
            print(f"🔍 步骤列表: {[step.name for step in workflow.steps]}")
            
            self._notify_step(f"任务类型: {task_type} (复杂度: {complexity})")
            self._notify_progress(f"工作流构建完成，预计{estimated_steps}步", 30)
            
            return workflow
            
        except Exception as e:
            error_msg = f"工作流构建失败: {str(e)}"
            self._notify_step(error_msg)
            print(f"❌ 工作流构建异常: {e}")
            
            # 创建一个简单的降级工作流
            return self._create_fallback_workflow(user_query)
    
    def _create_fallback_workflow(self, user_query: str) -> DynamicWorkflow:
        """创建降级工作流"""
        workflow_config = {
            "task_type": "问答系统",
            "complexity": "简单",
            "requires_search": True,
            "requires_multiple_rounds": False,
            "estimated_steps": 2,
            "estimated_time": "1-2分钟",
            "reasoning": "降级工作流：直接搜索和回答"
        }
        
        workflow = DynamicWorkflow(workflow_config)
        
        workflow.add_step(WorkflowStep(
            "简单搜索",
            "执行基本搜索",
            self._simple_search_step
        ))
        
        workflow.add_step(WorkflowStep(
            "生成答案",
            "基于搜索结果生成答案",
            self._generate_simple_answer_step
        ))
        
        return workflow
    
    def _adjust_workflow_by_effort(self, workflow: DynamicWorkflow, effort_level: str):
        """根据努力级别调整工作流参数（参考原始frontend规格）"""
        # 参考原始frontend: 
        # Low: initial_search_query_count=1, max_research_loops=1
        # Medium: initial_search_query_count=3, max_research_loops=3  
        # High: initial_search_query_count=5, max_research_loops=10
        
        # 强制覆盖AI分析的复杂度，以用户选择的effort为准
        if effort_level == "low":
            workflow.config["complexity"] = "Low"
            workflow.config["estimated_steps"] = 3
            workflow.config["estimated_time"] = "1-3分钟"
            self.state_manager.update_settings(
                max_search_results=5,
                max_iterations=1,
                search_timeout=15
            )
        elif effort_level == "high":
            workflow.config["complexity"] = "High"  
            workflow.config["estimated_steps"] = 7
            workflow.config["estimated_time"] = "5-15分钟"
            self.state_manager.update_settings(
                max_search_results=20,
                max_iterations=10,
                search_timeout=60
            )
        else:  # medium
            workflow.config["complexity"] = "Medium"
            workflow.config["estimated_steps"] = 5
            workflow.config["estimated_time"] = "3-8分钟"
            self.state_manager.update_settings(
                max_search_results=10,
                max_iterations=3,
                search_timeout=30
            )
        
        print(f"🎯 用户effort级别: {effort_level} → 复杂度: {workflow.config['complexity']}")
    
    def _inject_research_functions(self, workflow: DynamicWorkflow, max_search_rounds: int = 3, effort_level: str = "medium"):
        """将实际的研究功能注入工作流步骤"""
        function_map = {
            "_generate_search_queries_step": self._generate_search_queries_step,
            "_execute_search_step": self._execute_search_step,
            "_analyze_search_results_step": self._analyze_search_results_step,
            "_supplementary_search_step": self._supplementary_search_step,
            "_generate_final_answer_step": self._generate_final_answer_step,
            "_simple_search_step": self._simple_search_step,
            "_generate_simple_answer_step": self._generate_simple_answer_step,
        }
        
        for step in workflow.steps:
            function_name = step.function.__name__
            if function_name in function_map:
                step.function = function_map[function_name]
                
                # 为生成搜索查询步骤调整查询数量（参考原始frontend规格）
                if step.name == "生成搜索查询":
                    # 根据effort级别设置初始查询数量
                    if effort_level == "low":
                        initial_queries = 1
                    elif effort_level == "high":
                        initial_queries = 5
                    else:  # medium
                        initial_queries = 3
                    
                    step.kwargs["num_queries"] = initial_queries
                    print(f"🔍 effort={effort_level} → 初始查询数量: {initial_queries}")
    
    async def _execute_workflow(self, workflow: DynamicWorkflow, 
                               user_query: str, max_search_rounds: int) -> Dict[str, Any]:
        """执行工作流 - 支持动态多轮搜索（参考原始backend逻辑）"""
        initial_context = {
            "user_query": user_query,
            "max_search_rounds": max_search_rounds,
            "search_round": 0
        }
        
        # 如果是研究工作流，实现动态循环
        if len(workflow.steps) >= 4:  # 研究工作流通常有5步
            return await self._execute_research_workflow_with_loops(workflow, initial_context)
        else:
            # 简单工作流直接执行
            result = await workflow.execute(initial_context)
            return result
    
    async def _execute_research_workflow_with_loops(self, workflow: DynamicWorkflow, 
                                                   initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行带循环的研究工作流（参考原始backend的graph结构）"""
        context = initial_context.copy()
        
        # 第1步：生成搜索查询
        self._notify_step("正在生成搜索查询...")
        step1_result = await workflow.steps[0].execute(context)
        context.update(step1_result)
        
        # 第2步：执行初始搜索
        self._notify_step("正在执行初始搜索...")
        step2_result = await workflow.steps[1].execute(context)
        context.update(step2_result)
        
        # 第3步：分析初始搜索结果（第一次reflection）
        self._notify_step("正在分析初始搜索结果...")
        context["search_round"] = 0
        step3_result = await workflow.steps[2].execute(context)
        context.update(step3_result)
        
        analysis = step3_result.get("analysis", {})
        
        # 开始反思循环（参考原始backend的reflection→evaluate_research循环）
        search_round = 1  # 从1开始，因为第0轮（初始搜索）已经完成
        max_search_rounds = context.get("max_search_rounds", 3)
        
        self._notify_progress(f"完成初始搜索分析", 50)
        
        # 添加外部停止检查标记
        self._stop_research = False
        
        while (search_round < max_search_rounds and 
               not analysis.get("is_sufficient", False) and 
               not self._stop_research):
            
            # 检查外部停止信号
            if self._stop_research:
                self._notify_step("🛑 收到停止信号，终止搜索循环")
                break
            
            self._notify_step(f"信息不充足，开始第{search_round+1}轮补充搜索...")
            
            # 第4步：补充搜索
            context["search_round"] = search_round
            step4_result = await workflow.steps[3].execute(context)
            context.update(step4_result)
            
            # 检查是否有API错误导致的搜索失败
            if step4_result.get("api_error", False):
                self._notify_step("⚠️ API错误，停止补充搜索循环")
                break
            
            # 如果没有额外结果，停止循环
            additional_results = step4_result.get("additional_results", [])
            if not additional_results:
                self._notify_step("无法获取更多信息，准备生成最终答案")
                break
            
            self._notify_progress(f"完成第{search_round+1}轮补充搜索", 50 + (search_round * 15))
            
            # 再次分析搜索结果
            self._notify_step(f"正在分析第{search_round+1}轮搜索结果...")
            context["search_round"] = search_round
            step3_result = await workflow.steps[2].execute(context)
            context.update(step3_result)
            
            analysis = step3_result.get("analysis", {})
            
            # 检查分析步骤是否因API错误而强制终止
            if analysis.get("api_error", False):
                self._notify_step("⚠️ 分析阶段API错误，终止搜索循环")
                break
            
            search_round += 1
            
            # 检查是否达到最大轮数
            if search_round >= max_search_rounds:
                self._notify_step("达到最大搜索轮数，准备生成最终答案")
                break
        
        if analysis.get("is_sufficient", False):
            self._notify_step("✅ 信息已充足，准备生成最终答案")
        else:
            self._notify_step(f"⏱️ 完成{search_round}轮搜索，准备生成最终答案")
        
        # 第5步：生成最终答案
        self._notify_step("正在生成最终答案...")
        final_step_result = await workflow.steps[-1].execute(context)
        context.update(final_step_result)
        
        return context
    
    async def _generate_search_queries_step(self, **kwargs) -> Dict[str, Any]:
        """生成搜索查询步骤"""
        user_query = kwargs.get("user_query", "")
        num_queries = kwargs.get("num_queries", 3)
        
        self._notify_step("正在生成搜索查询...")
        
        queries = await self.search_agent.generate_search_queries(user_query, num_queries)
        
        self.state_manager.add_search_queries(queries)
        
        return {"search_queries": queries}
    
    async def _execute_search_step(self, **kwargs) -> Dict[str, Any]:
        """执行搜索步骤"""
        search_queries = kwargs.get("search_queries", [kwargs.get("user_query", "")])
        
        self._notify_step("正在执行网络搜索...")
        
        search_results = []
        for i, query in enumerate(search_queries):
            self._notify_progress(f"搜索查询 {i+1}/{len(search_queries)}: {query[:30]}...", 
                                 40 + (i * 20 // len(search_queries)))
            
            result = await self.search_agent.search_with_grounding(query)
            
            if result.get("success"):
                # 将结果添加到状态管理器（会转换为 SearchResult 对象）
                self.state_manager.add_search_result(query, result)
                
                # 保存到分析过程（参考原始backend结构）
                web_research_content = f"Query: {query}\nContent: {result.get('content', '')}"
                if result.get('citations'):
                    citations_list = result.get('citations', []) or []
                    citations_text = "\n".join([f"- {cite.get('title', 'Unknown Source')}: {cite.get('url', '#')}" 
                                               for cite in citations_list[:3]])
                    web_research_content += f"\nCitations:\n{citations_text}"
                self.state_manager.add_web_research_result(web_research_content)
                
                # 在工作流步骤间传递字典格式
                search_results.append(result)
        
        return {"search_results": search_results}
    
    async def _analyze_search_results_step(self, **kwargs) -> Dict[str, Any]:
        """分析搜索结果步骤 - 参考原始backend的reflection逻辑"""
        user_query = kwargs.get("user_query", "")
        search_results = kwargs.get("search_results", [])
        search_round = kwargs.get("search_round", 0)
        max_search_rounds = kwargs.get("max_search_rounds", 3)
        
        self._notify_step("正在分析搜索结果...")
        
        # 获取所有已搜索的内容用于反思分析
        all_research_results = self.state_manager.get_search_content_list()
        
        # 使用AI进行反思分析（参考原始backend的reflection函数）
        from utils.prompts import PromptTemplates
        
        reflection_prompt = f"""分析以下研究内容，判断是否需要进一步搜索：

研究主题: {user_query}
当前搜索轮数: {search_round + 1}
最大搜索轮数: {max_search_rounds}

已收集的研究内容:
{chr(10).join(['---' + chr(10) + content for content in all_research_results[-5:]])}

请回答：
1. 当前信息是否足够回答用户问题？(是/否)
2. 如果不够，还需要什么信息？
3. 建议的后续搜索查询（如果需要）

请以JSON格式回答：
{{
    "is_sufficient": true/false,
    "knowledge_gap": "说明信息缺口",
    "follow_up_queries": ["查询1", "查询2", ...]
}}"""

        try:
            if self.search_agent.client:
                reflection_model = self.model_config.get_model_for_task("reflection")
                max_tokens = self.model_config.get_token_limits("reflection")
                
                response = self.search_agent.client.models.generate_content(
                    model=reflection_model,
                    contents=reflection_prompt,
                    config={
                        "temperature": 0.3,
                        "max_output_tokens": max_tokens
                    }
                )
                
                # 解析AI反思结果
                import json
                try:
                    reflection_result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                except:
                    # 降级处理
                    reflection_result = {
                        "is_sufficient": len(all_research_results) >= 2,
                        "knowledge_gap": "需要更多详细信息",
                        "follow_up_queries": [f"{user_query} 详细分析", f"{user_query} 最新发展"]
                    }
            else:
                # 降级处理：简单的长度判断
                total_content = sum(len(content) for content in all_research_results)
                reflection_result = {
                    "is_sufficient": total_content > 2000 or search_round >= max_search_rounds - 1,
                    "knowledge_gap": "信息充足" if total_content > 2000 else "需要更多详细信息",
                    "follow_up_queries": [] if total_content > 2000 else [f"{user_query} 详细分析"]
                }
        
        except Exception as e:
            self._notify_step(f"反思分析失败，使用简单逻辑: {str(e)}")
            
            # 检查是否是API配额耗尽错误
            error_str = str(e).lower()
            is_quota_exhausted = any(keyword in error_str for keyword in [
                "quota", "resource_exhausted", "rate limit", "429"
            ])
            
            if is_quota_exhausted:
                # 如果是配额耗尽，强制标记为信息充足，停止循环
                self._notify_step("⚠️ API配额耗尽，强制终止搜索循环")
                reflection_result = {
                    "is_sufficient": True,  # 强制终止
                    "knowledge_gap": "API配额耗尽，无法继续分析",
                    "follow_up_queries": []
                }
            else:
                # 其他错误的降级处理
                total_content = sum(len(content) for content in all_research_results)
                reflection_result = {
                    "is_sufficient": total_content > 1500 or search_round >= max_search_rounds - 1,
                    "knowledge_gap": "分析失败，使用简单判断",
                    "follow_up_queries": [] if total_content > 1500 else [f"{user_query} 补充信息"]
                }
        
        # 保存反思分析结果
        reflection_with_metadata = {
            **reflection_result,
            "search_round": search_round + 1,
            "total_research_content": len(all_research_results),
            "content_analysis": f"已收集 {len(all_research_results)} 个搜索结果"
        }
        self.state_manager.add_reflection_result(reflection_with_metadata)
        
        # 如果是API配额耗尽导致的强制终止，标记API错误
        api_error = False
        knowledge_gap = reflection_result.get("knowledge_gap", "") or ""
        if "配额耗尽" in knowledge_gap:
            api_error = True
        
        return {
            "analysis": reflection_result,
            "search_round": search_round + 1,
            "max_search_rounds": max_search_rounds,
            "api_error": api_error
        }
    
    async def _supplementary_search_step(self, **kwargs) -> Dict[str, Any]:
        """补充搜索步骤 - 参考原始backend的多轮搜索逻辑"""
        analysis = kwargs.get("analysis", {})
        user_query = kwargs.get("user_query", "")
        search_round = kwargs.get("search_round", 0)
        max_search_rounds = kwargs.get("max_search_rounds", 3)
        
        # 检查是否需要继续搜索（参考原始backend的evaluate_research逻辑）
        if analysis.get("is_sufficient", True) or search_round >= max_search_rounds:
            self._notify_step("信息已充足或达到最大搜索轮数，跳过补充搜索")
            return {"additional_results": [], "continue_search": False}
        
        # 获取follow_up_queries
        follow_up_queries = analysis.get("follow_up_queries", [])
        if not follow_up_queries:
            follow_up_queries = [f"{user_query} 详细分析"]
        
        self._notify_step(f"正在进行第{search_round}轮补充搜索...")
        self._notify_progress(f"补充搜索轮次 {search_round}/{max_search_rounds}", 60 + (search_round * 10))
        
        additional_results = []
        
        # 执行所有follow_up_queries（参考原始backend逻辑）
        for i, query in enumerate(follow_up_queries[:2]):  # 限制每轮最多2个查询
            self._notify_step(f"补充搜索 {i+1}/{len(follow_up_queries[:2])}: {query[:30]}...")
            
            try:
                result = await self.search_agent.search_with_grounding(query)
                
                if result.get("success"):
                    self.state_manager.add_search_result(query, result)
                    
                    # 保存到分析过程
                    web_research_content = f"Supplementary Query: {query}\nContent: {result.get('content', '')}"
                    if result.get('citations'):
                        citations_list = result.get('citations', []) or []
                        citations_text = "\n".join([f"- {cite.get('title', 'Unknown Source')}: {cite.get('url', '#')}" 
                                                   for cite in citations_list[:3]])
                        web_research_content += f"\nCitations:\n{citations_text}"
                    self.state_manager.add_web_research_result(web_research_content)
                    
                    additional_results.append(result)
                    
            except Exception as e:
                error_str = str(e).lower()
                is_quota_exhausted = any(keyword in error_str for keyword in [
                    "quota", "resource_exhausted", "rate limit", "429"
                ])
                
                if is_quota_exhausted:
                    self._notify_step(f"⚠️ 补充搜索API配额耗尽，停止当前搜索")
                    return {
                        "additional_results": additional_results,
                        "continue_search": False,
                        "search_round": search_round,
                        "max_search_rounds": max_search_rounds,
                        "api_error": True
                    }
                else:
                    self._notify_step(f"补充搜索失败: {str(e)}")
            
            # 添加延迟避免速率限制
            time.sleep(1)
        
        return {
            "additional_results": additional_results,
            "continue_search": True,
            "search_round": search_round,
            "max_search_rounds": max_search_rounds
        }
    
    async def _generate_final_answer_step(self, **kwargs) -> Dict[str, Any]:
        """生成最终答案步骤"""
        user_query = kwargs.get("user_query", "")
        
        self._notify_step("正在生成最终答案...")
        self._notify_progress("综合信息生成答案", 90)
        
        # 获取所有搜索结果
        all_results = self.state_manager.get_successful_search_results()
        
        if not all_results:
            return {"final_answer": f"抱歉，没有找到关于『{user_query}』的相关信息。"}
        
        # 准备搜索结果内容用于AI合成
        search_summaries = []
        for result in all_results:
            if result.content:
                summary = f"Query: {result.query}\nContent: {result.content}"
                if result.citations:
                    citations_list = result.citations or []
                    citations_text = "\n".join([f"- {cite.get('title', 'Unknown Source')}: {cite.get('url', '#')}" for cite in citations_list[:3]])
                    summary += f"\nCitations:\n{citations_text}"
                search_summaries.append(summary)
        
        if not search_summaries:
            return {"final_answer": f"抱歉，搜索结果没有包含有效内容来回答『{user_query}』。"}
        
        # 使用AI来合成最终答案，让AI判断用户语言
        from utils.prompts import PromptTemplates
        
        synthesis_prompt = PromptTemplates.answer_synthesis_prompt(user_query, search_summaries)
        
        try:
            # 使用SearchAgent的客户端来生成答案，但使用answer_model
            if self.search_agent.client:
                self._notify_step("正在调用AI模型生成详细答案...")
                self._notify_progress("AI正在生成答案，请耐心等待...", 92)
                
                answer_model = self.model_config.get_model_for_task("answer")
                max_tokens = self.model_config.get_token_limits("answer")
                
                self._notify_step(f"使用模型: {answer_model}, Token限制: {max_tokens}")
                
                response = self.search_agent.client.models.generate_content(
                    model=answer_model,
                    contents=synthesis_prompt,
                    config={
                        "temperature": 0.3,
                        "max_output_tokens": max_tokens
                    }
                )
                
                self._notify_step("AI模型响应完成，正在处理结果...")
                self._notify_progress("答案生成完成", 95)
                
                final_answer = response.text
            else:
                # 降级处理：简单拼接
                combined_content = "\n\n---\n\n".join(search_summaries)
                final_answer = f"""# Research Results for: {user_query}

{combined_content}

Note: This information is gathered from web searches. Please verify for accuracy."""
        
        except Exception as e:
            self._notify_step(f"AI合成失败，使用简单格式: {str(e)}")
            # 降级处理：简单拼接但格式化更好
            combined_content = "\n\n---\n\n".join(search_summaries)
            final_answer = f"""# Research Results for: {user_query}

Based on web search results:

{combined_content}

Note: This information is gathered from web searches. Please verify for accuracy."""
        
        return {"final_answer": final_answer}
    
    async def _simple_search_step(self, **kwargs) -> Dict[str, Any]:
        """简单搜索步骤"""
        user_query = kwargs.get("user_query", "")
        
        self._notify_step("正在搜索相关信息...")
        self._notify_progress("执行搜索", 50)
        
        result = await self.search_agent.search_with_grounding(user_query)
        
        if result.get("success"):
            self.state_manager.add_search_result(user_query, result)
        
        return {"search_result": result}
    
    async def _generate_simple_answer_step(self, **kwargs) -> Dict[str, Any]:
        """生成简单答案步骤"""
        user_query = kwargs.get("user_query", "")
        search_result = kwargs.get("search_result", {})
        
        self._notify_step("正在生成答案...")
        self._notify_progress("生成最终答案", 80)
        
        content = search_result.get("content", "")
        citations = search_result.get("citations", [])
        
        if content:
            # 准备搜索结果用于AI合成
            search_summaries = [f"Query: {user_query}\nContent: {content}"]
            if citations:
                citations_list = citations or []
                citations_text = "\n".join([f"- {cite.get('title', 'Unknown Source')}: {cite.get('url', '#')}" for cite in citations_list[:3]])
                search_summaries[0] += f"\nCitations:\n{citations_text}"
            
            # 使用AI来合成答案，让AI判断用户语言
            from utils.prompts import PromptTemplates
            synthesis_prompt = PromptTemplates.answer_synthesis_prompt(user_query, search_summaries)
            
            try:
                # 使用SearchAgent的客户端来生成答案，但使用answer_model
                if self.search_agent.client:
                    answer_model = self.model_config.get_model_for_task("answer")
                    max_tokens = self.model_config.get_token_limits("answer")
                    
                    response = self.search_agent.client.models.generate_content(
                        model=answer_model,
                        contents=synthesis_prompt,
                        config={
                            "temperature": 0.3,
                            "max_output_tokens": max_tokens
                        }
                    )
                    answer = response.text
                else:
                    # 降级处理
                    answer = f"""# Answer to: {user_query}

{content}

{f"Sources: {len(citations)} citations" if citations else ""}"""
            
            except Exception as e:
                self._notify_step(f"AI合成失败，使用简单格式: {str(e)}")
                # 降级处理
                answer = f"""# Answer to: {user_query}

{content}

{f"Sources: {len(citations)} citations" if citations else ""}"""
        else:
            answer = f"Sorry, no relevant information was found for '{user_query}'. Please try rephrasing your question."
        
        return {"final_answer": answer}
    
    def _notify_progress(self, message: str, percentage: float):
        """通知进度更新"""
        if self.progress_callback:
            self.progress_callback(message, percentage)
    
    def _notify_step(self, message: str):
        """通知步骤更新"""
        if self.step_callback:
            self.step_callback(message)
    
    def get_current_task_info(self) -> Dict[str, Any]:
        """获取当前任务信息"""
        return self.state_manager.get_task_summary()
    
    def export_results(self) -> Dict[str, Any]:
        """导出研究结果"""
        return self.state_manager.export_session_data()
    
    def clear_session(self):
        """清除会话数据"""
        self.state_manager.clear_session()
        self.search_agent.clear_history() 