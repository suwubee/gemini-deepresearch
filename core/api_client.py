"""
API Client for making direct HTTP requests to Google Gemini API.
This module is designed to be a layer of abstraction over the raw HTTP API,
preparing for future integration with other APIs like OpenAI's.
"""

import httpx
from typing import Optional, Dict, List, Any

class GeminiApiClient:
    """A client for interacting with the Google Gemini REST API."""

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=600.0)

    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calls the 'generateContent' endpoint of the Gemini API.

        Args:
            model_name: The name of the model to use (e.g., 'gemini-2.0-flash').
            prompt: The user's prompt.
            tools: A list of tools the model may call. For Google Search, use [{"google_search": {}}].
            temperature: The sampling temperature.
            max_output_tokens: The maximum number of tokens to generate.

        Returns:
            The raw JSON response from the API as a dictionary.
        """
        url = f"{self.base_url}/models/{model_name}:generateContent?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}

        # Construct payload
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
            print(f"HTTP error occurred: {e.response.status_code} - {error_text}")
            try:
                # 尝试解析错误详情
                error_details = e.response.json()
                return {"error": error_details.get("error", {"code": e.response.status_code, "message": error_text})}
            except Exception:
                return {"error": {"code": e.response.status_code, "message": error_text}}
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url!r}: {e}")
            return {"error": {"message": str(e)}}

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.http_client.aclose() 