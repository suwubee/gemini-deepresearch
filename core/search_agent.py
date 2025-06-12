"""
搜索代理类
使用 Gemini 2.0 内置搜索功能实现智能搜索
"""

import time
import traceback
from typing import List, Dict, Optional, Any
from datetime import datetime

try:
    from google.genai import Client
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
except ImportError:
    print("警告: 未安装必要的库，请运行: pip install google-genai")
    Client = None

from utils.helpers import (
    extract_json_from_text, 
    format_citations, 
    extract_urls,
    clean_text
)
from utils.debug_logger import get_debug_logger


class SearchAgent:
    """智能搜索代理"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.search_history = []
        self.debug_logger = get_debug_logger()
        
        # 初始化客户端
        if Client:
            self.client = Client(api_key=api_key)
    
    def _is_available(self) -> bool:
        """检查搜索代理是否可用"""
        return Client is not None and self.client is not None
    
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
            raise Exception("搜索代理不可用，请检查 google-genai 库是否正确安装")
        
        try:
            search_start_time = datetime.now()
            request_id = f"search_{int(time.time() * 1000)}"
            
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
                    time.sleep(2.0 - time_since_last)
            
            self._last_request_time = time.time()
            
            # 配置工具和参数
            config = GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            )
            
            if use_search:
                google_search_tool = Tool(google_search=GoogleSearch())
                config.tools = [google_search_tool]
            
            # 使用 google.genai.Client 进行搜索
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=query,
                config=config
            )
            
            search_duration = (datetime.now() - search_start_time).total_seconds()
            
            # Debug: 记录API响应
            response_text = response.text if response and hasattr(response, 'text') else ""
            metadata = {}
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata["has_grounding"] = True
                    if hasattr(candidate.grounding_metadata, 'web_search_queries'):
                        metadata["search_queries"] = list(candidate.grounding_metadata.web_search_queries)
            
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
    
    def _parse_search_response(self, response, original_query: str, duration: float) -> Dict[str, Any]:
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
                            
                            # 尝试提取真实域名和URL
                            domain = 'Unknown Domain'
                            actual_url = uri
                            
                            # 如果是vertexaisearch重定向链接，尝试从标题推断实际域名
                            if uri and 'vertexaisearch.cloud.google.com' in uri:
                                # 尝试从标题推断真实网站
                                title_lower = title.lower() if title and isinstance(title, str) else ""
                                if 'bondcap' in title_lower:
                                    actual_url = "https://bondcap.com"
                                    domain = "bondcap.com"
                                elif 'zdnet' in title_lower:
                                    actual_url = "https://zdnet.com" 
                                    domain = "zdnet.com"
                                elif 'techcrunch' in title_lower:
                                    actual_url = "https://techcrunch.com"
                                    domain = "techcrunch.com"
                                elif 'forbes' in title_lower:
                                    actual_url = "https://forbes.com"
                                    domain = "forbes.com"
                                elif 'precedence' in title_lower:
                                    actual_url = "https://precedenceresearch.com"
                                    domain = "precedenceresearch.com"
                                else:
                                    # 保持原始URI，但提取显示域名
                                    actual_url = uri
                                    domain = "Grounding Search"
                            else:
                                # 正常URL处理
                                if uri and '//' in uri:
                                    try:
                                        domain = uri.split('//')[1].split('/')[0]
                                        actual_url = uri
                                    except:
                                        domain = 'Unknown Domain'
                                        actual_url = uri
                            
                            chunk_citations.append({
                                "title": title,
                                "url": actual_url,  # 使用处理后的实际URL
                                "description": f"Source from {domain}"
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
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                )
            )
            
            if response and response.text:
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