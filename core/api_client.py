"""
API客户端抽象层
支持多种API模式的统一接口
"""

import asyncio
import aiohttp
import json
import time
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

try:
    from google.genai import Client
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
except ImportError:
    print("警告: 未安装google-genai库，GoogleGenAI客户端将不可用")
    Client = None

from .api_config import APIConfig, APIMode, ModelConfig
from utils.debug_logger import get_debug_logger
from utils.helpers import extract_urls, clean_text


class APIResponse:
    """统一的API响应格式"""
    
    def __init__(self, 
                 text: str = "", 
                 success: bool = True,
                 error: Optional[str] = None,
                 usage: Optional[Dict] = None,
                 metadata: Optional[Dict] = None):
        self.text = text
        self.success = success
        self.error = error
        self.usage = usage or {}
        self.metadata = metadata or {}
        
        # 搜索相关字段
        self.has_grounding = metadata.get("has_grounding", False) if metadata else False
        self.citations = metadata.get("citations", []) if metadata else []
        self.search_queries = metadata.get("search_queries", []) if metadata else []
        self.urls = metadata.get("urls", []) if metadata else []


class BaseAPIClient(ABC):
    """API客户端基类"""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.debug_logger = get_debug_logger()
        self.model_config = APIConfig.get_model_config(model_name)
        
        # 请求历史
        self.request_history = []
        
        # 速率限制
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 秒
    
    @abstractmethod
    async def generate_content(self, 
                             prompt: str, 
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             tools: Optional[List[Dict]] = None,
                             **kwargs) -> APIResponse:
        """生成内容的抽象方法"""
        pass
    
    @abstractmethod
    def supports_search(self) -> bool:
        """是否支持搜索功能"""
        pass
    
    @abstractmethod
    def supports_tools(self) -> bool:
        """是否支持工具调用"""
        pass
    
    def get_default_params(self) -> Dict[str, Any]:
        """获取默认参数"""
        return APIConfig.get_default_params(self.model_name)
    
    async def _apply_rate_limit(self):
        """应用速率限制"""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _log_request(self, request_type: str, prompt: str, **kwargs):
        """记录API请求"""
        request_id = f"{request_type}_{int(time.time() * 1000)}"
        self.debug_logger.log_api_request(
            request_type=request_type,
            model=self.model_name,
            prompt=prompt,
            config=kwargs,
            request_id=request_id
        )
        return request_id
    
    def _log_response(self, request_id: str, response: APIResponse):
        """记录API响应"""
        self.debug_logger.log_api_response(
            request_id=request_id,
            response_text=response.text,
            metadata=response.metadata
        )


class GoogleGenAIClient(BaseAPIClient):
    """Google GenAI SDK客户端"""
    
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        self.client = None
        
        if Client:
            try:
                self.client = Client(api_key=api_key)
            except Exception as e:
                print(f"初始化Google GenAI客户端失败: {e}")
        
        self._min_request_interval = 2.0  # Google API需要更长间隔
    
    def supports_search(self) -> bool:
        """Google GenAI支持搜索（仅限特定模型）"""
        return APIConfig.supports_search(self.model_name)
    
    def supports_tools(self) -> bool:
        """Google GenAI支持工具"""
        return APIConfig.supports_tools(self.model_name)
    
    async def generate_content(self, 
                             prompt: str, 
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             tools: Optional[List[Dict]] = None,
                             **kwargs) -> APIResponse:
        """使用Google GenAI生成内容"""
        if not self.client:
            return APIResponse(
                success=False,
                error="Google GenAI客户端未正确初始化"
            )
        
        try:
            await self._apply_rate_limit()
            
            # 准备参数
            default_params = self.get_default_params()
            config_params = {
                "temperature": temperature or default_params.get("temperature", 0.1),
                "max_output_tokens": max_tokens or default_params.get("max_output_tokens", 4096)
            }
            
            # 记录请求
            request_id = self._log_request("google_genai", prompt, **config_params)
            
            # 创建配置
            config = GenerateContentConfig(**config_params)
            
            # 处理工具配置
            if tools:
                config.tools = self._convert_tools_to_genai(tools)
            
            # 执行请求
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            # 解析响应
            api_response = self._parse_genai_response(response, prompt)
            
            # 记录响应
            self._log_response(request_id, api_response)
            
            return api_response
            
        except Exception as e:
            error_msg = f"Google GenAI请求失败: {str(e)}"
            self.debug_logger.log_error(
                error_type="GoogleGenAIError",
                error_message=error_msg,
                context={"model": self.model_name, "prompt": prompt[:200]},
                stacktrace=traceback.format_exc()
            )
            
            return APIResponse(
                success=False,
                error=error_msg
            )
    
    def _convert_tools_to_genai(self, tools: List[Dict]) -> List[Tool]:
        """将通用工具格式转换为Google GenAI格式"""
        genai_tools = []
        
        for tool in tools:
            if tool.get("type") == "web_search" or tool.get("type") == "google_search":
                genai_tools.append(Tool(google_search=GoogleSearch()))
        
        return genai_tools
    
    def _parse_genai_response(self, response, original_prompt: str) -> APIResponse:
        """解析Google GenAI响应"""
        try:
            content = response.text if response and hasattr(response, 'text') else ""
            
            # 提取元数据
            metadata = {
                "has_grounding": False,
                "citations": [],
                "search_queries": [],
                "urls": extract_urls(content)
            }
            
            # 检查grounding metadata
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata["has_grounding"] = True
                    grounding_metadata = candidate.grounding_metadata
                    
                    # 提取搜索查询
                    if hasattr(grounding_metadata, 'web_search_queries'):
                        metadata["search_queries"] = list(grounding_metadata.web_search_queries)
                    
                    # 提取引用
                    if hasattr(grounding_metadata, 'grounding_supports') and hasattr(grounding_metadata, 'grounding_chunks'):
                        metadata["citations"] = self._extract_citations(
                            grounding_metadata.grounding_supports,
                            grounding_metadata.grounding_chunks
                        )
            
            return APIResponse(
                text=clean_text(content),
                success=True,
                metadata=metadata
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"解析Google GenAI响应失败: {str(e)}"
            )
    
    def _extract_citations(self, grounding_supports, grounding_chunks) -> List[Dict]:
        """提取引用信息"""
        citations = []
        
        try:
            for support in grounding_supports:
                if hasattr(support, 'segment') and hasattr(support, 'grounding_chunk_indices'):
                    start_index = getattr(support.segment, 'start_index', 0) 
                    end_index = getattr(support.segment, 'end_index', 0)
                    
                    if end_index is None:
                        continue
                    
                    # 获取对应的grounding chunks
                    for chunk_idx in support.grounding_chunk_indices:
                        if chunk_idx < len(grounding_chunks):
                            chunk = grounding_chunks[chunk_idx]
                            if hasattr(chunk, 'web') and chunk.web:
                                title = getattr(chunk.web, 'title', '') or 'Unknown Source'
                                uri = getattr(chunk.web, 'uri', '#')
                                
                                # 提取域名
                                domain = 'Unknown Domain'
                                if uri and '//' in uri:
                                    try:
                                        domain = uri.split('//')[1].split('/')[0]
                                    except:
                                        domain = 'Unknown Domain'
                                
                                citations.append({
                                    "title": title,
                                    "url": uri,
                                    "description": f"来源: {domain}",
                                    "start_index": start_index,
                                    "end_index": end_index
                                })
        except Exception as e:
            print(f"提取引用信息失败: {e}")
        
        return citations


class OpenAICompatibleClient(BaseAPIClient):
    """OpenAI兼容HTTP客户端"""
    
    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        super().__init__(api_key, model_name)
        
        # 获取配置
        if base_url:
            self.base_url = base_url
        elif self.model_config and self.model_config.base_url:
            self.base_url = self.model_config.base_url
        else:
            openai_config = APIConfig.get_openai_config()
            self.base_url = openai_config.base_url
        
        # HTTP会话
        self.session = None
        self._min_request_interval = 0.5  # OpenAI兼容接口通常更快
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    def supports_search(self) -> bool:
        """OpenAI兼容客户端通常不支持原生搜索"""
        return False  # 可以通过配置改变
    
    def supports_tools(self) -> bool:
        """OpenAI兼容客户端支持工具"""
        return APIConfig.supports_tools(self.model_name)
    
    async def generate_content(self, 
                             prompt: str, 
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             tools: Optional[List[Dict]] = None,
                             **kwargs) -> APIResponse:
        """使用OpenAI兼容API生成内容"""
        try:
            await self._ensure_session()
            await self._apply_rate_limit()
            
            # 准备参数
            default_params = self.get_default_params()
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature or default_params.get("temperature", 0.3),
                "max_tokens": max_tokens or default_params.get("max_tokens", 4096)
            }
            
            # 处理工具
            if tools and self.supports_tools():
                payload["tools"] = self._convert_tools_to_openai(tools)
                payload["tool_choice"] = "auto"
            
            # 记录请求
            request_id = self._log_request("openai_compatible", prompt, **payload)
            
            # 准备headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 如果有自定义headers
            if self.model_config and self.model_config.headers:
                headers.update(self.model_config.headers)
            
            # 执行请求
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    api_response = self._parse_openai_response(data)
                else:
                    error_text = await response.text()
                    api_response = APIResponse(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}"
                    )
            
            # 记录响应
            self._log_response(request_id, api_response)
            
            return api_response
            
        except Exception as e:
            error_msg = f"OpenAI兼容API请求失败: {str(e)}"
            self.debug_logger.log_error(
                error_type="OpenAICompatibleError",
                error_message=error_msg,
                context={"model": self.model_name, "prompt": prompt[:200]},
                stacktrace=traceback.format_exc()
            )
            
            return APIResponse(
                success=False,
                error=error_msg
            )
    
    def _convert_tools_to_openai(self, tools: List[Dict]) -> List[Dict]:
        """将通用工具格式转换为OpenAI格式"""
        openai_tools = []
        
        for tool in tools:
            if tool.get("type") == "web_search":
                # OpenAI兼容的搜索工具定义
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"}
                            },
                            "required": ["query"]
                        }
                    }
                })
        
        return openai_tools
    
    def _parse_openai_response(self, data: Dict) -> APIResponse:
        """解析OpenAI兼容响应"""
        try:
            if "choices" not in data or not data["choices"]:
                return APIResponse(
                    success=False,
                    error="响应中没有选择项"
                )
            
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            
            # 使用情况
            usage = data.get("usage", {})
            
            # 元数据
            metadata = {
                "has_grounding": False,
                "citations": [],
                "search_queries": [],
                "urls": extract_urls(content),
                "finish_reason": choice.get("finish_reason", "stop")
            }
            
            return APIResponse(
                text=clean_text(content),
                success=True,
                usage=usage,
                metadata=metadata
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"解析OpenAI响应失败: {str(e)}"
            )
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None 