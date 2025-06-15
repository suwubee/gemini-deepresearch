"""
模型配置管理
通用化设计，支持不同API提供商
"""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class ModelConfiguration:
    """通用模型配置类"""
    
    # 基础模型名称 - 将由API客户端映射到具体模型
    search_model: str = "default-search"
    query_generator_model: str = "default-search" 
    reflection_model: str = "default-fast"
    answer_model: str = "default-advanced"
    task_analysis_model: str = "default-fast"
    
    # API提供商
    api_provider: str = "gemini"  # "gemini" 或 "openai"
    
    # 配置参数
    number_of_initial_queries: int = 3
    max_research_loops: int = 2
    
    # 模型映射表 - 支持不同API提供商
    _model_mappings: Dict[str, Dict[str, str]] = None
    
    def __post_init__(self):
        """初始化模型映射"""
        if self._model_mappings is None:
            self._model_mappings = self._get_default_mappings()
    
    def _get_default_mappings(self) -> Dict[str, Dict[str, str]]:
        """获取默认的模型映射"""
        return {
            "gemini": {
                "default-search": "gemini-2.0-flash",
                "default-fast": "gemini-2.5-flash-preview-05-20", 
                "default-advanced": "gemini-2.5-pro-preview-06-05"
            },
            "openai": {
                "default-search": "gpt-4o",  # 未来OpenAI集成时使用
                "default-fast": "gpt-4o-mini",
                "default-advanced": "gpt-4o"
            }
        }
    
    def get_actual_model_name(self, logical_name: str) -> str:
        """将逻辑模型名映射到实际API模型名"""
        mappings = self._model_mappings.get(self.api_provider, {})
        return mappings.get(logical_name, logical_name)
    
    @classmethod
    def from_user_model(cls, user_model: str, api_provider: str = "gemini") -> "ModelConfiguration":
        """根据用户选择的模型创建配置"""
        config = cls(api_provider=api_provider)
        
        # 用户可以选择除搜索外的其他模型
        if user_model:
            # 搜索功能保持使用专门的搜索模型
            config.reflection_model = user_model
            config.answer_model = user_model  
            config.task_analysis_model = user_model
        
        return config
    
    @classmethod
    def get_default_config(cls, api_provider: str = "gemini") -> "ModelConfiguration":
        """获取默认配置"""
        return cls(api_provider=api_provider)
    
    def get_model_for_task(self, task_type: str) -> str:
        """根据任务类型获取对应的实际模型名"""
        task_model_map = {
            "search": self.search_model,
            "query_generation": self.query_generator_model,
            "reflection": self.reflection_model,
            "answer": self.answer_model,
            "task_analysis": self.task_analysis_model,
        }
        
        logical_name = task_model_map.get(task_type, self.search_model)
        return self.get_actual_model_name(logical_name)
    
    def get_token_limits(self, task_type: str) -> int:
        """根据任务类型获取token限制"""
        if self.api_provider == "gemini":
            token_limits = {
                "search": 8192,
                "query_generation": 4096,
                "reflection": 8192,
                "answer": 32000,
                "task_analysis": 4096,
            }
        elif self.api_provider == "openai":
            # OpenAI的token限制
            token_limits = {
                "search": 4096,
                "query_generation": 2048,
                "reflection": 4096,
                "answer": 16000,
                "task_analysis": 2048,
            }
        else:
            # 默认限制
            token_limits = {
                "search": 4096,
                "query_generation": 2048,
                "reflection": 4096,
                "answer": 8192,
                "task_analysis": 2048,
            }
        
        return token_limits.get(task_type, 4096)


# 全局配置实例
model_config = ModelConfiguration.get_default_config()


def set_user_model(user_model: str):
    """设置用户选择的模型"""
    global model_config
    if user_model:
        model_config = ModelConfiguration.from_user_model(user_model)
    else:
        model_config = ModelConfiguration.get_default_config()


def get_model_config() -> ModelConfiguration:
    """获取当前模型配置"""
    return model_config 