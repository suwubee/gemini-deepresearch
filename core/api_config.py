"""
API配置管理系统
支持双模式架构：google-genai SDK 和 OpenAI兼容 HTTP API
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class APIMode(Enum):
    """API模式枚举"""
    GENAI = "genai"
    OPENAI = "openai"
    AUTO = "auto"


@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str
    mode: APIMode
    supports_search: bool = False
    supports_tools: bool = False
    fallback_search: bool = False
    base_url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    default_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenAICompatibleConfig:
    """OpenAI兼容配置"""
    base_url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3


class APIConfig:
    """API配置管理器"""
    
    # 默认配置
    DEFAULT_MODE = APIMode.GENAI
    
    # 模型配置字典
    MODEL_CONFIGS = {
        # Gemini 模型
        "gemini-2.0-flash": ModelConfig(
            name="gemini-2.0-flash",
            mode=APIMode.AUTO,  # 可选择模式
            supports_search=True,
            supports_tools=True,
            fallback_search=True,
            default_params={
                "temperature": 0.1,
                "max_output_tokens": 8192
            }
        ),
        "gemini-2.5-flash": ModelConfig(
            name="gemini-2.5-flash",
            mode=APIMode.GENAI,
            supports_search=False,
            supports_tools=False,
            default_params={
                "temperature": 0.3,
                "max_output_tokens": 8192
            }
        ),
        "gemini-2.5-flash-preview-05-20": ModelConfig(
            name="gemini-2.5-flash-preview-05-20",
            mode=APIMode.GENAI,
            supports_search=False,
            supports_tools=False,
            default_params={
                "temperature": 0.3,
                "max_output_tokens": 8192
            }
        ),
        "gemini-2.5-pro": ModelConfig(
            name="gemini-2.5-pro",
            mode=APIMode.GENAI,
            supports_search=False,
            supports_tools=False,
            default_params={
                "temperature": 0.3,
                "max_output_tokens": 32000
            }
        ),
        "gemini-2.5-pro-preview-06-05": ModelConfig(
            name="gemini-2.5-pro-preview-06-05",
            mode=APIMode.GENAI,
            supports_search=False,
            supports_tools=False,
            default_params={
                "temperature": 0.3,
                "max_output_tokens": 32000
            }
        ),
        
        # OpenAI 模型示例
        "gpt-4": ModelConfig(
            name="gpt-4",
            mode=APIMode.OPENAI,
            supports_search=False,
            supports_tools=True,
            base_url="https://api.openai.com/v1",
            headers={"Content-Type": "application/json"},
            default_params={
                "temperature": 0.3,
                "max_tokens": 4096
            }
        ),
        "gpt-3.5-turbo": ModelConfig(
            name="gpt-3.5-turbo",
            mode=APIMode.OPENAI,
            supports_search=False,
            supports_tools=True,
            base_url="https://api.openai.com/v1",
            headers={"Content-Type": "application/json"},
            default_params={
                "temperature": 0.3,
                "max_tokens": 4096
            }
        )
    }
    
    # OpenAI兼容服务配置
    OPENAI_COMPATIBLE_CONFIGS = {
        "default": OpenAICompatibleConfig(
            base_url="https://api.openai.com/v1",
            headers={"Content-Type": "application/json"},
            timeout=30,
            retry_count=3
        ),
        "custom": OpenAICompatibleConfig(
            base_url="https://api.your-provider.com/v1",
            headers={"Content-Type": "application/json"},
            timeout=60,
            retry_count=2
        )
    }
    
    # 全局设置
    GLOBAL_SETTINGS = {
        "enable_dual_mode": True,
        "gemini_2_0_preferred_mode": APIMode.GENAI,  # gemini-2.0-flash的优先模式
        "fallback_enabled": True,
        "debug_mode": False,
        "request_timeout": 30,
        "max_retries": 3
    }
    
    @classmethod
    def get_model_config(cls, model_name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return cls.MODEL_CONFIGS.get(model_name)
    
    @classmethod
    def get_effective_mode(cls, model_name: str, preferred_mode: Optional[APIMode] = None) -> APIMode:
        """获取模型的有效API模式"""
        config = cls.get_model_config(model_name)
        if not config:
            return cls.DEFAULT_MODE
        
        # 处理AUTO模式
        if config.mode == APIMode.AUTO:
            if model_name == "gemini-2.0-flash":
                return preferred_mode or cls.GLOBAL_SETTINGS["gemini_2_0_preferred_mode"]
            return cls.DEFAULT_MODE
        
        return config.mode
    
    @classmethod
    def supports_search(cls, model_name: str) -> bool:
        """检查模型是否支持搜索功能"""
        config = cls.get_model_config(model_name)
        return config.supports_search if config else False
    
    @classmethod
    def supports_tools(cls, model_name: str) -> bool:
        """检查模型是否支持工具调用"""
        config = cls.get_model_config(model_name)
        return config.supports_tools if config else False
    
    @classmethod
    def get_default_params(cls, model_name: str) -> Dict[str, Any]:
        """获取模型默认参数"""
        config = cls.get_model_config(model_name)
        return config.default_params.copy() if config else {}
    
    @classmethod
    def get_openai_config(cls, config_name: str = "default") -> OpenAICompatibleConfig:
        """获取OpenAI兼容配置"""
        return cls.OPENAI_COMPATIBLE_CONFIGS.get(config_name, cls.OPENAI_COMPATIBLE_CONFIGS["default"])
    
    @classmethod
    def add_model_config(cls, model_name: str, config: ModelConfig) -> None:
        """动态添加模型配置"""
        cls.MODEL_CONFIGS[model_name] = config
    
    @classmethod
    def update_global_setting(cls, key: str, value: Any) -> None:
        """更新全局设置"""
        if key in cls.GLOBAL_SETTINGS:
            cls.GLOBAL_SETTINGS[key] = value
    
    @classmethod
    def get_global_setting(cls, key: str, default: Any = None) -> Any:
        """获取全局设置"""
        return cls.GLOBAL_SETTINGS.get(key, default)
    
    @classmethod
    def is_dual_mode_enabled(cls) -> bool:
        """检查是否启用双模式"""
        return cls.GLOBAL_SETTINGS.get("enable_dual_mode", False)
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """获取所有可用模型列表"""
        return list(cls.MODEL_CONFIGS.keys())
    
    @classmethod
    def get_models_by_mode(cls, mode: APIMode) -> List[str]:
        """按模式获取模型列表"""
        return [
            name for name, config in cls.MODEL_CONFIGS.items()
            if config.mode == mode or (config.mode == APIMode.AUTO and mode == cls.DEFAULT_MODE)
        ]
    
    @classmethod
    def validate_model(cls, model_name: str) -> bool:
        """验证模型是否被支持"""
        return model_name in cls.MODEL_CONFIGS 