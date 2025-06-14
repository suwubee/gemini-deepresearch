#!/usr/bin/env python3
"""
测试双模式API功能的简单脚本
"""

import os
import sys
import asyncio
from core.api_config import APIConfig, APIMode, ModelConfig
from core.api_factory import APIClientFactory
from core.research_engine import ResearchEngine

async def test_dual_mode():
    """测试双模式功能"""
    
    # 检查环境变量
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 请设置 GEMINI_API_KEY 环境变量")
        return
    
    print("🔍 DeepSearch 双模式API测试")
    print("=" * 50)
    
    # 测试1: Google GenAI模式
    print("\n📋 测试1: Google GenAI模式")
    try:
        engine_genai = ResearchEngine(
            api_key=api_key,
            model_name="gemini-2.0-flash",
            preferred_mode=APIMode.GENAI
        )
        
        client_info = engine_genai.get_client_info()
        print(f"✅ GenAI模式初始化成功")
        print(f"   搜索客户端: {client_info['search_client']['type']}")
        print(f"   工作流客户端: {client_info['workflow_client']['type']}")
        
        await engine_genai.close_clients()
        
    except Exception as e:
        print(f"❌ GenAI模式测试失败: {e}")
    
    # 测试2: OpenAI兼容模式（如果有OpenAI API密钥）
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("\n📋 测试2: OpenAI兼容模式")
        try:
            # 配置OpenAI模式
            APIConfig.update_global_setting("openai_api_key", openai_key)
            
            engine_openai = ResearchEngine(
                api_key=openai_key,
                model_name="gpt-3.5-turbo",
                preferred_mode=APIMode.OPENAI
            )
            
            client_info = engine_openai.get_client_info()
            print(f"✅ OpenAI模式初始化成功")
            print(f"   搜索客户端: {client_info['search_client']['type']}")
            print(f"   工作流客户端: {client_info['workflow_client']['type']}")
            
            await engine_openai.close_clients()
            
        except Exception as e:
            print(f"❌ OpenAI模式测试失败: {e}")
    else:
        print("\n⚠️  跳过OpenAI模式测试（未设置OPENAI_API_KEY）")
    
    # 测试3: 配置管理
    print("\n📋 测试3: 配置管理")
    try:
        # 添加自定义模型配置
        custom_model = ModelConfig(
            name="test-model",
            mode=APIMode.OPENAI,
            supports_search=False,
            supports_tools=True,
            base_url="https://api.example.com/v1",
            default_params={"temperature": 0.5, "max_tokens": 2048}
        )
        
        APIConfig.add_model_config("test-model", custom_model)
        
        available_models = APIConfig.get_available_models()
        if "test-model" in available_models:
            print("✅ 自定义模型配置成功")
        else:
            print("❌ 自定义模型配置失败")
            
    except Exception as e:
        print(f"❌ 配置管理测试失败: {e}")
    
    # 测试4: 客户端工厂
    print("\n📋 测试4: 客户端工厂")
    try:
        factory = APIClientFactory()
        
        # 测试GenAI客户端创建
        genai_client = factory.create_client(
            model_name="gemini-2.0-flash",
            api_key=api_key,
            preferred_mode=APIMode.GENAI
        )
        
        print(f"✅ GenAI客户端创建成功: {type(genai_client).__name__}")
        
        # 测试客户端能力
        print(f"   支持搜索: {genai_client.supports_search()}")
        print(f"   支持工具: {genai_client.supports_tools()}")
        
    except Exception as e:
        print(f"❌ 客户端工厂测试失败: {e}")
    
    print("\n🎉 双模式API测试完成！")

def main():
    """主函数"""
    try:
        asyncio.run(test_dual_mode())
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")

if __name__ == "__main__":
    main() 