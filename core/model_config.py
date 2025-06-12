"""
模型配置管理
参考原始backend/src/agent/configuration.py的设计
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfiguration:
    """模型配置类，参考原始backend设计"""
    
    # 搜索相关模型 - 固定使用gemini-2.0-flash（确保有搜索功能）
    search_model: str = "gemini-2.0-flash"
    query_generator_model: str = "gemini-2.0-flash"
    
    # 分析反思模型 - 使用最新2.5版本
    reflection_model: str = "gemini-2.5-flash-preview-05-20"
    
    # 最终答案生成模型 - 使用最新2.5 Pro版本
    answer_model: str = "gemini-2.5-pro-preview-06-05"
    
    # 任务分析模型 - 使用最新2.5版本
    task_analysis_model: str = "gemini-2.5-flash-preview-05-20"
    
    # 初始查询数量配置（参考原始frontend规格）
    number_of_initial_queries: int = 3
    
    # 最大研究循环数（参考原始backend）
    max_research_loops: int = 2
    
    def __post_init__(self):
        """后处理，确保搜索模型固定"""
        # 强制确保搜索相关功能使用gemini-2.0-flash
        self.search_model = "gemini-2.0-flash"
        self.query_generator_model = "gemini-2.0-flash"
    
    @classmethod
    def from_user_model(cls, user_model: str) -> "ModelConfiguration":
        """根据用户选择的模型创建配置"""
        config = cls()
        
        # 搜索模型保持固定
        config.search_model = "gemini-2.0-flash"
        config.query_generator_model = "gemini-2.0-flash"
        
        # 其他功能使用用户选择的模型
        config.reflection_model = user_model
        config.answer_model = user_model
        config.task_analysis_model = user_model
        
        return config
    
    @classmethod
    def get_default_config(cls) -> "ModelConfiguration":
        """获取默认配置（参考原始backend）"""
        return cls(
            search_model="gemini-2.0-flash",
            query_generator_model="gemini-2.0-flash", 
            reflection_model="gemini-2.5-flash-preview-05-20",
            answer_model="gemini-2.5-pro-preview-06-05",
            task_analysis_model="gemini-2.5-flash-preview-05-20"
        )
    
    def get_model_for_task(self, task_type: str) -> str:
        """根据任务类型获取对应模型"""
        task_model_map = {
            "search": self.search_model,
            "query_generation": self.query_generator_model,
            "reflection": self.reflection_model,
            "answer": self.answer_model,
            "task_analysis": self.task_analysis_model,
        }
        
        return task_model_map.get(task_type, self.search_model)
    
    def get_token_limits(self, task_type: str) -> int:
        """根据任务类型获取token限制 - 大幅增加以防止截断"""
        # 大幅增加token限制，防止输出截断
        token_limits = {
            "search": 8192,          # 搜索结果可能很长
            "query_generation": 4096, # 查询生成
            "reflection": 8192,       # 反思分析需要更多token
            "answer": 32000,          # 最终答案需要大量token防止截断
            "task_analysis": 4096,    # 任务分析
        }
        
        return token_limits.get(task_type, 32000)


# 全局配置实例
model_config = ModelConfiguration.get_default_config()


def set_user_model(user_model: str):
    """设置用户选择的模型"""
    global model_config
    model_config = ModelConfiguration.from_user_model(user_model)


def get_model_config() -> ModelConfiguration:
    """获取当前模型配置"""
    return model_config 