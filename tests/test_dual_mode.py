"""
双模式API架构测试
"""

import pytest
import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api_config import APIConfig, APIMode, ModelConfig
from core.api_factory import APIClientFactory
from core.api_client import GoogleGenAIClient, OpenAICompatibleClient


class TestAPIConfig:
    """测试API配置管理"""
    
    def test_model_config_creation(self):
        """测试模型配置创建"""
        config = ModelConfig(
            name="test-model",
            mode=APIMode.GENAI,
            supports_search=True,
            supports_tools=False
        )
        
        assert config.name == "test-model"
        assert config.mode == APIMode.GENAI
        assert config.supports_search == True
        assert config.supports_tools == False
    
    def test_get_model_config(self):
        """测试获取模型配置"""
        config = APIConfig.get_model_config("gemini-2.0-flash")
        
        assert config is not None
        assert config.name == "gemini-2.0-flash"
        assert config.supports_search == True
        assert config.mode == APIMode.AUTO
    
    def test_effective_mode_determination(self):
        """测试有效模式确定"""
        # 测试AUTO模式
        mode = APIConfig.get_effective_mode("gemini-2.0-flash", APIMode.GENAI)
        assert mode == APIMode.GENAI
        
        # 测试固定模式
        mode = APIConfig.get_effective_mode("gemini-2.5-flash")
        assert mode == APIMode.GENAI
    
    def test_supports_search(self):
        """测试搜索支持检查"""
        assert APIConfig.supports_search("gemini-2.0-flash") == True
        assert APIConfig.supports_search("gemini-2.5-flash") == False
        assert APIConfig.supports_search("gpt-4") == False
    
    def test_add_model_config(self):
        """测试动态添加模型配置"""
        test_config = ModelConfig(
            name="test-custom-model",
            mode=APIMode.OPENAI,
            supports_search=False,
            supports_tools=True
        )
        
        APIConfig.add_model_config("test-custom-model", test_config)
        
        retrieved_config = APIConfig.get_model_config("test-custom-model")
        assert retrieved_config is not None
        assert retrieved_config.name == "test-custom-model"
        assert retrieved_config.mode == APIMode.OPENAI


class TestAPIClientFactory:
    """测试API客户端工厂"""
    
    @pytest.fixture
    def mock_api_key(self):
        """模拟API密钥"""
        return "test_api_key_12345678901234567890"
    
    def test_create_genai_client(self, mock_api_key):
        """测试创建Google GenAI客户端"""
        client = APIClientFactory.create_client(
            api_key=mock_api_key,
            model_name="gemini-2.0-flash",
            preferred_mode=APIMode.GENAI
        )
        
        assert isinstance(client, GoogleGenAIClient)
        assert client.model_name == "gemini-2.0-flash"
        assert client.api_key == mock_api_key
    
    def test_create_openai_client(self, mock_api_key):
        """测试创建OpenAI兼容客户端"""
        client = APIClientFactory.create_client(
            api_key=mock_api_key,
            model_name="gpt-4",
            preferred_mode=APIMode.OPENAI
        )
        
        assert isinstance(client, OpenAICompatibleClient)
        assert client.model_name == "gpt-4"
        assert client.api_key == mock_api_key
    
    def test_create_search_client(self, mock_api_key):
        """测试创建搜索客户端"""
        client = APIClientFactory.create_search_client(
            api_key=mock_api_key,
            model_name="gemini-2.0-flash"
        )
        
        assert client.supports_search() == True
        assert client.model_name == "gemini-2.0-flash"
    
    def test_create_analysis_client(self, mock_api_key):
        """测试创建分析客户端"""
        client = APIClientFactory.create_analysis_client(
            api_key=mock_api_key,
            model_name="gemini-2.5-flash-preview-05-20"
        )
        
        assert client.model_name == "gemini-2.5-flash-preview-05-20"
    
    def test_get_client_info(self):
        """测试获取客户端信息"""
        info = APIClientFactory.get_client_info("gemini-2.0-flash")
        
        assert "model_name" in info
        assert "mode" in info
        assert "supports_search" in info
        assert "supports_tools" in info
        assert info["model_name"] == "gemini-2.0-flash"
        assert info["supports_search"] == True
    
    def test_list_available_models(self):
        """测试列出可用模型"""
        models = APIClientFactory.list_available_models()
        
        assert isinstance(models, dict)
        assert "gemini-2.0-flash" in models
        assert "gemini-2.5-flash" in models
        assert "gpt-4" in models
    
    def test_validate_configuration(self, mock_api_key):
        """测试配置验证"""
        result = APIClientFactory.validate_configuration(
            api_key=mock_api_key,
            model_name="gemini-2.0-flash",
            preferred_mode=APIMode.GENAI
        )
        
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "info" in result
        assert result["valid"] == True
    
    def test_validate_invalid_configuration(self):
        """测试无效配置验证"""
        result = APIClientFactory.validate_configuration(
            api_key="short",  # 太短的API密钥
            model_name="invalid-model",  # 不存在的模型
            preferred_mode=APIMode.GENAI
        )
        
        assert result["valid"] == False
        assert len(result["errors"]) > 0
    
    def test_client_caching(self, mock_api_key):
        """测试客户端缓存"""
        # 清理缓存
        APIClientFactory.clear_cache()
        
        # 创建第一个客户端
        client1 = APIClientFactory.create_client(
            api_key=mock_api_key,
            model_name="gemini-2.0-flash",
            preferred_mode=APIMode.GENAI
        )
        
        # 创建第二个相同配置的客户端
        client2 = APIClientFactory.create_client(
            api_key=mock_api_key,
            model_name="gemini-2.0-flash",
            preferred_mode=APIMode.GENAI
        )
        
        # 应该返回缓存的客户端
        assert client1 is client2
        
        # 检查缓存统计
        stats = APIClientFactory.get_cache_stats()
        assert stats["cached_clients"] >= 1


class TestAPIClients:
    """测试API客户端"""
    
    @pytest.fixture
    def mock_api_key(self):
        """模拟API密钥"""
        return "test_api_key_12345678901234567890"
    
    def test_google_genai_client_initialization(self, mock_api_key):
        """测试Google GenAI客户端初始化"""
        client = GoogleGenAIClient(mock_api_key, "gemini-2.0-flash")
        
        assert client.api_key == mock_api_key
        assert client.model_name == "gemini-2.0-flash"
        assert client.supports_search() == True
        assert client.supports_tools() == True
    
    def test_openai_compatible_client_initialization(self, mock_api_key):
        """测试OpenAI兼容客户端初始化"""
        client = OpenAICompatibleClient(
            mock_api_key, 
            "gpt-4",
            base_url="https://api.openai.com/v1"
        )
        
        assert client.api_key == mock_api_key
        assert client.model_name == "gpt-4"
        assert client.base_url == "https://api.openai.com/v1"
        assert client.supports_search() == False
        assert client.supports_tools() == True
    
    def test_get_default_params(self, mock_api_key):
        """测试获取默认参数"""
        client = GoogleGenAIClient(mock_api_key, "gemini-2.0-flash")
        params = client.get_default_params()
        
        assert isinstance(params, dict)
        assert "temperature" in params
        assert "max_output_tokens" in params


@pytest.mark.asyncio
class TestAsyncFunctionality:
    """测试异步功能"""
    
    @pytest.fixture
    def mock_api_key(self):
        """模拟API密钥"""
        return "test_api_key_12345678901234567890"
    
    async def test_client_cleanup(self, mock_api_key):
        """测试客户端清理"""
        client = OpenAICompatibleClient(
            mock_api_key,
            "gpt-4",
            base_url="https://api.openai.com/v1"
        )
        
        # 确保会话被创建
        await client._ensure_session()
        assert client.session is not None
        
        # 测试清理
        await client.close()
        assert client.session is None


class TestGlobalSettings:
    """测试全局设置"""
    
    def test_dual_mode_enabled(self):
        """测试双模式启用状态"""
        enabled = APIConfig.is_dual_mode_enabled()
        assert isinstance(enabled, bool)
        assert enabled == True  # 默认应该启用
    
    def test_global_setting_update(self):
        """测试全局设置更新"""
        original_value = APIConfig.get_global_setting("debug_mode")
        
        # 更新设置
        APIConfig.update_global_setting("debug_mode", True)
        assert APIConfig.get_global_setting("debug_mode") == True
        
        # 恢复原值
        APIConfig.update_global_setting("debug_mode", original_value)
    
    def test_available_models(self):
        """测试可用模型列表"""
        models = APIConfig.get_available_models()
        
        assert isinstance(models, list)
        assert "gemini-2.0-flash" in models
        assert "gemini-2.5-flash" in models
        assert len(models) > 0
    
    def test_models_by_mode(self):
        """测试按模式获取模型"""
        genai_models = APIConfig.get_models_by_mode(APIMode.GENAI)
        openai_models = APIConfig.get_models_by_mode(APIMode.OPENAI)
        
        assert isinstance(genai_models, list)
        assert isinstance(openai_models, list)
        assert "gemini-2.0-flash" in genai_models
        assert "gpt-4" in openai_models


def run_tests():
    """运行所有测试"""
    print("🧪 开始运行双模式API架构测试...")
    
    # 运行pytest
    pytest_args = [
        __file__,
        "-v",  # 详细输出
        "--tb=short",  # 简短的traceback
    ]
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败，请检查输出")
    
    return exit_code


if __name__ == "__main__":
    run_tests() 