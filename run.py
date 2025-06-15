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

    # 简单回调，直接打印到控制台
    def step_callback(message):
        print(f"[PROGRESS] {message}")

    engine = ResearchEngine(api_key=api_key)
    engine.set_callbacks(step_callback=step_callback)
    
    try:
        query = "2024年AI技术的主要发展趋势是什么？"
        print(f"🚀 开始研究: {query}")
        
        results = await engine.research(user_query=query)
        
        if results.get("success"):
            print("\n✅ 研究完成！")
            print("="*20 + " 最终答案 " + "="*20)
            print(results.get("final_answer", "没有最终答案。"))
            print("="*50)
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