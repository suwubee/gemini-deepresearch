"""
搜索代理类
使用 Gemini 2.0 内置搜索功能实现智能搜索
"""

import time
import traceback
from typing import List, Dict, Optional, Any
from datetime import datetime
import asyncio
import re

from .api_client import create_api_client, BaseApiClient
from utils.debug_logger import get_debug_logger
from utils.prompts import PromptTemplates
from utils.helpers import (
    extract_json_from_text, 
    format_citations, 
    extract_urls,
    clean_text
)


class SearchAgent:
    """智能搜索代理"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash", api_provider: str = "gemini"):
        self.api_key = api_key
        self.model_name = model_name
        self.api_provider = api_provider
        self.client = create_api_client(api_provider, api_key)
        self.search_history = []
        self.debug_logger = get_debug_logger()
    
    def _is_available(self) -> bool:
        """检查搜索代理是否可用"""
        return self.client is not None
    
    async def search_with_grounding(self, query: str, use_search: bool = True) -> Dict[str, Any]:
        """
        使用 Gemini 2.0 的内置搜索功能进行搜索
        
        Args:
            query: 搜索查询
            use_search: 是否使用搜索工具
            
        Returns:
            包含搜索结果和元数据的字典
        """
        if not self._is_available():
            raise Exception("搜索代理不可用，请检查 API 客户端是否正确初始化")
        
        try:
            search_start_time = datetime.now()
            request_id = f"search_{int(time.time() * 1000)}"
            
            tools = [{"google_search": {}}] if use_search else None
            
            # Debug: 记录API请求
            config_dict = {
                "temperature": 0.1,
                "max_output_tokens": 8192,
                "use_search": use_search
            }
            self.debug_logger.log_api_request(
                request_type="search_with_grounding",
                model=self.model_name,
                prompt=query,
                config=config_dict,
                request_id=request_id
            )
            
            # 添加延迟避免速率限制
            if hasattr(self, '_last_request_time'):
                time_since_last = time.time() - self._last_request_time
                if time_since_last < 2.0:
                    await asyncio.sleep(2.0 - time_since_last)
            
            self._last_request_time = time.time()
            
            response = await self.client.generate_content(
                model_name=self.model_name,
                prompt=query,
                tools=tools,
                temperature=0.1,
                max_output_tokens=8192,
            )
            
            search_duration = (datetime.now() - search_start_time).total_seconds()

            if "error" in response:
                raise Exception(f"API Error: {response['error'].get('message', 'Unknown error')}")

            # Debug: 记录API响应
            response_text = self._get_text_from_response(response)
            metadata = {}
            if response.get("candidates"):
                candidate = response["candidates"][0]
                if candidate.get("groundingMetadata"):
                    metadata["has_grounding"] = True
                    if candidate["groundingMetadata"].get("webSearchQueries"):
                        metadata["search_queries"] = candidate["groundingMetadata"]["webSearchQueries"]

            self.debug_logger.log_api_response(
                request_id=request_id,
                response_text=response_text,
                metadata=metadata
            )
            
            # 解析响应
            result = self._parse_search_response(response, query, search_duration)
            
            # Debug: 记录搜索结果
            self.debug_logger.log_search_result(query, result, "grounding")
            
            # 记录搜索历史
            self.search_history.append({
                "query": query,
                "timestamp": datetime.now(),
                "duration": search_duration,
                "has_grounding": result.get("has_grounding", False)
            })
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "query": query,
                "content": "",
                "citations": [],
                "urls": [],
                "has_grounding": False,
                "search_queries": [],
                "duration": 0
            }
            
            # Debug: 记录错误
            self.debug_logger.log_error(
                error_type="SearchError",
                error_message=str(e),
                context={"query": query, "model": self.model_name},
                stacktrace=traceback.format_exc()
            )
            
            return error_result

    def _get_text_from_response(self, response: Dict[str, Any]) -> str:
        """Extracts text from the raw API response."""
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return ""

    def _parse_search_response(self, response: Dict[str, Any], original_query: str, duration: float) -> Dict[str, Any]:
        """解析搜索响应"""
        try:
            content = self._get_text_from_response(response)
            
            # 检查是否有 grounding metadata
            has_grounding = False
            citations = []
            search_queries = []
            grounding_chunks_count = 0
            
            candidates = response.get("candidates", [])
            if candidates:
                candidate = candidates[0]
                grounding_metadata = candidate.get("groundingMetadata")
                
                if grounding_metadata:
                    has_grounding = True
                    search_queries = grounding_metadata.get("webSearchQueries", [])
                    grounding_chunks = grounding_metadata.get("groundingChunks", [])
                    grounding_chunks_count = len(grounding_chunks)
                    
                    citations = self._extract_citations(
                        grounding_metadata.get("groundingSupports", []),
                        grounding_chunks
                    )
            
            # 提取URL
            urls = extract_urls(content)
            
            # 如果有引用，格式化内容
            if citations:
                content = format_citations(content, citations)
            
            return {
                "success": True,
                "query": original_query,
                "content": clean_text(content),
                "citations": citations,
                "urls": urls,
                "has_grounding": has_grounding,
                "search_queries": search_queries,
                "grounding_chunks": grounding_chunks_count,
                "duration": duration
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"解析响应失败: {str(e)}",
                "query": original_query,
                "content": "",
                "citations": [],
                "urls": [],
                "has_grounding": False,
                "search_queries": [],
                "duration": duration
            }
    
    def _extract_citations(self, grounding_supports: List[Dict], grounding_chunks: List[Dict]) -> List[Dict]:
        """提取引用信息"""
        citations = []
        
        for support in grounding_supports:
            segment = support.get("segment", {})
            start_index = segment.get("startIndex", 0)
            end_index = segment.get("endIndex")

            if end_index is None:
                continue

            chunk_citations = []
            for chunk_idx in support.get("groundingChunkIndices", []):
                if chunk_idx < len(grounding_chunks):
                    chunk = grounding_chunks[chunk_idx]
                    web_info = chunk.get("web")
                    if web_info:
                        title = web_info.get("title", "Unknown Source")
                        uri = web_info.get("uri", "#")
                        
                        if title and isinstance(title, str) and '.' in title:
                            title = title.split('.')[0]
                        
                        domain = 'Unknown Domain'
                        if uri and '//' in uri:
                            try:
                                domain = uri.split('//')[1].split('/')[0]
                            except Exception:
                                domain = 'Unknown Domain'
                        
                        chunk_citations.append({
                            "title": title,
                            "url": uri,
                            "description": f"来源: {domain}"
                        })
            
            if chunk_citations:
                for chunk_citation in chunk_citations:
                    citations.append({
                        **chunk_citation,
                        "start_index": start_index,
                        "end_index": end_index
                    })
        
        return citations
    
    async def generate_search_queries(self, user_query: str, num_queries: int = 3) -> List[str]:
        """生成搜索查询"""
        if not self._is_available():
            return [user_query]

        try:
            prompt = PromptTemplates.search_query_generation_prompt(user_query, num_queries)
            
            # Debug: Log API request
            request_id = f"query_gen_{int(time.time() * 1000)}"
            self.debug_logger.log_api_request(
                "query_generation", self.model_name, prompt, 
                {"num_queries": num_queries}, request_id, "search_queries"
            )
            
            response = await self.client.generate_content(
                model_name=self.model_name,
                prompt=prompt,
                temperature=0.3,
                max_output_tokens=1024,
            )

            if "error" in response:
                error_msg = response.get('error', {}).get('message', 'API error')
                self.debug_logger.log_api_response(request_id, "", None, error_msg)
                self.debug_logger.log_error("QueryGenerationError", error_msg, {"user_query": user_query})
                return [user_query]

            response_text = self._get_text_from_response(response)
            self.debug_logger.log_api_response(request_id, response_text, {"response_length": len(response_text)})
            
            if response_text:
                result = extract_json_from_text(response_text)
                
                if result and "query" in result and isinstance(result["query"], list):
                    queries = [q.strip() for q in result["query"] if q and q.strip()]
                    if queries:
                        return queries[:num_queries]
            
            # 如果解析失败或无有效结果，返回原始查询
            return [user_query]
            
        except Exception as e:
            self.debug_logger.log_error("QueryGenerationError", str(e), {"user_query": user_query})
            return [user_query]
    
    def _generate_fallback_queries(self, user_query: str, num_queries: int) -> List[str]:
        """生成简单的fallback查询"""
        # 保持简单，只做基础的查询变换
        if num_queries == 1:
            return [user_query]
        
        queries = [user_query]
        if num_queries > 1:
            queries.append(f"{user_query} 2024")
        if num_queries > 2:
            queries.append(f"{user_query} analysis")
            
        return queries[:num_queries]
    
    def _extract_queries_from_text(self, text: str, num_queries: int) -> List[str]:
        """从文本中提取查询（简化版本）"""
        # 查找引号中的内容
        quotes_pattern = r'["\']([^"\']{5,100})["\']'
        matches = re.findall(quotes_pattern, text)
        
        valid_queries = []
        for match in matches:
            cleaned = match.strip()
            if len(cleaned) > 5 and cleaned not in valid_queries:
                valid_queries.append(cleaned)
            if len(valid_queries) >= num_queries:
                break
        
        return valid_queries
    
    async def batch_search(self, queries: List[str]) -> List[Dict[str, Any]]:
        """批量搜索"""
        tasks = [self.search_with_grounding(query) for query in queries]
        results = await asyncio.gather(*tasks)
        return results
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        if not self.search_history:
            return {"total_searches": 0}
        
        total_searches = len(self.search_history)
        successful_searches = len([h for h in self.search_history if h.get("has_grounding", False)])
        avg_duration = sum(h.get("duration", 0) for h in self.search_history) / total_searches if total_searches else 0
        
        return {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "success_rate": successful_searches / total_searches if total_searches > 0 else 0,
            "average_duration": avg_duration,
            "recent_queries": [h["query"] for h in self.search_history[-5:]]
        }
    
    def clear_history(self):
        """清除搜索历史"""
        self.search_history = []
    
    async def close(self):
        """关闭客户端会话"""
        await self.client.close() 