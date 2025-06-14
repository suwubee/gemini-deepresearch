# 🚀 双模式API架构指南

## 📋 概述

DeepSearch项目现已支持**双模式API架构**，允许您在Google GenAI SDK和OpenAI兼容HTTP API之间灵活切换。这种设计提供了更好的兼容性、灵活性和扩展性。

## 🏗️ 架构设计

### 核心组件

```
双模式API架构
├── 📁 core/
│   ├── api_config.py       # 配置管理系统
│   ├── api_client.py       # 抽象客户端层
│   ├── api_factory.py      # 客户端工厂
│   ├── search_agent.py     # 搜索代理（已升级）
│   ├── workflow_builder.py # 工作流构建器（已升级）
│   └── research_engine.py  # 研究引擎（已升级）
└── 📁 examples/
    └── dual_mode_example.py # 使用示例
```

### 抽象层设计

```python
BaseAPIClient (抽象基类)
├── GoogleGenAIClient     # Google GenAI SDK客户端
└── OpenAICompatibleClient # OpenAI兼容HTTP客户端
```

## 🎯 特性概览

### ✅ 支持的功能

- **🔄 双模式切换**: 运行时动态切换API模式
- **🏭 工厂模式**: 统一的客户端创建和管理
- **⚙️ 配置驱动**: 灵活的模型和模式配置
- **📊 智能缓存**: 客户端实例缓存和复用
- **🔍 搜索功能**: 完整保留Gemini 2.0的搜索能力
- **🛡️ 错误处理**: 完善的降级和重试机制
- **📝 调试支持**: 完整的API请求/响应日志

### 🎨 模式对比

| 特性 | Google GenAI | OpenAI兼容 |
|------|-------------|------------|
| 搜索功能 | ✅ 原生支持 | ❌ 需要外部实现 |
| Grounding元数据 | ✅ 完整支持 | ❌ 不支持 |
| 工具调用 | ✅ 支持 | ✅ 支持 |
| HTTP控制 | ❌ SDK封装 | ✅ 完全控制 |
| 调试友好 | ⭕ 中等 | ✅ 优秀 |
| 跨平台兼容 | ⭕ 依赖SDK | ✅ 标准HTTP |

## 🔧 配置管理

### 模型配置

```python
from core.api_config import APIConfig, APIMode, ModelConfig

# 查看可用模型
models = APIConfig.get_available_models()

# 添加自定义模型
custom_model = ModelConfig(
    name="custom-model",
    mode=APIMode.OPENAI,
    supports_search=False,
    supports_tools=True,
    base_url="https://api.custom.com/v1",
    default_params={"temperature": 0.2}
)
APIConfig.add_model_config("custom-model", custom_model)
```

### 全局设置

```python
# 启用/禁用双模式
APIConfig.update_global_setting("enable_dual_mode", True)

# 设置Gemini 2.0的优先模式
APIConfig.update_global_setting("gemini_2_0_preferred_mode", APIMode.GENAI)

# 检查配置
print(f"双模式启用: {APIConfig.is_dual_mode_enabled()}")
```

## 🚀 使用指南

### 基本使用

```python
from core.research_engine import ResearchEngine
from core.api_config import APIMode

# 方式1: 使用默认模式
engine = ResearchEngine(
    api_key="your_api_key",
    model_name="gemini-2.0-flash"
)

# 方式2: 指定API模式
engine = ResearchEngine(
    api_key="your_api_key", 
    model_name="gemini-2.0-flash",
    preferred_mode=APIMode.GENAI
)

# 方式3: 使用配置创建
engine = ResearchEngine.create_with_config(
    api_key="your_api_key",
    model_name="gemini-2.5-pro",
    preferred_mode="openai"  # 字符串自动转换
)
```

### 客户端管理

```python
from core.api_factory import APIClientFactory, ClientManager

# 创建特定用途的客户端
search_client = APIClientFactory.create_search_client(
    api_key="your_api_key",
    model_name="gemini-2.0-flash"
)

analysis_client = APIClientFactory.create_analysis_client(
    api_key="your_api_key", 
    model_name="gemini-2.5-flash"
)

# 使用客户端管理器
manager = ClientManager("your_api_key")
search_client = manager.get_search_client()
analysis_client = manager.get_analysis_client()

# 清理资源
await manager.close_all()
```

### 模式切换

```python
# 运行时切换模式
engine.switch_mode(APIMode.OPENAI)

# 查看客户端信息
client_info = engine.get_client_info()
print(f"搜索客户端类型: {client_info['search_client']['type']}")
print(f"支持搜索: {client_info['search_client']['supports_search']}")
```

## 📊 配置选项

### 模型配置示例

```python
# Gemini模型配置
"gemini-2.0-flash": ModelConfig(
    name="gemini-2.0-flash",
    mode=APIMode.AUTO,  # 可选择模式
    supports_search=True,
    supports_tools=True,
    fallback_search=True,
    default_params={
        "temperature": 0.1,
        "max_output_tokens": 8192
    }
)

# OpenAI兼容模型配置
"gpt-4": ModelConfig(
    name="gpt-4",
    mode=APIMode.OPENAI,
    supports_search=False,
    supports_tools=True,
    base_url="https://api.openai.com/v1",
    headers={"Content-Type": "application/json"},
    default_params={
        "temperature": 0.3,
        "max_tokens": 4096
    }
)
```

### OpenAI兼容服务配置

```python
OPENAI_COMPATIBLE_CONFIGS = {
    "default": OpenAICompatibleConfig(
        base_url="https://api.openai.com/v1",
        headers={"Content-Type": "application/json"},
        timeout=30,
        retry_count=3
    ),
    "custom": OpenAICompatibleConfig(
        base_url="https://api.your-provider.com/v1",
        headers={"Content-Type": "application/json"},
        timeout=60,
        retry_count=2
    )
}
```

## 🔍 搜索功能处理

### Gemini 2.0 原生搜索

```python
# 支持完整的搜索功能
result = await search_agent.search_with_grounding(
    query="AI发展趋势2024",
    use_search=True
)

print(f"有Grounding: {result['has_grounding']}")
print(f"搜索查询: {result['search_queries']}")
print(f"引用数量: {len(result['citations'])}")
```

### OpenAI兼容模式的搜索降级

```python
# 自动降级到普通对话模式
# 如果需要搜索功能，需要实现外部搜索API集成
```

## 🛡️ 错误处理与降级

### 自动降级策略

1. **API调用失败**: 自动重试，超过限制后降级到简单模式
2. **模型不支持搜索**: 自动警告并使用普通对话模式
3. **配置验证失败**: 提供详细错误信息和修复建议
4. **网络连接问题**: 自动重试和超时处理

### 调试和监控

```python
# 启用调试模式
APIConfig.update_global_setting("debug_mode", True)

# 查看缓存统计
cache_stats = APIClientFactory.get_cache_stats()
print(f"缓存的客户端: {cache_stats['cached_clients']}")

# 验证配置
validation = APIClientFactory.validate_configuration(
    api_key="your_api_key",
    model_name="gemini-2.0-flash"
)
print(f"配置有效: {validation['valid']}")
```

## 📈 性能优化

### 客户端缓存

- **智能缓存**: 自动缓存和复用客户端实例
- **缓存键管理**: 基于模型名、模式、配置生成唯一键
- **内存管理**: 自动清理无效缓存

### 速率限制

- **请求间隔**: Google API 2秒间隔，OpenAI 0.5秒间隔
- **自动调节**: 根据API提供商自动调整
- **并发控制**: 避免超过API限制

## 🔮 扩展指南

### 添加新的API提供商

1. **继承BaseAPIClient**
2. **实现抽象方法**
3. **添加到工厂类**
4. **更新配置系统**

```python
class CustomAPIClient(BaseAPIClient):
    def supports_search(self) -> bool:
        return False
    
    def supports_tools(self) -> bool:
        return True
    
    async def generate_content(self, prompt: str, **kwargs) -> APIResponse:
        # 实现自定义API调用逻辑
        pass
```

### 自定义配置

```python
# 添加自定义全局设置
APIConfig.GLOBAL_SETTINGS["custom_setting"] = "value"

# 添加自定义OpenAI兼容配置
APIConfig.OPENAI_COMPATIBLE_CONFIGS["my_provider"] = OpenAICompatibleConfig(
    base_url="https://api.myprovider.com/v1",
    headers={"Authorization": "Bearer {api_key}"},
    timeout=45
)
```

## 🎯 最佳实践

1. **模式选择**: 
   - 需要搜索功能时使用Gemini模式
   - 需要精确HTTP控制时使用OpenAI模式

2. **资源管理**: 
   - 始终调用`close_clients()`清理资源
   - 使用ClientManager统一管理多个客户端

3. **错误处理**: 
   - 检查`APIResponse.success`状态
   - 处理`APIResponse.error`信息

4. **配置验证**: 
   - 使用`validate_configuration()`验证设置
   - 监听配置错误和警告

5. **性能优化**: 
   - 复用客户端实例避免重复初始化
   - 合理设置Token限制和超时时间

## 📝 示例代码

完整的使用示例请参考：
- `examples/dual_mode_example.py` - 完整功能演示
- `core/` 目录中的各个模块 - 具体实现细节

## 🤝 贡献指南

1. **添加新功能**: 遵循现有的抽象层设计
2. **修改配置**: 保持向后兼容性
3. **测试**: 确保双模式都能正常工作
4. **文档**: 更新相关文档和示例

---

**双模式API架构** - 让您的AI应用更加灵活和强大! 🚀 