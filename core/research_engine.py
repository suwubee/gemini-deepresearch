"""
研究引擎核心
整合工作流构建、搜索代理、状态管理，实现完整的深度研究功能
"""

import asyncio
import json
import time
import traceback
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

# 导入核心模块
from .search_agent import SearchAgent
from .workflow_builder import DynamicWorkflowBuilder, DynamicWorkflow, WorkflowStep
from .state_manager import StateManager
from .debug_logger import get_debug_logger
from ..utils.models import get_model_config, set_user_model


class ResearchEngine:
    """深度研究引擎核心 - 支持双模式API"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        """初始化研究引擎"""
        self.api_key = api_key
        self.model_name = model_name
        
        # 设置用户选择的模型，但搜索功能将固定使用gemini-2.0-flash
        set_user_model(model_name)
        self.model_config = get_model_config()
        
        print(f"🤖 研究引擎初始化:")
        print(f"  用户选择模型: {model_name}")
        print(f"  搜索模型: {self.model_config.search_model}")
        print(f"  任务分析模型: {self.model_config.task_analysis_model}")
        print(f"  反思模型: {self.model_config.reflection_model}")
        print(f"  答案生成模型: {self.model_config.answer_model}")
        
        # 初始化核心组件，使用原始方法
        self.workflow_builder = DynamicWorkflowBuilder(api_key, self.model_config.task_analysis_model)
        self.search_agent = SearchAgent(api_key, self.model_config.search_model)
        self.state_manager = StateManager()
        self.debug_logger = get_debug_logger()
        
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
                      effort_level: str = "medium",
                      num_search_queries: int = 3) -> Dict[str, Any]:
        """
        执行深度研究
        
        Args:
            user_query: 用户查询
            max_search_rounds: 最大搜索轮数
            effort_level: 努力级别 (low, medium, high)
            num_search_queries: 初始搜索查询数量
            
        Returns:
            研究结果字典
        """
        try:
            # 重置停止标记
            self._stop_research = False
            
            # Debug: 记录研究开始
            self.debug_logger.log_workflow_step(
                step_name="research_start",
                step_status="running",
                input_data={
                    "user_query": user_query,
                    "max_search_rounds": max_search_rounds,
                    "effort_level": effort_level,
                    "num_search_queries": num_search_queries
                }
            )
            
            # 1. 开始新任务
            task_id = self.state_manager.start_new_task(user_query)
            self._notify_progress("开始分析任务...", 0)
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 2. 分析任务并构建工作流
            workflow = await self._analyze_and_build_workflow(user_query, effort_level)
            
            # 设置搜索查询数量
            workflow.config["num_search_queries"] = num_search_queries
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 3. 替换工作流步骤函数为实际实现
            self._inject_research_functions(workflow)
            
            # 4. 执行工作流
            self.state_manager.update_task_progress(status=TaskStatus.ANALYZING)
            result = await self._execute_workflow(workflow, user_query, max_search_rounds, num_search_queries)
            
            # 检查停止信号
            if self._stop_research:
                return {"success": False, "error": "研究被用户停止"}
            
            # 5. 完成任务
            self.state_manager.complete_task(result)
            self._notify_progress("研究完成！", 100)
            
            final_result = {
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
            
            # Debug: 记录研究完成
            self.debug_logger.log_research_result(
                user_query=user_query,
                final_result=final_result,
                metadata={
                    "task_id": task_id,
                    "effort_level": effort_level,
                    "max_search_rounds": max_search_rounds
                }
            )
            
            self.debug_logger.log_workflow_step(
                step_name="research_complete",
                step_status="completed",
                output_data=final_result
            )
            
            return final_result
            
        except Exception as e:
            # 处理错误
            error_msg = f"研究过程中发生错误: {str(e)}"
            self.state_manager.fail_task(error_msg)
            
            # Debug: 记录错误
            self.debug_logger.log_error(
                error_type="ResearchError",
                error_message=error_msg,
                context={
                    "user_query": user_query,
                    "max_search_rounds": max_search_rounds,
                    "effort_level": effort_level
                },
                stacktrace=traceback.format_exc()
            )
            
            self.debug_logger.log_workflow_step(
                step_name="research_failed",
                step_status="failed",
                output_data={"error": error_msg}
            )
            
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
            estimated_steps = len(workflow.steps_config)  # 使用步骤配置数量
            
            print(f"🔍 工作流详情: 类型={task_type}, 复杂度={complexity}, 实际步骤={estimated_steps}")
            print(f"🔍 步骤列表: {[step['name'] for step in workflow.steps_config]}")
            
            self._notify_step(f"任务类型: {task_type} (复杂度: {complexity})")
            self._notify_progress(f"工作流构建完成，预计{estimated_steps}步", 30)
            
            return workflow
            
        except Exception as e:
            error_msg = f"工作流构建失败: {str(e)}"
            self._notify_step(error_msg)
            print(f"❌ 工作流构建异常: {e}")
            
            # 创建一个简单的降级工作流
            return self._create_fallback_workflow()
    
    def _create_fallback_workflow(self) -> DynamicWorkflow:
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
        steps_config = [
            {"name": "simple_search", "description": "执行简单的网络搜索"},
            {"name": "generate_final_answer", "description": "生成最终答案"}
        ]
        return DynamicWorkflow(workflow_config, steps_config)
    
    def _adjust_workflow_by_effort(self, workflow: DynamicWorkflow, effort_level: str):
        """根据努力级别调整工作流参数（参考原始frontend规格）"""
        # 参考原始frontend: 
        # Low: initial_search_query_count=1, max_research_loops=1
        # Medium: initial_search_query_count=3, max_research_loops=3  
        # High: initial_search_query_count=5, max_research_loops=10
        
        # 强制覆盖AI分析的复杂度，以用户选择的effort为准
        if effort_level == "low":
            workflow.config["complexity"] = "Low"
            workflow.config["estimated_steps"] = 4
            workflow.config["estimated_time"] = "1-5分钟"
            workflow.config["max_search_rounds"] = 3  # 低强度：最多3轮搜索（包括补充）
            workflow.config["default_search_rounds"] = 1  # 默认1轮，不足时补充
            workflow.config["queries_per_round"] = 3  # 每轮3个查询
            self.state_manager.update_settings(
                max_search_results=15,
                max_iterations=3,
                search_timeout=30
            )
        elif effort_level == "high":
            workflow.config["complexity"] = "High"  
            workflow.config["estimated_steps"] = 8
            workflow.config["estimated_time"] = "8-20分钟"
            workflow.config["max_search_rounds"] = 5  # 高强度：5轮搜索
            workflow.config["default_search_rounds"] = 5
            workflow.config["queries_per_round"] = 10  # 每轮10个查询
            self.state_manager.update_settings(
                max_search_results=50,
                max_iterations=5,
                search_timeout=60
            )
        else:  # medium
            workflow.config["complexity"] = "Medium"
            workflow.config["estimated_steps"] = 6
            workflow.config["estimated_time"] = "4-10分钟"
            workflow.config["max_search_rounds"] = 3  # 中等强度：3轮搜索
            workflow.config["default_search_rounds"] = 3
            workflow.config["queries_per_round"] = 5  # 每轮5个查询
            self.state_manager.update_settings(
                max_search_results=25,
                max_iterations=3,
                search_timeout=45
            )
        
        print(f"🎯 用户effort级别: {effort_level} → 复杂度: {workflow.config['complexity']}, 最大搜索轮数: {workflow.config['max_search_rounds']}")
    
    def _inject_research_functions(self, workflow: DynamicWorkflow):
        """将实际的研究函数注入到工作流步骤中"""
        
        function_mapping = {
            "generate_search_queries": self._generate_search_queries_step,
            "execute_search": self._execute_search_step,
            "analyze_search_results": self._analyze_search_results_step,
            "supplementary_search": self._supplementary_search_step,
            "generate_final_answer": self._generate_final_answer_step,
            "simple_search": self._simple_search_step,
        }

        # 替换 workflow.steps 为绑定了函数的完整 WorkflowStep 实例
        injected_steps = []
        for step_config in workflow.steps_config:
            step_name = step_config["name"]
            if step_name in function_mapping:
                step_function = function_mapping[step_name]
                injected_steps.append(WorkflowStep(
                    name=step_name,
                    description=step_config["description"],
                    function=step_function
                ))
            else:
                raise ValueError(f"未找到工作流步骤 '{step_name}' 对应的实现函数")
        
        workflow.steps = injected_steps
    
    async def _execute_workflow(self, workflow: DynamicWorkflow, 
                               user_query: str, max_search_rounds: int, num_search_queries: int = 3) -> Dict[str, Any]:
        """执行工作流，包含可能的多轮研究"""
        
        # 使用工作流配置中的max_search_rounds，如果没有则使用传入的参数
        effective_max_rounds = workflow.config.get("max_search_rounds", max_search_rounds)
        
        context = {
            "user_query": user_query,
            "max_search_rounds": effective_max_rounds,
            "num_search_queries": num_search_queries,
            "queries_per_round": workflow.config.get("queries_per_round", num_search_queries),
            "effort_level": workflow.config.get("complexity", "Medium").lower()
        }
        
        print(f"🔄 执行工作流，最大搜索轮数: {effective_max_rounds}")
        
        # 执行初始步骤，直到需要循环的"补充搜索"或"最终答案"
        for step in workflow.steps:
            if step.name == "supplementary_search":
                self._notify_step(f"✅ 初始搜索阶段完成，准备进入补充搜索循环")
                break # 结束初始步骤的执行，但不跳过simple_search
            elif step.name == "generate_final_answer":
                # 如果是最后一步，在循环外单独处理
                self._notify_step(f"✅ 所有搜索步骤完成，准备生成最终答案")
                break
            
            self._notify_step(f"🔄 执行步骤: {step.name}")
            
            # Debug: 记录步骤开始
            step_start_time = time.time()
            self.debug_logger.log_workflow_step(
                step_name=step.name,
                step_status="running",
                input_data=context
            )
            
            try:
                result = await self._execute_step_with_context(step, context)
                context.update(result)
                
                # Debug: 记录步骤完成
                step_duration = time.time() - step_start_time
                self.debug_logger.log_workflow_step(
                    step_name=step.name,
                    step_status="completed",
                    input_data=context,
                    output_data=result,
                    duration=step_duration
                )
                
                self._notify_step(f"✅ 步骤 {step.name} 完成 [{step_duration:.2f}s]")
                
            except Exception as e:
                # Debug: 记录步骤失败
                step_duration = time.time() - step_start_time
                self.debug_logger.log_workflow_step(
                    step_name=step.name,
                    step_status="failed",
                    input_data=context,
                    duration=step_duration,
                    error_message=str(e)
                )
                raise
            
        # 如果定义了补充搜索，则进入循环（所有强度都支持补充搜索）
        supplementary_search_step = next((s for s in workflow.steps if s.name == "supplementary_search"), None)
        if supplementary_search_step:
            current_round = 1
            default_rounds = workflow.config.get("default_search_rounds", 1)
            
            # Debug: 记录补充搜索循环开始
            self.debug_logger.log_execution_flow(
                flow_type="supplementary_search_loop",
                description=f"开始补充搜索循环，默认轮数: {default_rounds}, 最大轮数: {effective_max_rounds}",
                details={
                    "default_rounds": default_rounds,
                    "max_rounds": effective_max_rounds,
                    "effort_level": context.get("effort_level", "medium")
                }
            )
            
            while current_round < effective_max_rounds:
                # 检查停止信号
                if self._stop_research:
                    self._notify_step("🛑 收到停止指令，终止补充搜索")
                    break
                
                # 如果已经达到默认轮数，检查信息是否充足
                if current_round >= default_rounds:
                    is_sufficient = context.get("is_sufficient", False)
                    
                    # Debug: 记录信息充足性检查
                    self.debug_logger.log_decision_point(
                        decision_type="information_sufficiency_check",
                        condition=f"current_round({current_round}) >= default_rounds({default_rounds})",
                        result=f"is_sufficient: {is_sufficient}",
                        context={
                            "current_round": current_round,
                            "default_rounds": default_rounds,
                            "is_sufficient": is_sufficient
                        }
                    )
                    
                    if is_sufficient:
                        self._notify_step("✅ 信息已充足，跳过后续补充研究")
                        break
                    else:
                        # 对于低强度，在第2轮后更严格地检查是否停止
                        effort_level = context.get("effort_level", "medium")
                        if effort_level == "low" and current_round >= 2:
                            total_content = sum(len(content) for content in self.state_manager.get_search_content_list())
                            
                            # Debug: 记录低强度特殊检查
                            self.debug_logger.log_decision_point(
                                decision_type="low_effort_content_check",
                                condition=f"effort_level=low AND current_round({current_round})>=2 AND total_content({total_content})>800",
                                result=f"stop_search: {total_content > 800}",
                                context={
                                    "effort_level": effort_level,
                                    "current_round": current_round,
                                    "total_content": total_content,
                                    "threshold": 800
                                }
                            )
                            
                            if total_content > 800:  # 低强度的更宽松条件
                                self._notify_step("✅ 低强度模式：信息量已足够，停止补充搜索")
                                break
                        
                        # 对于所有强度，在第3轮后强制检查
                        if current_round >= 3:
                            total_content = sum(len(content) for content in self.state_manager.get_search_content_list())
                            
                            # Debug: 记录强制检查
                            self.debug_logger.log_decision_point(
                                decision_type="force_content_check",
                                condition=f"current_round({current_round})>=3 AND total_content({total_content})>1200",
                                result=f"force_stop: {total_content > 1200}",
                                context={
                                    "effort_level": effort_level,
                                    "current_round": current_round,
                                    "total_content": total_content,
                                    "threshold": 1200
                                }
                            )
                            
                            if total_content > 1200:  # 强制停止条件
                                self._notify_step("✅ 信息量充足，强制停止补充搜索")
                                break
                        self._notify_step(f"ℹ️ 已完成默认{default_rounds}轮搜索，但信息不足，继续补充搜索...")
                
                # 计算当前轮次的进度
                base_progress = 60  # 初始搜索完成后的进度
                round_progress = base_progress + (current_round * 15)  # 每轮增加15%
                
                self._notify_step(f"🔄 第 {current_round+1}/{effective_max_rounds} 轮补充研究开始...")
                self._notify_progress(f"执行第 {current_round+1} 轮补充搜索", round_progress)
                
                # 执行补充搜索，传递轮次信息
                context["current_round"] = current_round + 1
                context["total_rounds"] = effective_max_rounds
                context["default_rounds"] = default_rounds
                context["queries_per_round"] = workflow.config.get("queries_per_round", num_search_queries)
                result = await self._execute_step_with_context(supplementary_search_step, context)
                context.update(result)
                
                # 再次分析结果
                analyze_step = next((s for s in workflow.steps if s.name == "analyze_search_results"), None)
                if analyze_step:
                    context["search_round"] = current_round  # 传递搜索轮次给分析步骤
                    context["effort_level"] = context.get("effort_level", "medium")  # 确保传递effort_level
                    analysis_result = await self._execute_step_with_context(analyze_step, context)
                    context.update(analysis_result)

                current_round += 1
            
            # 如果达到最大轮数但信息仍不充足
            if current_round >= effective_max_rounds and not context.get("is_sufficient"):
                self._notify_step(f"⚠️ 已达到最大搜索轮数({effective_max_rounds})，停止补充搜索")

        # 循环结束，执行最终的答案生成
        final_answer_step = next((s for s in workflow.steps if s.name == "generate_final_answer"), None)
        if final_answer_step:
            final_result = await self._execute_step_with_context(final_answer_step, context)
            context.update(final_result)
        else:
            raise ValueError("工作流中未定义 'generate_final_answer' 步骤")
        
        return context
    
    async def _execute_step_with_context(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行工作流步骤并返回结果"""
        return await step.execute(context)
    
    async def _generate_search_queries_step(self, **kwargs) -> Dict[str, Any]:
        """生成搜索查询步骤"""
        user_query = kwargs.get("user_query", "")
        # 优先使用workflow配置的查询数量
        workflow_queries = kwargs.get("queries_per_round")
        num_queries = workflow_queries or kwargs.get("num_search_queries", kwargs.get("num_queries", 3))
        
        self._notify_step(f"正在生成 {num_queries} 个搜索查询...")
        
        # Debug: 记录API请求
        request_id = f"gen_queries_{int(time.time() * 1000)}"
        self.debug_logger.log_api_request(
            request_type="generate_search_queries",
            model=self.model_config.search_model,
            prompt=f"为用户查询生成{num_queries}个搜索查询: {user_query}",
            request_id=request_id,
            context="生成搜索查询"
        )
        
        queries = await self.search_agent.generate_search_queries(user_query, num_queries)
        
        # Debug: 记录API响应
        self.debug_logger.log_api_response(
            request_id=request_id,
            response_text=f"生成了{len(queries)}个查询: {queries}"
        )
        
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
            
            # Debug: 记录搜索请求
            search_request_id = f"search_{i}_{int(time.time() * 1000)}"
            self.debug_logger.log_api_request(
                request_type="grounding_search",
                model=self.model_config.search_model,
                prompt=f"搜索查询: {query}",
                request_id=search_request_id,
                context=f"搜索查询 {i+1}/{len(search_queries)}"
            )
            
            result = await self.search_agent.search_with_grounding(query)
            
            # Debug: 记录搜索结果
            self.debug_logger.log_search_result(query, result, "grounding")
            
            # Debug: 记录搜索响应
            if result.get("success"):
                response_summary = f"成功获取内容，长度: {len(result.get('content', ''))}, 引用数: {len(result.get('citations', []))}"
            else:
                response_summary = f"搜索失败: {result.get('error', '未知错误')}"
            
            self.debug_logger.log_api_response(
                request_id=search_request_id,
                response_text=response_summary,
                metadata={
                    "success": result.get("success", False),
                    "content_length": len(result.get("content", "")),
                    "citations_count": len(result.get("citations", [])),
                    "urls_count": len(result.get("urls", []))
                },
                error=None if result.get("success") else result.get("error", "搜索失败")
            )
            
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
        current_round = kwargs.get("current_round", search_round + 1)
        total_rounds = kwargs.get("total_rounds", kwargs.get("max_search_rounds", 3))
        
        self._notify_step(f"🤔 分析第 {current_round} 轮搜索结果，判断是否需要继续...")
        self._notify_progress(f"分析第 {current_round} 轮结果", 70 + ((current_round - 1) * 10))
        
        # 获取所有已搜索的内容用于反思分析
        all_research_results = self.state_manager.get_search_content_list()
        
        # 使用AI进行反思分析（参考原始backend的reflection函数）
        from utils.prompts import PromptTemplates
        
        reflection_prompt = f"""分析以下研究内容，判断是否需要进一步搜索：

研究主题: {user_query}
当前搜索轮数: {current_round}
最大搜索轮数: {total_rounds}

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
                
                # Debug: 记录反思分析API请求
                reflection_request_id = f"reflection_{current_round}_{int(time.time() * 1000)}"
                self.debug_logger.log_api_request(
                    request_type="reflection_analysis",
                    model=reflection_model,
                    prompt=reflection_prompt,
                    request_id=reflection_request_id,
                    context=f"第{current_round}轮反思分析"
                )
                
                response = self.search_agent.client.models.generate_content(
                    model=reflection_model,
                    contents=reflection_prompt,
                    config={
                        "temperature": 0.3,
                        "max_output_tokens": max_tokens
                    }
                )
                
                # Debug: 记录反思分析API响应
                self.debug_logger.log_api_response(
                    request_id=reflection_request_id,
                    response_text=response.text
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
                effort_level = kwargs.get("effort_level", "medium")
                
                # 根据强度和轮次调整阈值
                if effort_level == "low":
                    content_threshold = 800 if current_round >= 2 else 1200
                elif effort_level == "medium":
                    content_threshold = 1500 if current_round >= 2 else 2000
                else:  # high
                    content_threshold = 2000 if current_round >= 3 else 2500
                
                reflection_result = {
                    "is_sufficient": total_content > content_threshold or current_round >= total_rounds,
                    "knowledge_gap": "信息充足" if total_content > content_threshold else "需要更多详细信息",
                    "follow_up_queries": [] if total_content > content_threshold else [f"{user_query} 详细分析"]
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
                effort_level = kwargs.get("effort_level", "medium")
                
                # 错误情况下使用更宽松的阈值
                if effort_level == "low":
                    content_threshold = 600 if current_round >= 2 else 1000
                elif effort_level == "medium":
                    content_threshold = 1000 if current_round >= 2 else 1500
                else:  # high
                    content_threshold = 1500 if current_round >= 3 else 2000
                
                reflection_result = {
                    "is_sufficient": total_content > content_threshold or current_round >= total_rounds,
                    "knowledge_gap": "分析失败，使用简单判断",
                    "follow_up_queries": [] if total_content > content_threshold else [f"{user_query} 补充信息"]
                }
        
        # 显示分析结果
        is_sufficient = reflection_result.get("is_sufficient", False)
        knowledge_gap = reflection_result.get("knowledge_gap", "")
        
        if is_sufficient:
            self._notify_step(f"✅ 第 {current_round} 轮分析完成：信息充足，准备生成最终答案")
        else:
            self._notify_step(f"⚠️ 第 {current_round} 轮分析完成：{knowledge_gap}")
            if current_round < total_rounds:
                self._notify_step(f"🔄 将进行第 {current_round + 1} 轮补充搜索")
        
        # 保存反思分析结果
        reflection_with_metadata = {
            **reflection_result,
            "search_round": current_round,
            "total_research_content": len(all_research_results),
            "content_analysis": f"已收集 {len(all_research_results)} 个搜索结果"
        }
        self.state_manager.add_reflection_result(reflection_with_metadata)
        
        # 如果是API配额耗尽导致的强制终止，标记API错误
        api_error = False
        if "配额耗尽" in knowledge_gap:
            api_error = True
        
        # 记录分析结果
        is_sufficient = reflection_result.get("is_sufficient", False)
        total_content_length = sum(len(content) for content in all_research_results)
        
        self._notify_step(f"📊 分析结果: {'信息充足' if is_sufficient else '需要补充搜索'}")
        self._notify_step(f"📈 当前信息量: {total_content_length} 字符, 轮次: {current_round}/{total_rounds}")
        
        if not is_sufficient and current_round < total_rounds:
            follow_up_queries = reflection_result.get("follow_up_queries", [])
            self._notify_step(f"🔍 计划补充搜索: {len(follow_up_queries)} 个查询")
        
        return {
            "analysis": reflection_result,
            "is_sufficient": is_sufficient,  # 这个字段很重要！
            "follow_up_queries": reflection_result.get("follow_up_queries", []),
            "current_round": current_round,
            "total_rounds": total_rounds,
            "api_error": api_error
        }
    
    async def _supplementary_search_step(self, **kwargs) -> Dict[str, Any]:
        """补充搜索步骤 - 基于上下文生成新的搜索查询"""
        analysis = kwargs.get("analysis", {})
        user_query = kwargs.get("user_query", "")
        search_round = kwargs.get("search_round", 0)
        current_round = kwargs.get("current_round", search_round + 1)
        total_rounds = kwargs.get("total_rounds", kwargs.get("max_search_rounds", 3))
        queries_per_round = kwargs.get("queries_per_round", 3)
        
        # 安全检查：防止无限循环
        if current_round > total_rounds:
            self._notify_step(f"⚠️ 已达到最大搜索轮数({total_rounds})，强制停止")
            return {"additional_results": [], "continue_search": False}
        
        # 检查是否需要继续搜索
        if analysis.get("is_sufficient", True):
            self._notify_step("✅ 信息已充足，跳过补充搜索")
            return {"additional_results": [], "continue_search": False}
        
        self._notify_step(f"🔍 第 {current_round}/{total_rounds} 轮补充搜索中...")
        
        # 获取之前轮次的搜索结果作为上下文
        previous_results = self.state_manager.get_successful_search_results()
        previous_context = ""
        if previous_results:
            context_summaries = []
            for result in previous_results[-5:]:  # 只取最近5个结果作为上下文
                if result.content:
                    context_summaries.append(f"已搜索: {result.query}\n结果摘要: {result.content[:200]}...")
            previous_context = "\n\n".join(context_summaries)
        
        # 基于上下文和分析结果生成新的搜索查询
        follow_up_queries = analysis.get("follow_up_queries", [])
        if not follow_up_queries and previous_context:
            # 如果没有明确的follow_up_queries，基于上下文生成
            self._notify_step("🤔 基于已有信息生成补充搜索查询...")
            try:
                from utils.prompts import PromptTemplates
                context_prompt = f"""
基于用户问题: {user_query}

已有搜索结果:
{previous_context}

分析结果显示信息不足。请生成{queries_per_round}个补充搜索查询，用于获取缺失的信息。
查询应该:
1. 与已有结果互补，避免重复
2. 针对具体的信息缺口
3. 使用不同的关键词和角度

请直接返回查询列表，每行一个查询。
"""
                
                if self.search_agent.client:
                    response = self.search_agent.client.models.generate_content(
                        model=self.model_config.get_model_for_task("search"),
                        contents=context_prompt,
                        config={"temperature": 0.7, "max_output_tokens": 500}
                    )
                    generated_queries = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
                    follow_up_queries = generated_queries[:queries_per_round]
                    
            except Exception as e:
                self._notify_step(f"⚠️ 自动生成查询失败，使用默认查询: {str(e)}")
        
        # 如果仍然没有查询，使用默认策略
        if not follow_up_queries:
            follow_up_queries = [
                f"{user_query} 详细分析",
                f"{user_query} 最新发展",
                f"{user_query} 相关案例"
            ][:queries_per_round]
        
        # 限制查询数量
        follow_up_queries = follow_up_queries[:queries_per_round]
        
        base_progress = 60 + ((current_round - 1) * 15)
        self._notify_progress(f"第 {current_round} 轮补充搜索", base_progress)
        
        additional_results = []
        
        # 执行所有补充查询
        for i, query in enumerate(follow_up_queries):
            query_progress = base_progress + (i * (10 // len(follow_up_queries)))
            self._notify_step(f"🔎 补充查询 {i+1}/{len(follow_up_queries)}: {query[:50]}...")
            self._notify_progress(f"执行补充查询 {i+1}", query_progress)
            
            try:
                # Debug: 记录补充搜索请求
                supp_request_id = f"supp_search_{current_round}_{i}_{int(time.time() * 1000)}"
                self.debug_logger.log_api_request(
                    request_type="supplementary_search",
                    model=self.model_config.search_model,
                    prompt=f"第{current_round}轮补充搜索: {query}",
                    request_id=supp_request_id,
                    context=f"第{current_round}轮补充搜索 {i+1}/{len(follow_up_queries)}"
                )
                
                result = await self.search_agent.search_with_grounding(query)
                
                # Debug: 记录补充搜索结果
                self.debug_logger.log_search_result(query, result, "supplementary")
                
                # Debug: 记录补充搜索响应
                if result.get("success"):
                    response_summary = f"补充搜索成功，内容长度: {len(result.get('content', ''))}, 引用数: {len(result.get('citations', []))}"
                else:
                    response_summary = f"补充搜索失败: {result.get('error', '未知错误')}"
                
                self.debug_logger.log_api_response(
                    request_id=supp_request_id,
                    response_text=response_summary,
                    metadata={
                        "round": current_round,
                        "query_index": i,
                        "success": result.get("success", False),
                        "content_length": len(result.get("content", "")),
                        "citations_count": len(result.get("citations", []))
                    },
                    error=None if result.get("success") else result.get("error", "补充搜索失败")
                )
                
                if result.get("success"):
                    self.state_manager.add_search_result(query, result)
                    
                    # 保存到分析过程，标明轮次和上下文关联
                    web_research_content = f"第{current_round}轮补充查询: {query}\n内容: {result.get('content', '')}"
                    if result.get('citations'):
                        citations_list = result.get('citations', []) or []
                        citations_text = "\n".join([f"- {cite.get('title', 'Unknown Source')}: {cite.get('url', '#')}" 
                                                   for cite in citations_list[:3]])
                        web_research_content += f"\n引用:\n{citations_text}"
                    self.state_manager.add_web_research_result(web_research_content)
                    
                    additional_results.append(result)
                    self._notify_step(f"✅ 补充查询 {i+1} 完成")
                    
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
                        "current_round": current_round,
                        "total_rounds": total_rounds,
                        "api_error": True
                    }
                else:
                    self._notify_step(f"❌ 补充搜索失败: {str(e)}")
            
            # 添加延迟避免速率限制
            time.sleep(1)
        
        self._notify_step(f"🎯 第 {current_round} 轮补充搜索完成，共获得 {len(additional_results)} 个结果")
        
        return {
            "additional_results": additional_results,
            "continue_search": True,
            "current_round": current_round,
            "total_rounds": total_rounds
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
        
        # 在调用模型之前再次通知，让用户知道正在进行耗时操作
        self._notify_step(f"调用最终模型({self.model_config.answer_model})生成报告，请耐心等待...")
        
        try:
            # 使用SearchAgent的客户端来生成答案，但使用answer_model
            if self.search_agent.client:
                self._notify_step("正在调用AI模型生成详细答案...")
                self._notify_progress("AI正在生成答案，请耐心等待...", 92)
                
                answer_model = self.model_config.get_model_for_task("answer")
                max_tokens = self.model_config.get_token_limits("answer")
                
                self._notify_step(f"使用模型: {answer_model}, Token限制: {max_tokens}")
                
                # Debug: 记录最终答案生成API请求
                answer_request_id = f"final_answer_{int(time.time() * 1000)}"
                self.debug_logger.log_api_request(
                    request_type="final_answer_generation",
                    model=answer_model,
                    prompt=synthesis_prompt,
                    request_id=answer_request_id,
                    context="生成最终答案"
                )
                
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
                
                # Debug: 记录最终答案生成API响应
                self.debug_logger.log_api_response(
                    request_id=answer_request_id,
                    response_text=final_answer
                )
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
        
    async def close_clients(self):
        """关闭所有客户端连接"""
        try:
            if hasattr(self.search_agent.client, 'close'):
                await self.search_agent.client.close()
        except Exception as e:
            print(f"关闭客户端时出错: {e}")
    
    @classmethod
    def create_with_config(cls, api_key: str, **config) -> "ResearchEngine":
        """使用配置创建研究引擎实例"""
        model_name = config.get("model_name", "gemini-2.0-flash")
        engine = cls(api_key, model_name)
        
        # 设置其他配置
        if "max_search_rounds" in config:
            engine._max_search_rounds = config["max_search_rounds"]
        if "effort_level" in config:
            engine._effort_level = config["effort_level"]
        
        return engine 