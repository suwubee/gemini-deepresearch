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
        step = WorkflowStep(step_name, step_function, description)
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


class DynamicWorkflowBuilder:
    """动态工作流构建器"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        
        if GeminiApiClient:
            self.client = GeminiApiClient(api_key=api_key)
    
    async def analyze_task_and_build_workflow(self, user_query: str) -> DynamicWorkflow:
        """
        分析用户任务并构建动态工作流
        
        Args:
            user_query: 用户查询
            
        Returns:
            构建好的工作流
        """
        # 1. 分析任务类型
        task_analysis = await self._analyze_task_type(user_query)
        
        # 2. 基于分析结果构建工作流
        workflow = self._build_workflow_from_analysis(task_analysis, user_query)
        
        return workflow
    
    async def _analyze_task_type(self, user_query: str) -> Dict[str, Any]:
        """分析任务类型"""
        print(f"开始分析任务类型: {user_query[:50]}...")
        
        if not self.client:
            print("没有可用的客户端，使用默认分析")
            return self._get_default_task_analysis(user_query)
        
        try:
            print("生成任务分析提示词...")
            prompt = PromptTemplates.task_analysis_prompt(user_query)
            
            print("调用Gemini API进行任务分析...")
            
            # 确保prompt是UTF-8编码的字符串
            if isinstance(prompt, str):
                prompt_content = prompt.encode('utf-8').decode('utf-8')
            else:
                prompt_content = str(prompt)
            
            # 使用模型配置获取合适的模型和token限制
            from core.model_config import get_model_config
            model_config = get_model_config()
            task_model = model_config.get_model_for_task("task_analysis")
            max_tokens = model_config.get_token_limits("task_analysis")
            
            response = self.client.generate_content(
                model_name=task_model,
                prompt=prompt_content,
                temperature=0.1,
                max_output_tokens=max_tokens,
            )
            
            print("API调用完成，解析响应...")
            
            if response and response.text:
                print(f"收到响应: {response.text[:200]}...")
                analysis = extract_json_from_text(response.text)
                if analysis:
                    print("任务分析成功")
                    return analysis
                else:
                    print("JSON解析失败，使用默认分析")
            else:
                print("空响应，使用默认分析")
            
        except Exception as e:
            print(f"任务分析失败: {e}，使用默认分析")
        
        return self._get_default_task_analysis(user_query)
    
    def _get_default_task_analysis(self, user_query: str) -> Dict[str, Any]:
        """获取默认任务分析（当AI分析失败时的fallback）"""
        print(f"Fallback: 使用默认深度研究模式用于查询: {user_query}")
        
        # 简单fallback - 默认使用深度研究模式
        return {
            "task_type": "Deep Research",
            "complexity": "Medium", 
            "requires_search": True,
            "requires_multiple_rounds": True,
            "estimated_steps": 5,
            "estimated_time": "3-8 minutes",
            "reasoning": "Default fallback to comprehensive research mode"
        }
    
    def _build_workflow_from_analysis(self, analysis: Dict[str, Any], user_query: str) -> DynamicWorkflow:
        """基于分析结果构建工作流"""
        # 根据分析结果构建工作流步骤
        steps_config = self._create_workflow_steps(analysis)
        
        workflow = DynamicWorkflow(
            workflow_id=f"wf_{int(time.time())}",
            analysis=analysis
        )
        
        for step_config in steps_config:
            workflow.add_step(step_config["name"], self._get_step_function(step_config["name"]), step_config["description"])
        
        return workflow

    def _create_workflow_steps(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """根据分析创建工作流步骤的配置"""
        steps = []
        task_type = analysis.get("task_type", "问答系统")
        requires_search = analysis.get("requires_search", True)

        # 支持中英文的深度研究类型判断
        if (task_type in ["深度研究", "Deep Research"] and requires_search):
            steps.extend([
                {"name": "generate_search_queries", "description": "生成初步搜索查询"},
                {"name": "execute_search", "description": "执行初步网络搜索"},
                {"name": "analyze_search_results", "description": "分析搜索结果并进行反思"},
                {"name": "supplementary_search", "description": "根据反思进行补充搜索"},
            ])
        elif requires_search:
            steps.extend([
                {"name": "simple_search", "description": "执行简单的网络搜索"},
            ])
        
        # 所有工作流都有最终的答案生成步骤
        steps.append({"name": "generate_final_answer", "description": "生成最终答案"})
        
        return steps
    
    def _get_step_function(self, step_name: str) -> Callable:
        """获取步骤函数"""
        # 实现步骤函数获取逻辑
        # 这里需要根据步骤名称返回相应的函数
        # 可以使用字典或其他数据结构来映射步骤名称到函数
        # 这里只是一个示例，实际实现需要根据具体情况来确定
        return lambda **kwargs: {}  # 临时返回，实际实现需要根据具体情况来确定

    def _build_research_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """构建研究工作流"""
        workflow.add_step(WorkflowStep(
            "生成搜索查询",
            "基于用户问题生成多个搜索查询",
            self._generate_search_queries_step,
            user_query=user_query,
            num_queries=3
        ))
        
        workflow.add_step(WorkflowStep(
            "执行搜索",
            "执行搜索获取相关信息",
            self._execute_search_step
        ))
        
        workflow.add_step(WorkflowStep(
            "分析搜索结果",
            "分析搜索结果，识别信息缺口",
            self._analyze_search_results_step,
            user_query=user_query
        ))
        
        workflow.add_step(WorkflowStep(
            "补充搜索",
            "基于信息缺口进行补充搜索",
            self._supplementary_search_step
        ))
        
        workflow.add_step(WorkflowStep(
            "生成最终答案",
            "整合所有信息生成完整答案",
            self._generate_final_answer_step,
            user_query=user_query
        ))
    
    def _build_qa_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """构建问答工作流"""
        workflow.add_step(WorkflowStep(
            "搜索",
            "搜索相关信息",
            self._simple_search_step,
            user_query=user_query
        ))
        
        workflow.add_step(WorkflowStep(
            "生成答案",
            "基于搜索结果生成答案",
            self._generate_simple_answer_step,
            user_query=user_query
        ))
    
    def _build_coding_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """构建编程工作流"""
        workflow.add_step(WorkflowStep(
            "分析需求",
            "分析编程需求和技术要求",
            self._analyze_coding_requirements_step,
            user_query=user_query
        ))
        
        workflow.add_step(WorkflowStep(
            "搜索技术信息",
            "搜索相关技术文档和示例",
            self._search_technical_info_step
        ))
        
        workflow.add_step(WorkflowStep(
            "生成代码",
            "基于需求和技术信息生成代码",
            self._generate_code_step,
            user_query=user_query
        ))
    
    def _build_data_analysis_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """构建数据分析工作流"""
        workflow.add_step(WorkflowStep(
            "分析数据需求",
            "分析数据分析需求",
            self._analyze_data_requirements_step,
            user_query=user_query
        ))
        
        workflow.add_step(WorkflowStep(
            "搜索数据源",
            "搜索相关数据源和方法",
            self._search_data_sources_step
        ))
        
        workflow.add_step(WorkflowStep(
            "生成分析方案",
            "生成数据分析方案",
            self._generate_analysis_plan_step,
            user_query=user_query
        ))
    
    def _build_writing_workflow(self, workflow: DynamicWorkflow, user_query: str, analysis: Dict):
        """构建写作工作流"""
        workflow.add_step(WorkflowStep(
            "创建大纲",
            "根据主题创建写作大纲",
            self._create_outline_step,
            user_query=user_query
        ))
        
        workflow.add_step(WorkflowStep(
            "收集素材",
            "搜索和收集相关素材",
            self._collect_materials_step
        ))
        
        workflow.add_step(WorkflowStep(
            "生成文档",
            "基于大纲和素材生成完整文档",
            self._generate_document_step,
            user_query=user_query
        ))
    
    # 占位符方法 - 这些方法将在 ResearchEngine 中被实际实现替换
    async def _generate_search_queries_step(self, **kwargs):
        return {"queries": [kwargs.get("user_query", "")]}
    
    async def _execute_search_step(self, **kwargs):
        return {"search_results": []}
    
    async def _analyze_search_results_step(self, **kwargs):
        return {"analysis": "分析完成"}
    
    async def _supplementary_search_step(self, **kwargs):
        return {"additional_results": []}
    
    async def _generate_final_answer_step(self, **kwargs):
        return {"final_answer": "答案生成完成"}
    
    async def _simple_search_step(self, **kwargs):
        return {"search_result": "搜索完成"}
    
    async def _generate_simple_answer_step(self, **kwargs):
        return {"answer": "答案生成完成"}
    
    async def _analyze_coding_requirements_step(self, **kwargs):
        return {"requirements": "需求分析完成"}
    
    async def _search_technical_info_step(self, **kwargs):
        return {"technical_info": "技术信息搜索完成"}
    
    async def _generate_code_step(self, **kwargs):
        return {"code": "代码生成完成"}
    
    async def _analyze_data_requirements_step(self, **kwargs):
        return {"data_requirements": "数据需求分析完成"}
    
    async def _search_data_sources_step(self, **kwargs):
        return {"data_sources": "数据源搜索完成"}
    
    async def _generate_analysis_plan_step(self, **kwargs):
        return {"analysis_plan": "分析方案生成完成"}
    
    async def _create_outline_step(self, **kwargs):
        return {"outline": "大纲创建完成"}
    
    async def _collect_materials_step(self, **kwargs):
        return {"materials": "素材收集完成"}
    
    async def _generate_document_step(self, **kwargs):
        return {"document": "文档生成完成"} 