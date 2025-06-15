#!/usr/bin/env python3
"""
DeepSearch 启动脚本
简化版本 - 直接启动主应用
"""

import os
import sys
import subprocess
import time
import asyncio
from core.research_engine import ResearchEngine

def check_dependencies():
    """检查依赖是否已安装"""
    try:
        import streamlit
        import google.generativeai
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

async def main():
    """主异步函数，用于命令行研究"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("错误：请设置 GEMINI_API_KEY 环境变量")
        return

    engine = ResearchEngine(api_key=api_key)
    
    try:
        # 示例：执行一次研究
        query = "2024年AI技术的主要发展趋势是什么？"
        print(f"🚀 开始研究: {query}")
        
        results = await engine.research(
            user_query=query,
            max_search_rounds=3,
            effort_level="medium",
            num_search_queries=3
        )
        
        if results.get("success"):
            print("\n✅ 研究完成！")
            print("="*20 + " 最终答案 " + "="*20)
            print(results.get("final_answer", "没有最终答案。"))
            print("="*50)
        else:
            print(f"\n❌ 研究失败: {results.get('error', '未知错误')}")

    finally:
        # 确保客户端被关闭
        await engine.close_clients()
        print("✅ 客户端已关闭。")

def main_streamlit():
    """主函数"""
    print("🔍 DeepSearch - 智能深度研究助手")
    print("=" * 50)
    
    # 检查当前目录
    if not os.path.exists("app.py"):
        print("❌ 未找到 app.py 文件")
        print("请确保在 deepsearch 目录中运行此脚本")
        return 1
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    print("🚀 启动 DeepSearch...")
    
    try:
        # 启动 Streamlit 应用
        cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port=8531"]
        
        print(f"💡 应用将在浏览器中打开: http://localhost:8531")
        print("📝 按 Ctrl+C 停止应用")
        print("-" * 50)
        
        # 启动应用
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n👋 应用已停止")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        return 1
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        return 1

if __name__ == "__main__":
    # 启用调试日志
    asyncio.run(main())
    sys.exit(main_streamlit()) 