"""
通用API客户端
支持多种API提供商的抽象层
"""

import httpx
from typing import Optional, Dict, List, Any, Protocol
from abc import ABC, abstractmethod


class ApiClientProtocol(Protocol):
    """API客户端接口协议"""
    
    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """生成内容的通用接口"""
        ...
    
    async def close(self):
        """关闭客户端"""
        ...


class BaseApiClient(ABC):
    """API客户端基类"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        self.http_client = httpx.AsyncClient(timeout=600.0)
    
    @abstractmethod
    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """生成内容 - 子类实现"""
        pass
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()


class GeminiApiClient(BaseApiClient):
    """Gemini API客户端实现"""

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        super().__init__(api_key)
        self.base_url = base_url

    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        调用Gemini API生成内容
        """
        url = f"{self.base_url}/models/{model_name}:generateContent?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}

        # 构建Gemini API格式的payload
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
            }
        }
        if max_output_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_output_tokens
        
        if tools:
            payload["tools"] = tools

        try:
            response = await self.http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            try:
                error_details = e.response.json()
                return {"error": error_details.get("error", {"code": e.response.status_code, "message": error_text})}
            except Exception:
                return {"error": {"code": e.response.status_code, "message": error_text}}
        except httpx.RequestError as e:
            return {"error": {"message": str(e)}}


class OpenAIApiClient(BaseApiClient):
    """OpenAI API客户端实现 - 为未来集成预留"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        super().__init__(api_key)
        self.base_url = base_url

    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        调用OpenAI API生成内容 - 将Gemini格式转换为OpenAI格式
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建OpenAI API格式的payload
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens
        
        # 注意：OpenAI的工具格式与Gemini不同，需要转换
        # 这里暂时简化处理，实际实现时需要格式转换
        
        try:
            response = await self.http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            openai_response = response.json()
            
            # 将OpenAI响应格式转换为Gemini兼容格式
            return self._convert_openai_to_gemini_format(openai_response)
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            try:
                error_details = e.response.json()
                return {"error": error_details.get("error", {"code": e.response.status_code, "message": error_text})}
            except Exception:
                return {"error": {"code": e.response.status_code, "message": error_text}}
        except httpx.RequestError as e:
            return {"error": {"message": str(e)}}
    
    def _convert_openai_to_gemini_format(self, openai_response: Dict[str, Any]) -> Dict[str, Any]:
        """将OpenAI响应格式转换为Gemini格式，保持兼容性"""
        try:
            content = openai_response["choices"][0]["message"]["content"]
            return {
                "candidates": [{
                    "content": {
                        "parts": [{"text": content}]
                    }
                }]
            }
        except (KeyError, IndexError):
            return {"error": {"message": "Invalid OpenAI response format"}}


def create_api_client(provider: str, api_key: str) -> BaseApiClient:
    """工厂函数：根据提供商创建对应的API客户端"""
    if provider.lower() == "gemini":
        return GeminiApiClient(api_key)
    elif provider.lower() == "openai":
        return OpenAIApiClient(api_key)
    else:
        raise ValueError(f"Unsupported API provider: {provider}") 