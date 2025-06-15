"""
搜索代理类
使用统一的API抽象层进行智能搜索
"""

import time
import traceback
from typing import List, Dict, Optional, Any
from datetime import datetime

from .api_client import BaseAPIClient, APIResponse
from utils.helpers import (
    extract_json_from_text, 
    format_citations, 
    extract_urls,
    clean_text
)
from utils.debug_logger import get_debug_logger


class SearchAgent:
    """智能搜索代理 - 使用统一API抽象层"""
    
    def __init__(self, client: BaseAPIClient):
        self.client = client
        self.model_name = client.model_name
        self.search_history = []
        self.debug_logger = get_debug_logger()
        
        print(f"🔍 搜索代理初始化:")
        print(f"  模型: {self.model_name}")
        print(f"  客户端类型: {self.client.__class__.__name__}")
        print(f"  支持搜索: {self.client.supports_search()}")
    
    def _is_available(self) -> bool:
        """检查搜索代理是否可用"""
        return self.client is not None
    
    def search_with_grounding(self, query: str, use_search: bool = True) -> Dict[str, Any]:
        """
        使用统一API进行搜索
        
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
            
            # 调用统一API
            if self.client.supports_search() and use_search:
                # 支持搜索，使用搜索工具
                response = self.client.generate_content(
                    query,
                    temperature=0.1,
                    max_tokens=8192,
                    tools='google_search_retrieval',
                    use_search=True
                )
            else:
                # 不支持搜索，普通生成
                response = self.client.generate_content(
                    query,
                    temperature=0.1,
                    max_tokens=8192
                )
                if not response.success:
                    print(f"⚠️ 普通生成模式：{response.error}")
            
            search_duration = (datetime.now() - search_start_time).total_seconds()
            
            # 转换为统一格式
            result = self._convert_response_to_legacy_format(response, query, search_duration)
            
            # Debug: 记录搜索结果
            self.debug_logger.log_search_result(query, result, self.client.__class__.__name__)
            
            # 记录搜索历史
            self.search_history.append({
                "query": query,
                "timestamp": datetime.now(),
                "duration": search_duration,
                "has_grounding": result.get("has_grounding", False),
                "api_client": self.client.__class__.__name__
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
    
    def _convert_response_to_legacy_format(self, response: APIResponse, original_query: str, duration: float) -> Dict[str, Any]:
        """将API响应转换为旧格式以保持兼容性"""
        return {
            "success": response.success,
            "query": original_query,
            "content": clean_text(response.text) if response.text else "",
            "citations": response.citations,
            "urls": response.urls,
            "has_grounding": response.has_grounding,
            "search_queries": response.search_queries,
            "grounding_chunks": len(response.citations),
            "duration": duration,
            "error": response.error if not response.success else None
        }
    
    def generate_search_queries(self, user_query: str, num_queries: int = 3) -> List[str]:
        """生成多维度搜索查询"""
        try:
            prompt = f"""
基于用户查询，生成{num_queries}个不同角度的搜索查询：

用户查询: {user_query}

请生成涵盖不同方面的搜索查询，每行一个：
"""
            
            response = self.client.generate_content(
                prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            if response.success:
                queries = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
                return queries[:num_queries]
            else:
                print(f"生成搜索查询失败: {response.error}")
                return [user_query]  # 降级返回原查询
            
        except Exception as e:
            print(f"生成搜索查询异常: {e}")
            return [user_query]
    
    def batch_search(self, queries: List[str]) -> List[Dict[str, Any]]:
        """批量搜索"""
        results = []
        for query in queries:
            try:
                result = self.search_with_grounding(query)
                results.append(result)
                time.sleep(1)  # 简单的速率限制
            except Exception as e:
                print(f"批量搜索失败 '{query}': {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "query": query
                })
        return results
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        total_searches = len(self.search_history)
        successful_searches = sum(1 for s in self.search_history if s.get("has_grounding", False))
        avg_duration = sum(s.get("duration", 0) for s in self.search_history) / max(total_searches, 1)
        
        return {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "success_rate": successful_searches / max(total_searches, 1),
            "average_duration": avg_duration,
            "model_name": self.model_name,
            "client_type": self.client.__class__.__name__
        }
    
    def clear_history(self):
        """清除搜索历史"""
        self.search_history.clear() 