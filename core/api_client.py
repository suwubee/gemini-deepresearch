"""
API客户端抽象层
支持Google GenAI SDK和OpenAI HTTP API两种模式
使用Python原生requests库
"""

import json
import time
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Google GenAI SDK
try:
    import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠️ 'genai' 库不可用")


@dataclass
class APIResponse:
    """统一的API响应格式"""
    success: bool
    text: str = ""
    error: str = ""
    citations: List[Dict] = None
    urls: List[str] = None
    has_grounding: bool = False
    search_queries: List[str] = None
    
    def __post_init__(self):
        if self.citations is None:
            self.citations = []
        if self.urls is None:
            self.urls = []
        if self.search_queries is None:
            self.search_queries = []


class BaseAPIClient(ABC):
    """API客户端基类"""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
    
    @abstractmethod
    def generate_content(self, prompt: str, **kwargs) -> APIResponse:
        """生成内容的抽象方法"""
        pass
    
    @abstractmethod
    def supports_search(self) -> bool:
        """是否支持搜索功能"""
        pass
    
    def supports_tools(self) -> bool:
        """是否支持工具调用"""
        return False


class GenAIClient(BaseAPIClient):
    """Google GenAI SDK客户端"""
    
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        
        if not GENAI_AVAILABLE:
            raise ImportError("'genai' 库不可用，请确认项目依赖")
        
        # 配置GenAI (使用你项目中的方式)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name)
        
        print(f"✅ GenAI客户端初始化成功 (使用 'genai' 库): {model_name}")
    
    def generate_content(self, prompt: str, **kwargs) -> APIResponse:
        """使用GenAI生成内容"""
        try:
            # 提取参数
            temperature = kwargs.get('temperature', 0.3)
            max_tokens = kwargs.get('max_tokens', kwargs.get('max_output_tokens', 4096))
            use_search = kwargs.get('use_search', False)
            
            # 准备生成配置 (使用 genai.types)
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # 准备工具 (使用 google_search_retrieval 字符串)
            tools = 'google_search_retrieval' if use_search else None
            
            # 调用API
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config,
                tools=tools
            )
            
            # 解析响应
            return self._parse_genai_response(response, prompt)
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"GenAI ('genai'库) API调用失败: {str(e)}"
            )
    
    def _parse_genai_response(self, response, original_query: str) -> APIResponse:
        """解析GenAI响应 (适配 'genai' 库)"""
        try:
            content = response.text if response and hasattr(response, 'text') else ""
            
            has_grounding = False
            citations = []
            search_queries = []
            urls = []
            
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    has_grounding = True
                    grounding_metadata = candidate.grounding_metadata
                    
                    if hasattr(grounding_metadata, 'web_search_queries'):
                        search_queries = list(grounding_metadata.web_search_queries)
                    
                    if hasattr(grounding_metadata, 'grounding_supports'):
                        citations = self._extract_citations(grounding_metadata.grounding_supports)
                        urls = [cite.get('url', '') for cite in citations if cite.get('url')]
            
            return APIResponse(
                success=True, text=content, citations=citations,
                urls=urls, has_grounding=has_grounding, search_queries=search_queries
            )
            
        except Exception as e:
            return APIResponse(success=False, error=f"解析GenAI响应失败: {str(e)}")
    
    def _extract_citations(self, grounding_supports) -> List[Dict]:
        """提取引用信息"""
        citations = []
        try:
            for support in grounding_supports:
                if hasattr(support, 'segment') and hasattr(support.segment, 'text'):
                    citation = {
                        'text': support.segment.text,
                        'title': getattr(support, 'title', ''),
                        'url': getattr(support, 'url', ''),
                        'snippet': support.segment.text[:200] + '...' if len(support.segment.text) > 200 else support.segment.text
                    }
                    citations.append(citation)
        except Exception as e:
            print(f"提取引用失败: {e}")
        
        return citations
    
    def supports_search(self) -> bool:
        """GenAI支持搜索"""
        return True
    
    def supports_tools(self) -> bool:
        """GenAI支持工具调用"""
        return True


class OpenAIClient(BaseAPIClient):
    """OpenAI HTTP API客户端（使用requests）"""
    
    def __init__(self, api_key: str, model_name: str, base_url: str = "https://api.openai.com/v1", timeout: int = 30):
        super().__init__(api_key, model_name)
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # 验证API连接
        self._validate_connection()
        
        print(f"✅ OpenAI客户端初始化成功: {model_name} @ {base_url}")
    
    def _validate_connection(self):
        """验证API连接"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"⚠️ API连接验证失败: {response.status_code}")
            
        except Exception as e:
            print(f"⚠️ API连接验证异常: {e}")
    
    def generate_content(self, prompt: str, **kwargs) -> APIResponse:
        """使用OpenAI API生成内容"""
        try:
            # 提取参数
            temperature = kwargs.get('temperature', 0.3)
            max_tokens = kwargs.get('max_tokens', kwargs.get('max_output_tokens', 4096))
            
            # 准备请求
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model_name,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            # 解析响应
            return self._parse_openai_response(response)
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"OpenAI API调用失败: {str(e)}"
            )
    
    def _parse_openai_response(self, response: requests.Response) -> APIResponse:
        """解析OpenAI响应"""
        try:
            if response.status_code != 200:
                return APIResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            
            # 提取内容
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                
                return APIResponse(
                    success=True,
                    text=content,
                    has_grounding=False  # OpenAI不支持grounding
                )
            else:
                return APIResponse(
                    success=False,
                    error="响应中没有找到有效内容"
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"解析OpenAI响应失败: {str(e)}"
            )
    
    def supports_search(self) -> bool:
        """OpenAI不支持原生搜索"""
        return False


class APIClientFactory:
    """API客户端工厂"""
    
    @staticmethod
    def create_client(mode: str, api_key: str, model_name: str, **kwargs) -> BaseAPIClient:
        """创建API客户端"""
        mode = mode.lower()
        
        if mode == 'genai' or mode == 'google':
            return GenAIClient(api_key, model_name)
        elif mode == 'openai':
            base_url = kwargs.get('base_url', 'https://api.openai.com/v1')
            timeout = kwargs.get('timeout', 30)
            return OpenAIClient(api_key, model_name, base_url, timeout)
        else:
            raise ValueError(f"不支持的API模式: {mode}")
    
    @staticmethod
    def get_available_modes() -> List[str]:
        """获取可用的API模式"""
        modes = []
        if GENAI_AVAILABLE:
            modes.append('genai')
        modes.append('openai')  # requests总是可用的
        return modes 