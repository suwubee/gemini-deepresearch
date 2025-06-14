"""
搜索代理类
支持双模式API：Google GenAI SDK 和 OpenAI兼容HTTP API
"""

import time
import traceback
from typing import List, Dict, Optional, Any
from datetime import datetime

from .api_factory import APIClientFactory, ClientManager
from .api_client import BaseAPIClient, APIResponse
from .api_config import APIConfig, APIMode
from utils.helpers import (
    extract_json_from_text, 
    format_citations, 
    extract_urls,
    clean_text
)
from utils.debug_logger import get_debug_logger


class SearchAgent:
    """智能搜索代理 - 支持双模式API"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash", preferred_mode: Optional[APIMode] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.preferred_mode = preferred_mode
        self.search_history = []
        self.debug_logger = get_debug_logger()
        
        # 使用工厂创建客户端
        self.client = APIClientFactory.create_search_client(
            api_key=api_key,
            model_name=model_name,
            preferred_mode=preferred_mode
        )
        
        # 打印客户端信息
        client_info = APIClientFactory.get_client_info(model_name)
        print(f"🔍 搜索代理初始化:")
        print(f"  模型: {model_name}")
        print(f"  模式: {client_info.get('mode', 'unknown')}")
        print(f"  支持搜索: {client_info.get('supports_search', False)}")
        print(f"  支持工具: {client_info.get('supports_tools', False)}")
    
    def _is_available(self) -> bool:
        """检查搜索代理是否可用"""
        return self.client is not None
    
    async def search_with_grounding(self, query: str, use_search: bool = True) -> Dict[str, Any]:
        """
        使用配置的API模式进行搜索
        
        Args:
            query: 搜索查询
            use_search: 是否使用搜索工具
            
        Returns:
            包含搜索结果和元数据的字典
        """
        if not self._is_available():
            raise Exception("搜索代理不可用，请检查客户端初始化")
        
        try:
            search_start_time = datetime.now()
            
            # 准备工具配置
            tools = []
            if use_search and self.client.supports_search():
                tools.append({"type": "web_search"})
            elif use_search and not self.client.supports_search():
                # 如果客户端不支持搜索但需要搜索，记录警告
                print(f"⚠️ 模型 {self.model_name} 不支持原生搜索，将使用普通对话模式")
            
            # 使用统一的客户端接口
            response = await self.client.generate_content(
                prompt=query,
                temperature=0.1,
                max_tokens=8192,
                tools=tools if tools else None
            )
            
            search_duration = (datetime.now() - search_start_time).total_seconds()
            
            # 转换响应格式以保持兼容性
            result = self._convert_to_legacy_format(response, query, search_duration)
            
            # Debug: 记录搜索结果
            self.debug_logger.log_search_result(query, result, "dual_mode")
            
            # 记录搜索历史
            self.search_history.append({
                "query": query,
                "timestamp": datetime.now(),
                "duration": search_duration,
                "has_grounding": result.get("has_grounding", False),
                "api_mode": self.client.__class__.__name__
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
                context={"query": query, "model": self.model_name, "client_type": self.client.__class__.__name__},
                stacktrace=traceback.format_exc()
            )
            
            return error_result
    
    def _convert_to_legacy_format(self, response: APIResponse, original_query: str, duration: float) -> Dict[str, Any]:
        """将新的API响应转换为旧的格式以保持兼容性"""
        return {
            "success": response.success,
            "query": original_query,
            "content": response.text,
            "citations": response.citations,
            "urls": response.urls,
            "has_grounding": response.has_grounding,
            "search_queries": response.search_queries,
            "grounding_chunks": len(response.citations),
            "duration": duration,
            "error": response.error if not response.success else None
        }

    def _parse_search_response(self, response, original_query: str, duration: float) -> Dict[str, Any]:
        """保留旧方法以保持向后兼容性"""
        """解析搜索响应"""
        try:
            content = response.text if response and hasattr(response, 'text') else ""
            
            # 检查是否有 grounding metadata
            has_grounding = False
            citations = []
            search_queries = []
            grounding_chunks = []
            
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # 检查 grounding metadata
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    has_grounding = True
                    grounding_metadata = candidate.grounding_metadata
                    
                    # 提取搜索查询
                    if hasattr(grounding_metadata, 'web_search_queries'):
                        search_queries = list(grounding_metadata.web_search_queries)
                    
                    # 提取 grounding chunks
                    if hasattr(grounding_metadata, 'grounding_chunks'):
                        grounding_chunks = grounding_metadata.grounding_chunks
                    
                    # 提取 grounding supports（引用信息）
                    if hasattr(grounding_metadata, 'grounding_supports'):
                        citations = self._extract_citations(
                            grounding_metadata.grounding_supports,
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
                "grounding_chunks": len(grounding_chunks),
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
    
    def _extract_citations(self, grounding_supports, grounding_chunks) -> List[Dict]:
        """提取引用信息"""
        citations = []
        
        for support in grounding_supports:
            if hasattr(support, 'segment') and hasattr(support, 'grounding_chunk_indices'):
                start_index = getattr(support.segment, 'start_index', 0) 
                end_index = getattr(support.segment, 'end_index', 0)
                
                if end_index is None:
                    continue  # 跳过没有end_index的项
                
                # 获取对应的grounding chunks  
                chunk_citations = []
                for chunk_idx in support.grounding_chunk_indices:
                    if chunk_idx < len(grounding_chunks):
                        chunk = grounding_chunks[chunk_idx]
                        if hasattr(chunk, 'web') and chunk.web:
                            title = getattr(chunk.web, 'title', '') or 'Unknown Source'
                            uri = getattr(chunk.web, 'uri', '#')
                            
                            # 清理标题（移除文件扩展名等）
                            if title and isinstance(title, str) and '.' in title:
                                title = title.split('.')[0]
                            
                            # 提取域名
                            domain = 'Unknown Domain'
                            if uri and '//' in uri:
                                try:
                                    domain = uri.split('//')[1].split('/')[0]
                                except:
                                    domain = 'Unknown Domain'
                            
                            chunk_citations.append({
                                "title": title,
                                "url": uri,
                                "description": f"来源: {domain}"
                            })
                
                if chunk_citations:
                    # 为了兼容性，我们为每个chunk创建单独的citation
                    for chunk_citation in chunk_citations:
                        citations.append({
                            "title": chunk_citation["title"],
                            "url": chunk_citation["url"], 
                            "description": chunk_citation["description"],
                            "start_index": start_index,
                            "end_index": end_index
                        })
        
        return citations
    
    async def generate_search_queries(self, user_query: str, num_queries: int = 3) -> List[str]:
        """生成搜索查询"""
        if not self._is_available():
            return [user_query]  # 降级到原始查询
        
        try:
            prompt = f"""
            基于以下用户查询，生成{num_queries}个不同角度的搜索查询，帮助全面研究这个话题。
            
            用户查询: {user_query}
            
            请返回JSON格式的查询列表，例如：
            {{"queries": ["查询1", "查询2", "查询3"]}}
            """
            
            # 使用统一的客户端接口
            response = await self.client.generate_content(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1024
            )
            
            if response.success and response.text:
                result = extract_json_from_text(response.text)
                if result and "queries" in result:
                    return result["queries"][:num_queries]
            
            return [user_query]  # 降级
            
        except Exception:
            return [user_query]  # 降级
    
    async def batch_search(self, queries: List[str]) -> List[Dict[str, Any]]:
        """批量搜索"""
        results = []
        
        for query in queries:
            result = await self.search_with_grounding(query)
            results.append(result)
            
            # 添加延迟避免速率限制
            time.sleep(1)
        
        return results
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        if not self.search_history:
            return {"total_searches": 0}
        
        total_searches = len(self.search_history)
        successful_searches = len([h for h in self.search_history if h.get("has_grounding", False)])
        avg_duration = sum(h.get("duration", 0) for h in self.search_history) / total_searches
        
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