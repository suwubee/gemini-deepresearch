#!/usr/bin/env python3
"""
DeepSearch 启动脚本
简化版本 - 直接启动主应用
"""

import os
import sys
import asyncio
from core.research_engine import ResearchEngine
from utils.debug_logger import enable_debug

async def main():
    """主异步函数，用于命令行研究"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("错误：请在.env文件中或作为环境变量设置您的GEMINI_API_KEY。")
        return

    # 详细回调，直接打印到控制台
    step_counter = 1
    def step_callback(message):
        nonlocal step_counter
        print(f"{step_counter}. ⚡ {message}")
        step_counter += 1
    
    def progress_callback(message, percentage):
        print(f"{step_counter}. [{percentage:.1f}%] {message}")

    engine = ResearchEngine(api_key=api_key)
    engine.set_callbacks(step_callback=step_callback, progress_callback=progress_callback)
    
    try:
        query = "分析2025年人工智能的趋势"
        print(f"📝 思考过程")
        print(f"1. 🚀 研究任务已启动...")
        
        results = await engine.research(user_query=query)
        
        if results.get("success"):
            print("\n✅ 研究完成！")
            
            # 尝试从不同位置获取最终答案
            final_answer = None
            task_summary = results.get("task_summary", {})
            
            # 检查多个可能的位置
            if "final_answer" in results:
                final_answer = results["final_answer"]
            elif "final_result" in results:
                final_answer = results["final_result"]
            elif task_summary and "final_answer" in task_summary:
                final_answer = task_summary["final_answer"]
            else:
                print(f"🔍 调试信息 - results结构: {list(results.keys())}")
                if task_summary:
                    print(f"🔍 调试信息 - task_summary结构: {list(task_summary.keys())}")
            
            if final_answer:
                print("="*20 + " 最终答案 " + "="*20)
                print(final_answer)
                print("="*50)
            else:
                print("⚠️ 警告：未找到最终答案")
                print("🔍 调试信息 - 完整results:")
                print(results)
        else:
            print(f"\n❌ 研究失败: {results.get('error', '未知错误')}")

    except Exception as e:
        print(f"发生未捕获的异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保客户端被关闭
        await engine.close_clients()
        print("✅ 客户端已关闭。")

if __name__ == "__main__":
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    enable_debug()
    asyncio.run(main()) 