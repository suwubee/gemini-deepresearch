"""
API客户端工厂
根据配置自动创建和管理API客户端
"""

from typing import Dict, Optional, Any
from .api_config import APIConfig, APIMode, ModelConfig
from .api_client import BaseAPIClient, GoogleGenAIClient, OpenAICompatibleClient, APIResponse


class APIClientFactory:
    """API客户端工厂类"""
    
    # 客户端缓存
    _client_cache: Dict[str, BaseAPIClient] = {}
    
    @classmethod
    def create_client(cls, 
                     api_key: str, 
                     model_name: str,
                     preferred_mode: Optional[APIMode] = None,
                     base_url: Optional[str] = None,
                     **kwargs) -> BaseAPIClient:
        """
        创建API客户端
        
        Args:
            api_key: API密钥
            model_name: 模型名称
            preferred_mode: 优先模式（用于AUTO模式）
            base_url: 自定义基础URL（用于OpenAI兼容模式）
            **kwargs: 其他参数
        
        Returns:
            API客户端实例
        """
        # 生成缓存键
        cache_key = cls._generate_cache_key(model_name, preferred_mode, base_url)
        
        # 检查缓存
        if cache_key in cls._client_cache:
            cached_client = cls._client_cache[cache_key]
            # 验证缓存的客户端是否仍然有效
            if cls._is_client_valid(cached_client, api_key):
                return cached_client
            else:
                # 清理无效缓存
                del cls._client_cache[cache_key]
        
        # 确定API模式
        effective_mode = APIConfig.get_effective_mode(model_name, preferred_mode)
        
        # 创建客户端
        if effective_mode == APIMode.GENAI:
            client = GoogleGenAIClient(api_key, model_name)
        elif effective_mode == APIMode.OPENAI:
            client = OpenAICompatibleClient(api_key, model_name, base_url)
        else:
            raise ValueError(f"不支持的API模式: {effective_mode}")
        
        # 缓存客户端
        cls._client_cache[cache_key] = client
        
        return client
    
    @classmethod
    def create_search_client(cls, 
                           api_key: str, 
                           model_name: str = "gemini-2.0-flash",
                           **kwargs) -> BaseAPIClient:
        """
        创建专门用于搜索的客户端
        
        Args:
            api_key: API密钥
            model_name: 模型名称，默认使用支持搜索的模型
            **kwargs: 其他参数
        
        Returns:
            支持搜索的API客户端
        """
        # 验证模型是否支持搜索
        if not APIConfig.supports_search(model_name):
            # 如果指定的模型不支持搜索，尝试使用默认的搜索模型
            search_models = [name for name in APIConfig.get_available_models() 
                           if APIConfig.supports_search(name)]
            if search_models:
                model_name = search_models[0]
                print(f"⚠️ 原模型不支持搜索，使用 {model_name} 进行搜索")
            else:
                raise ValueError("没有可用的搜索模型")
        
        return cls.create_client(api_key, model_name, **kwargs)
    
    @classmethod
    def create_analysis_client(cls, 
                             api_key: str, 
                             model_name: str = "gemini-2.5-flash-preview-05-20",
                             **kwargs) -> BaseAPIClient:
        """
        创建专门用于分析的客户端
        
        Args:
            api_key: API密钥
            model_name: 模型名称，默认使用适合分析的模型
            **kwargs: 其他参数
        
        Returns:
            适合分析的API客户端
        """
        return cls.create_client(api_key, model_name, **kwargs)
    
    @classmethod
    def create_answer_client(cls, 
                           api_key: str, 
                           model_name: str = "gemini-2.5-pro-preview-06-05",
                           **kwargs) -> BaseAPIClient:
        """
        创建专门用于答案生成的客户端
        
        Args:
            api_key: API密钥
            model_name: 模型名称，默认使用最强的模型
            **kwargs: 其他参数
        
        Returns:
            适合答案生成的API客户端
        """
        return cls.create_client(api_key, model_name, **kwargs)
    
    @classmethod
    def get_client_info(cls, model_name: str) -> Dict[str, Any]:
        """
        获取客户端信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            客户端信息字典
        """
        config = APIConfig.get_model_config(model_name)
        if not config:
            return {"error": f"未找到模型 {model_name} 的配置"}
        
        effective_mode = APIConfig.get_effective_mode(model_name)
        
        return {
            "model_name": model_name,
            "mode": effective_mode.value,
            "supports_search": config.supports_search,
            "supports_tools": config.supports_tools,
            "fallback_search": config.fallback_search,
            "default_params": config.default_params,
            "base_url": config.base_url
        }
    
    @classmethod
    def list_available_models(cls) -> Dict[str, Dict[str, Any]]:
        """
        列出所有可用模型及其信息
        
        Returns:
            模型信息字典
        """
        models_info = {}
        
        for model_name in APIConfig.get_available_models():
            models_info[model_name] = cls.get_client_info(model_name)
        
        return models_info
    
    @classmethod
    def validate_configuration(cls, 
                             api_key: str, 
                             model_name: str,
                             preferred_mode: Optional[APIMode] = None) -> Dict[str, Any]:
        """
        验证配置的有效性
        
        Args:
            api_key: API密钥
            model_name: 模型名称
            preferred_mode: 优先模式
            
        Returns:
            验证结果
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # 验证API密钥
        if not api_key or len(api_key) < 10:
            result["errors"].append("API密钥无效或太短")
        
        # 验证模型配置
        if not APIConfig.validate_model(model_name):
            result["errors"].append(f"不支持的模型: {model_name}")
        else:
            result["info"].update(cls.get_client_info(model_name))
        
        # 验证模式选择
        try:
            effective_mode = APIConfig.get_effective_mode(model_name, preferred_mode)
            result["info"]["effective_mode"] = effective_mode.value
        except Exception as e:
            result["errors"].append(f"模式选择错误: {str(e)}")
        
        # 检查搜索功能
        if model_name and not APIConfig.supports_search(model_name):
            result["warnings"].append(f"模型 {model_name} 不支持搜索功能")
        
        result["valid"] = len(result["errors"]) == 0
        
        return result
    
    @classmethod
    def _generate_cache_key(cls, 
                          model_name: str, 
                          preferred_mode: Optional[APIMode], 
                          base_url: Optional[str]) -> str:
        """生成缓存键"""
        key_parts = [model_name]
        
        if preferred_mode:
            key_parts.append(preferred_mode.value)
        
        if base_url:
            key_parts.append(base_url)
        
        return "|".join(key_parts)
    
    @classmethod
    def _is_client_valid(cls, client: BaseAPIClient, api_key: str) -> bool:
        """检查缓存的客户端是否仍然有效"""
        try:
            return client.api_key == api_key
        except:
            return False
    
    @classmethod
    def clear_cache(cls):
        """清理客户端缓存"""
        # 清理HTTP会话
        for client in cls._client_cache.values():
            if hasattr(client, 'close'):
                try:
                    import asyncio
                    asyncio.create_task(client.close())
                except:
                    pass
        
        cls._client_cache.clear()
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cached_clients": len(cls._client_cache),
            "cache_keys": list(cls._client_cache.keys())
        }


class ClientManager:
    """客户端管理器 - 用于管理多个客户端的生命周期"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.clients: Dict[str, BaseAPIClient] = {}
        self._default_configs = {
            "search_model": "gemini-2.0-flash",
            "analysis_model": "gemini-2.5-flash-preview-05-20", 
            "answer_model": "gemini-2.5-pro-preview-06-05"
        }
    
    def get_search_client(self, model_name: Optional[str] = None) -> BaseAPIClient:
        """获取搜索客户端"""
        model_name = model_name or self._default_configs["search_model"]
        if "search" not in self.clients:
            self.clients["search"] = APIClientFactory.create_search_client(
                self.api_key, model_name
            )
        return self.clients["search"]
    
    def get_analysis_client(self, model_name: Optional[str] = None) -> BaseAPIClient:
        """获取分析客户端"""
        model_name = model_name or self._default_configs["analysis_model"]
        if "analysis" not in self.clients:
            self.clients["analysis"] = APIClientFactory.create_analysis_client(
                self.api_key, model_name
            )
        return self.clients["analysis"]
    
    def get_answer_client(self, model_name: Optional[str] = None) -> BaseAPIClient:
        """获取答案生成客户端"""
        model_name = model_name or self._default_configs["answer_model"]
        if "answer" not in self.clients:
            self.clients["answer"] = APIClientFactory.create_answer_client(
                self.api_key, model_name
            )
        return self.clients["answer"]
    
    def update_config(self, **kwargs):
        """更新默认配置"""
        self._default_configs.update(kwargs)
        # 清理现有客户端，强制重新创建
        self.clients.clear()
    
    async def close_all(self):
        """关闭所有客户端"""
        for client in self.clients.values():
            if hasattr(client, 'close'):
                await client.close()
        self.clients.clear() 