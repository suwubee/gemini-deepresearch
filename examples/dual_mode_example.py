"""
双模式API使用示例
演示如何使用新的双模式架构：Google GenAI SDK 和 OpenAI兼容 HTTP API
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.research_engine import ResearchEngine
from core.api_config import APIConfig, APIMode, ModelConfig
from core.api_factory import APIClientFactory


async def example_basic_usage():
    """基本使用示例"""
    print("🔴 基本使用示例")
    print("=" * 50)
    
    api_key = os.getenv("GEMINI_API_KEY", "your_api_key_here")
    
    # 创建研究引擎 - 默认模式
    engine = ResearchEngine(
        api_key=api_key,
        model_name="gemini-2.0-flash"
    )
    
    # 查看客户端信息
    print("📊 客户端信息:")
    client_info = engine.get_client_info()
    print(f"  搜索客户端: {client_info['search_client']['type']}")
    print(f"  工作流客户端: {client_info['workflow_client']['type']}")
    print(f"  双模式启用: {client_info['dual_mode_enabled']}")
    
    # 执行简单研究
    try:
        result = await engine.research(
            user_query="AI发展趋势2024年",
            max_search_rounds=2,
            effort_level="low",
            num_search_queries=2
        )
        
        print(f"✅ 研究完成: {result['success']}")
        print(f"📄 答案长度: {len(result.get('final_answer', ''))}")
        print(f"🔗 引用数量: {len(result.get('citations', []))}")
        
    except Exception as e:
        print(f"❌ 研究失败: {e}")
    
    # 清理
    await engine.close_clients()


async def example_mode_switching():
    """模式切换示例"""
    print("\n🟡 模式切换示例")
    print("=" * 50)
    
    api_key = os.getenv("GEMINI_API_KEY", "your_api_key_here")
    
    # 测试不同模式
    modes = [APIMode.GENAI, APIMode.OPENAI]
    
    for mode in modes:
        print(f"\n🔧 测试 {mode.value} 模式:")
        
        try:
            # 创建引擎并指定模式
            engine = ResearchEngine(
                api_key=api_key,
                model_name="gemini-2.0-flash",
                preferred_mode=mode
            )
            
            # 显示客户端信息
            client_info = engine.get_client_info()
            print(f"  搜索客户端类型: {client_info['search_client']['type']}")
            print(f"  支持搜索: {client_info['search_client']['supports_search']}")
            
            # 执行简单搜索测试
            result = await engine.search_agent.search_with_grounding(
                "什么是人工智能？",
                use_search=True
            )
            
            print(f"  搜索成功: {result.get('success', False)}")
            print(f"  内容长度: {len(result.get('content', ''))}")
            print(f"  有引用: {result.get('has_grounding', False)}")
            
            await engine.close_clients()
            
        except Exception as e:
            print(f"  ❌ {mode.value} 模式测试失败: {e}")


async def example_configuration():
    """配置管理示例"""
    print("\n🟢 配置管理示例")
    print("=" * 50)
    
    # 查看可用模型
    print("📋 可用模型:")
    models_info = APIClientFactory.list_available_models()
    for model_name, info in models_info.items():
        print(f"  {model_name}:")
        print(f"    模式: {info['mode']}")
        print(f"    支持搜索: {info['supports_search']}")
        print(f"    支持工具: {info['supports_tools']}")
    
    # 查看全局设置
    print(f"\n⚙️ 全局设置:")
    print(f"  双模式启用: {APIConfig.is_dual_mode_enabled()}")
    print(f"  默认模式: {APIConfig.DEFAULT_MODE.value}")
    print(f"  Gemini 2.0优先模式: {APIConfig.get_global_setting('gemini_2_0_preferred_mode').value}")
    
    # 动态添加模型配置
    print(f"\n🔧 动态配置示例:")
    
    # 添加自定义模型配置
    custom_model = ModelConfig(
        name="custom-gpt-4",
        mode=APIMode.OPENAI,
        supports_search=False,
        supports_tools=True,
        base_url="https://api.custom-provider.com/v1",
        default_params={"temperature": 0.2, "max_tokens": 2048}
    )
    
    APIConfig.add_model_config("custom-gpt-4", custom_model)
    print(f"  添加自定义模型: custom-gpt-4")
    
    # 验证配置
    api_key = os.getenv("GEMINI_API_KEY", "your_api_key_here")
    validation = APIClientFactory.validate_configuration(
        api_key=api_key,
        model_name="gemini-2.0-flash",
        preferred_mode=APIMode.GENAI
    )
    
    print(f"  配置验证: {'✅ 有效' if validation['valid'] else '❌ 无效'}")
    if validation['errors']:
        print(f"  错误: {validation['errors']}")
    if validation['warnings']:
        print(f"  警告: {validation['warnings']}")


async def example_advanced_usage():
    """高级使用示例"""
    print("\n🔵 高级使用示例")
    print("=" * 50)
    
    api_key = os.getenv("GEMINI_API_KEY", "your_api_key_here")
    
    # 使用配置创建引擎
    engine = ResearchEngine.create_with_config(
        api_key=api_key,
        model_name="gemini-2.5-pro-preview-06-05",
        preferred_mode="genai"  # 字符串会自动转换
    )
    
    print("🎯 使用配置创建的引擎:")
    client_info = engine.get_client_info()
    print(f"  搜索模型: {client_info['search_client']['model']}")
    print(f"  工作流模型: {client_info['workflow_client']['model']}")
    
    # 切换模式
    print(f"\n🔄 切换到OpenAI模式:")
    try:
        engine.switch_mode(APIMode.OPENAI)
        new_info = engine.get_client_info()
        print(f"  新搜索客户端: {new_info['search_client']['type']}")
    except Exception as e:
        print(f"  切换失败: {e}")
    
    # 获取缓存统计
    cache_stats = APIClientFactory.get_cache_stats()
    print(f"\n📊 客户端缓存统计:")
    print(f"  缓存的客户端数量: {cache_stats['cached_clients']}")
    print(f"  缓存键: {cache_stats['cache_keys']}")
    
    # 清理
    await engine.close_clients()
    APIClientFactory.clear_cache()


async def main():
    """主函数"""
    print("🚀 双模式API架构示例")
    print("=" * 50)
    
    # 检查API密钥
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("⚠️ 请设置GEMINI_API_KEY环境变量")
        print("   export GEMINI_API_KEY='your_actual_api_key'")
        return
    
    try:
        # 运行所有示例
        await example_basic_usage()
        await example_mode_switching()
        await example_configuration()
        await example_advanced_usage()
        
        print("\n✅ 所有示例执行完成！")
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 