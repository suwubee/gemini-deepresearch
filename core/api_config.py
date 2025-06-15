"""
API配置管理
简化版本，支持GenAI和OpenAI两种模式的配置
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class APIMode(Enum):
    """API模式枚举"""
    GENAI = "genai"
    OPENAI = "openai"
    AUTO = "auto"


@dataclass
class OpenAIConfig:
    """OpenAI配置"""
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    timeout: int = 30


@dataclass  
class APIConfig:
    """API配置"""
    mode: APIMode = APIMode.GENAI
    genai_api_key: str = ""
    openai_config: OpenAIConfig = None
    
    def __post_init__(self):
        if self.openai_config is None:
            self.openai_config = OpenAIConfig()
    
    @classmethod
    def create_genai_config(cls, api_key: str) -> "APIConfig":
        """创建GenAI配置"""
        return cls(
            mode=APIMode.GENAI,
            genai_api_key=api_key
        )
    
    @classmethod 
    def create_openai_config(cls, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 30) -> "APIConfig":
        """创建OpenAI配置"""
        return cls(
            mode=APIMode.OPENAI,
            openai_config=OpenAIConfig(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout
            )
        )
    
    def get_api_key(self) -> str:
        """获取当前模式的API密钥"""
        if self.mode == APIMode.GENAI:
            return self.genai_api_key
        elif self.mode == APIMode.OPENAI:
            return self.openai_config.api_key
        else:
            return ""
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if self.mode == APIMode.GENAI:
            return bool(self.genai_api_key)
        elif self.mode == APIMode.OPENAI:
            return bool(self.openai_config.api_key)
        else:
            return False


# 全局配置实例
_global_config: Optional[APIConfig] = None


def set_global_config(config: APIConfig):
    """设置全局配置"""
    global _global_config
    _global_config = config


def get_global_config() -> Optional[APIConfig]:
    """获取全局配置"""
    return _global_config


def has_global_config() -> bool:
    """检查是否有全局配置"""
    return _global_config is not None and _global_config.is_valid() 