#!/usr/bin/env python3
"""
双模式API测试脚本
测试GenAI和OpenAI两种模式的基本功能
"""

import os
import sys
from core.research_engine import ResearchEngine
from core.api_config import APIMode

def test_genai_mode():
    """测试GenAI模式"""
    print("🔍 测试GenAI模式...")
    print("=" * 40)
    
    # 检查API密钥
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 请设置 GEMINI_API_KEY 环境变量")
        return False
    
    try:
        # 创建GenAI模式的研究引擎
        engine = ResearchEngine(
            api_key=api_key,
            model_name="gemini-2.0-flash",
            api_mode=APIMode.GENAI
        )
        print("✅ GenAI引擎创建成功")
        
        # 测试基本搜索
        print("\n🔍 测试搜索功能...")
        search_result = engine.search_agent.search_with_grounding("什么是人工智能?")
        
        if search_result.get("success"):
            print("✅ GenAI搜索测试成功")
            print(f"  查询: {search_result['query']}")
            print(f"  内容长度: {len(search_result.get('content', ''))}")
            print(f"  有引用: {search_result.get('has_grounding', False)}")
            print(f"  引用数量: {len(search_result.get('citations', []))}")
            return True
        else:
            print(f"❌ GenAI搜索测试失败: {search_result.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        print(f"❌ GenAI模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_openai_mode():
    """测试OpenAI模式"""
    print("\n🔍 测试OpenAI模式...")
    print("=" * 40)
    
    # 检查API密钥
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 请设置 OPENAI_API_KEY 环境变量")
        return False
    
    try:
        # 创建OpenAI模式的研究引擎
        engine = ResearchEngine(
            api_key="dummy",  # GenAI key不用，但需要占位
            model_name="gpt-3.5-turbo",
            api_mode=APIMode.OPENAI,
            openai_api_key=api_key,
            base_url="https://api.openai.com/v1"
        )
        print("✅ OpenAI引擎创建成功")
        
        # 测试基本生成（OpenAI不支持grounding搜索）
        print("\n📝 测试文本生成...")
        search_result = engine.search_agent.search_with_grounding("什么是人工智能?", use_search=False)
        
        if search_result.get("success"):
            print("✅ OpenAI生成测试成功")
            print(f"  查询: {search_result['query']}")
            print(f"  内容长度: {len(search_result.get('content', ''))}")
            print(f"  支持搜索: {search_result.get('has_grounding', False)}")
            return True
        else:
            print(f"❌ OpenAI生成测试失败: {search_result.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        print(f"❌ OpenAI模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 双模式API测试开始")
    print("=" * 50)
    
    # 测试GenAI模式
    genai_success = test_genai_mode()
    
    # 测试OpenAI模式
    openai_success = test_openai_mode()
    
    # 总结
    print("\n📊 测试总结")
    print("=" * 50)
    print(f"GenAI模式: {'✅ 成功' if genai_success else '❌ 失败'}")
    print(f"OpenAI模式: {'✅ 成功' if openai_success else '❌ 失败'}")
    
    if genai_success or openai_success:
        print("\n🎉 至少一种模式工作正常！")
        return 0
    else:
        print("\n💥 所有模式都失败了，请检查配置")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 