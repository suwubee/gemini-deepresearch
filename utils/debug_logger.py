import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class DebugLogger:
    """Debug日志记录器 - 记录API请求和响应数据"""
    
    def __init__(self, enabled: bool = False, output_dir: str = "debug_logs"):
        self.enabled = enabled
        self.output_dir = Path(output_dir)
        self.current_session = None
        self.session_data = {
            "session_info": {},
            "api_requests": [],
            "search_results": [],
            "workflow_steps": [],
            "research_results": [],
            "errors": []
        }
        
        if self.enabled:
            self._init_session()
    
    def _init_session(self):
        """初始化debug会话"""
        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        
        # 生成会话ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session = f"debug_session_{timestamp}"
        
        # 初始化会话信息
        self.session_data["session_info"] = {
            "session_id": self.current_session,
            "start_time": datetime.now().isoformat(),
            "python_version": None,
            "platform": None
        }
        
        print(f"🐛 Debug模式已启用 - 会话ID: {self.current_session}")
    
    def enable(self, output_dir: str = "debug_logs"):
        """启用debug模式"""
        self.enabled = True
        self.output_dir = Path(output_dir)
        if not self.current_session:
            self._init_session()
    
    def disable(self):
        """禁用debug模式"""
        if self.enabled and self.current_session:
            self._save_session()
        self.enabled = False
    
    def log_api_request(self, 
                       request_type: str,
                       model: str,
                       prompt: str,
                       config: Optional[Dict] = None,
                       request_id: Optional[str] = None):
        """记录API请求"""
        if not self.enabled:
            return
        
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id or f"req_{int(time.time() * 1000)}",
            "request_type": request_type,
            "model": model,
            "prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,  # 限制长度
            "full_prompt_length": len(prompt),
            "config": config or {},
            "status": "sent"
        }
        
        self.session_data["api_requests"].append(request_data)
        self._log_to_console("📤 API请求", request_data["request_id"], request_type)
    
    def log_api_response(self,
                        request_id: str,
                        response_text: str,
                        metadata: Optional[Dict] = None,
                        error: Optional[str] = None):
        """记录API响应"""
        if not self.enabled:
            return
        
        # 查找对应的请求
        for request in self.session_data["api_requests"]:
            if request.get("request_id") == request_id:
                request["response"] = {
                    "timestamp": datetime.now().isoformat(),
                    "text": response_text[:1000] + "..." if len(response_text) > 1000 else response_text,
                    "full_response_length": len(response_text),
                    "metadata": metadata or {},
                    "error": error,
                    "status": "error" if error else "success"
                }
                break
        
        status = "❌ 错误" if error else "✅ 成功"
        self._log_to_console("📥 API响应", request_id, status)
    
    def log_search_result(self,
                         query: str,
                         result: Dict[str, Any],
                         search_type: str = "grounding"):
        """记录搜索结果"""
        if not self.enabled:
            return
        
        search_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "search_type": search_type,
            "success": result.get("success", False),
            "content_length": len(result.get("content", "")),
            "citations_count": len(result.get("citations", [])),
            "has_grounding": result.get("has_grounding", False),
            "urls_count": len(result.get("urls", [])),
            "duration": result.get("duration", 0),
            "full_result": result  # 保存完整结果
        }
        
        self.session_data["search_results"].append(search_data)
        status = "✅" if result.get("success") else "❌"
        self._log_to_console("🔍 搜索结果", query[:30], status)
    
    def log_workflow_step(self,
                         step_name: str,
                         step_status: str,
                         input_data: Optional[Dict] = None,
                         output_data: Optional[Dict] = None,
                         duration: Optional[float] = None):
        """记录工作流步骤"""
        if not self.enabled:
            return
        
        step_data = {
            "timestamp": datetime.now().isoformat(),
            "step_name": step_name,
            "step_status": step_status,
            "duration": duration,
            "input_summary": self._summarize_data(input_data) if input_data else None,
            "output_summary": self._summarize_data(output_data) if output_data else None,
            "full_input": input_data,
            "full_output": output_data
        }
        
        self.session_data["workflow_steps"].append(step_data)
        status_icon = {"completed": "✅", "running": "🔄", "failed": "❌"}.get(step_status, "❓")
        self._log_to_console("⚙️ 工作流步骤", step_name, status_icon)
    
    def log_research_result(self,
                           user_query: str,
                           final_result: Dict[str, Any],
                           metadata: Optional[Dict] = None):
        """记录研究结果"""
        if not self.enabled:
            return
        
        result_data = {
            "timestamp": datetime.now().isoformat(),
            "user_query": user_query,
            "final_answer_length": len(final_result.get("final_answer", "")),
            "success": final_result.get("success", True),
            "metadata": metadata or {},
            "full_result": final_result
        }
        
        self.session_data["research_results"].append(result_data)
        self._log_to_console("🎯 研究结果", user_query[:30], "✅ 完成")
    
    def log_error(self,
                 error_type: str,
                 error_message: str,
                 context: Optional[Dict] = None,
                 stacktrace: Optional[str] = None):
        """记录错误"""
        if not self.enabled:
            return
        
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
            "stacktrace": stacktrace
        }
        
        self.session_data["errors"].append(error_data)
        self._log_to_console("❌ 错误", error_type, error_message[:50])
    
    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        if not self.enabled:
            return {}
        
        return {
            "session_id": self.current_session,
            "total_api_requests": len(self.session_data["api_requests"]),
            "successful_api_requests": len([r for r in self.session_data["api_requests"] 
                                          if r.get("response", {}).get("status") == "success"]),
            "total_searches": len(self.session_data["search_results"]),
            "successful_searches": len([s for s in self.session_data["search_results"] if s["success"]]),
            "total_workflow_steps": len(self.session_data["workflow_steps"]),
            "completed_steps": len([s for s in self.session_data["workflow_steps"] 
                                  if s["step_status"] == "completed"]),
            "total_errors": len(self.session_data["errors"]),
            "research_results": len(self.session_data["research_results"])
        }
    
    def _summarize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """总结数据，避免过大的JSON"""
        if not isinstance(data, dict):
            return {"type": type(data).__name__, "value": str(data)[:100]}
        
        summary = {}
        for key, value in data.items():
            if isinstance(value, str):
                summary[key] = value[:100] + "..." if len(value) > 100 else value
            elif isinstance(value, (list, tuple)):
                summary[key] = f"{type(value).__name__}[{len(value)}]"
            elif isinstance(value, dict):
                summary[key] = f"dict[{len(value)} keys]"
            else:
                summary[key] = str(value)[:50]
        
        return summary
    
    def _log_to_console(self, category: str, identifier: str, status: str):
        """输出到控制台"""
        print(f"🐛 {category}: {identifier} - {status}")
    
    def _save_session(self):
        """保存会话数据到文件"""
        if not self.enabled or not self.current_session:
            return
        
        # 添加结束时间
        self.session_data["session_info"]["end_time"] = datetime.now().isoformat()
        
        # 生成文件名
        output_file = self.output_dir / f"{self.current_session}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, ensure_ascii=False, indent=2)
            
            print(f"🐛 Debug数据已保存到: {output_file}")
            
            # 生成摘要文件
            summary_file = self.output_dir / f"{self.current_session}_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(self.get_session_summary(), f, ensure_ascii=False, indent=2)
            
            print(f"🐛 会话摘要已保存到: {summary_file}")
            
        except Exception as e:
            print(f"🐛 保存debug数据失败: {e}")
    
    def save_now(self):
        """立即保存当前会话数据"""
        if self.enabled:
            self._save_session()
    
    def clear_session(self):
        """清理当前会话数据"""
        self.session_data = {
            "session_info": {},
            "api_requests": [],
            "search_results": [],
            "workflow_steps": [],
            "research_results": [],
            "errors": []
        }
        self.current_session = None


# 全局debug实例
debug_logger = DebugLogger()


def enable_debug(output_dir: str = "debug_logs"):
    """启用全局debug模式"""
    debug_logger.enable(output_dir)


def disable_debug():
    """禁用全局debug模式"""
    debug_logger.disable()


def get_debug_logger() -> DebugLogger:
    """获取debug日志记录器实例"""
    return debug_logger 