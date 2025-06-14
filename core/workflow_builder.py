"""
动态工作流构建器
基于任务分析自动构建最优工作流
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from typing import Optional
from .api_factory import APIClientFactory
from .api_client import BaseAPIClient, APIResponse
from .api_config import APIConfig, APIMode
from utils.prompts import PromptTemplates
from utils.helpers import extract_json_from_text, safe_json_loads


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
    """动态工作流"""
    
    def __init__(self, workflow_config: Dict[str, Any], steps_config: List[Dict[str, str]]):
        self.config = workflow_config
        self.steps_config = steps_config
        self.steps = []
        self.current_step_index = 0
        self.context = {}
        self.start_time = None
        self.end_time = None
        self.status = "ready"  # ready, running, completed, failed
    
    def add_step(self, step: WorkflowStep):
        """添加步骤"""
        self.steps.append(step)
    
    async def execute(self, initial_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行工作流"""
        self.status = "running"
        self.start_time = datetime.now()
        self.context = initial_context or {}
        
        try:
            for i, step_config in enumerate(self.steps_config):
                self.current_step_index = i
                
                # 更新上下文
                self.context["current_step"] = step_config["name"]
                self.context["step_index"] = i
                self.context["total_steps"] = len(self.steps_config)
                
                # 执行步骤
                step_result = await self._execute_step(step_config, self.context)
                
                # 更新上下文
                if isinstance(step_result, dict):
                    self.context.update(step_result)
                else:
                    self.context[f"step_{i}_result"] = step_result
            
            self.status = "completed"
            self.end_time = datetime.now()
            
            return self.context
            
        except Exception as e:
            self.status = "failed"
            self.end_time = datetime.now()
            raise e
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        completed_steps = len([s for s in self.steps if s.status == "completed"])
        failed_steps = len([s for s in self.steps if s.status == "failed"])
        
        return {
            "total_steps": len(self.steps_config),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "current_step": self.current_step_index,
            "progress_percentage": (completed_steps / len(self.steps_config)) * 100 if self.steps_config else 0,
            "status": self.status,
            "elapsed_time": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }

    async def _execute_step(self, step_config: Dict[str, str], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤"""
        step_name = step_config["name"]
        step_description = step_config["description"]
        
        print(f"开始执行步骤: {step_name} - {step_description}")
        
        # 创建步骤实例
        step = WorkflowStep(step_name, step_description, self._get_step_function(step_name), **context)
        
        try:
            # 执行步骤
            step_result = await step.execute(context)
            
            print(f"步骤 {step_name} 执行完成")
            return step_result
            
        except Exception as e:
            print(f"步骤 {step_name} 执行失败: {e}")
            raise e

    def _get_step_function(self, step_name: str) -> Callable:
        """获取步骤函数"""
        # 实现步骤函数获取逻辑
        # 这里需要根据步骤名称返回相应的函数
        # 可以使用字典或其他数据结构来映射步骤名称到函数
        # 这里只是一个示例，实际实现需要根据具体情况来确定
        return lambda **kwargs: {}  # 临时返回，实际实现需要根据具体情况来确定


class DynamicWorkflowBuilder:
    """动态工作流构建器 - 支持双模式API"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash-preview-05-20", preferred_mode: Optional[APIMode] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.preferred_mode = preferred_mode
        
        # 使用工厂创建客户端
        self.client = APIClientFactory.create_analysis_client(
            api_key=api_key,
            model_name=model_name,
            preferred_mode=preferred_mode
        )
        
        # 打印客户端信息
        client_info = APIClientFactory.get_client_info(model_name)
        print(f"🏗️ 工作流构建器初始化:")
        print(f"  模型: {model_name}")
        print(f"  模式: {client_info.get('mode', 'unknown')}")
    
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
            
            # 使用统一的客户端接口
            response = await self.client.generate_content(
                prompt=prompt_content,
                temperature=0.1,
                max_tokens=4096
            )
            
            print("API调用完成，解析响应...")
            
            if response.success and response.text:
                print(f"收到响应: {response.text[:200]}...")
                analysis = extract_json_from_text(response.text)
                if analysis:
                    print("任务分析成功")
                    return analysis
                else:
                    print("JSON解析失败，使用默认分析")
            else:
                print(f"API调用失败或空响应: {response.error if response.error else '未知错误'}，使用默认分析")
            
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
            workflow_config=analysis,
            steps_config=steps_config  # 保存步骤配置，而不是实例
        )
        
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