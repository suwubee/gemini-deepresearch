# 🔍 DeepSearch 双模式API配置指南

## 📋 概述

DeepSearch现在支持双模式API架构，您可以在Streamlit界面中灵活配置和切换不同的API模式：

- **🔵 Google GenAI SDK模式** - 使用官方SDK，功能完整，支持搜索
- **🟠 OpenAI兼容HTTP API模式** - 支持任何OpenAI兼容的API服务
- **🔄 自动选择模式** - 根据模型自动选择最佳API模式

## 🚀 快速开始

### 1. 启动应用

```bash
streamlit run app.py
```

### 2. 配置API模式

在左侧边栏的"🔧 API配置"部分：

#### Google GenAI模式（推荐）
1. 选择"🔵 Google GenAI SDK (推荐)"
2. 输入您的Gemini API密钥
3. 配置完成！

#### OpenAI兼容模式
1. 选择"🟠 OpenAI兼容 HTTP API"
2. 配置Base URL（如：`https://api.openai.com/v1`）
3. 输入API密钥
4. 设置请求超时时间
5. 配置完成！

## 🎯 高级模型配置

### 任务专用模型

在"🎯 模型配置"部分，您可以为不同任务配置专用模型：

- **搜索模型** - 用于网络搜索和信息检索
- **任务分析模型** - 用于分析用户查询和构建工作流
- **反思分析模型** - 用于分析搜索结果和优化策略
- **答案生成模型** - 用于合成最终答案

### 自定义模型

在"➕ 自定义模型"部分添加您的自定义模型：

1. 输入模型名称（如：`gpt-4-custom`）
2. 设置Base URL
3. 配置模型能力：
   - 支持搜索：是否支持grounding搜索
   - 支持工具调用：是否支持function calling
4. 设置参数：
   - Temperature：控制输出随机性
   - Max Tokens：最大输出长度

## 🔧 配置管理

### 导出配置
- 点击"📤 导出配置"按钮
- 下载JSON配置文件（不包含API密钥）
- 可用于备份或分享配置

### 导入配置
- 使用"📥 导入配置"上传之前导出的配置文件
- 自动应用所有设置（保留当前API密钥）

### 重置配置
- 点击"🔄 重置配置"恢复默认设置
- 保留当前的API密钥

## 📊 配置详情查看

在"📋 当前配置详情"展开面板中查看：

- 当前API模式
- 搜索客户端类型和模型
- 工作流客户端类型和模型
- Base URL（OpenAI模式时）
- 各任务的模型配置

## 🌐 支持的API服务

### 官方支持
- **Google Gemini API** - 完整功能支持
- **OpenAI API** - 标准OpenAI接口

### 兼容服务
任何支持OpenAI API格式的服务都可以使用，包括：

- **Azure OpenAI**
- **Anthropic Claude** (通过代理)
- **本地部署模型** (如Ollama、vLLM)
- **第三方API服务**

## ⚙️ 配置示例

### Azure OpenAI配置
```
API模式: OpenAI兼容 HTTP API
Base URL: https://your-resource.openai.azure.com/openai/deployments/your-deployment/
API Key: your-azure-api-key
```

### 本地Ollama配置
```
API模式: OpenAI兼容 HTTP API  
Base URL: http://localhost:11434/v1
API Key: ollama (任意值)
自定义模型: llama2, codellama等
```

### 第三方服务配置
```
API模式: OpenAI兼容 HTTP API
Base URL: https://api.third-party-service.com/v1
API Key: your-service-api-key
```

## 🔍 搜索功能说明

### Gemini 2.0搜索优势
- 使用Gemini 2.0的grounding搜索功能
- 实时网络信息检索
- 自动引用和来源标注
- 高质量搜索结果

### OpenAI模式搜索限制
- 大多数OpenAI兼容模型不支持实时搜索
- 会自动降级到基于知识库的回答
- 建议搜索任务仍使用Gemini模式

## 🐛 调试模式

启用"🐛 Debug模式"可以：
- 记录所有API请求和响应
- 保存到JSON文件用于调试
- 分析API调用性能
- 排查配置问题

## 💡 最佳实践

### 模式选择建议
1. **需要搜索功能** → 使用Google GenAI模式
2. **使用特定模型** → 配置OpenAI兼容模式
3. **成本优化** → 根据任务配置不同价格的模型
4. **本地部署** → 使用OpenAI兼容模式连接本地服务

### 模型配置建议
- **搜索模型**: gemini-2.0-flash（速度快，成本低）
- **任务分析**: gemini-2.5-flash（平衡性能和成本）
- **反思分析**: gemini-2.5-flash（中等复杂度任务）
- **答案生成**: gemini-2.5-pro（高质量输出）

### 性能优化
- 启用客户端缓存和复用
- 合理设置超时时间
- 根据任务复杂度选择模型
- 使用配置导出/导入快速切换环境

## 🔒 安全注意事项

- API密钥仅存储在浏览器本地
- 导出配置时会隐藏敏感信息
- 建议定期更换API密钥
- 使用HTTPS连接确保传输安全

## 🆘 故障排除

### 常见问题

**Q: OpenAI模式连接失败**
A: 检查Base URL格式，确保以`/v1`结尾

**Q: 自定义模型不可用**
A: 验证模型名称和API服务支持的模型列表

**Q: 搜索功能不工作**
A: 确保使用支持搜索的模型（推荐Gemini 2.0）

**Q: 配置丢失**
A: 检查浏览器LocalStorage，或重新导入配置文件

### 获取帮助
- 查看控制台错误信息
- 启用Debug模式分析API调用
- 检查网络连接和防火墙设置
- 验证API密钥权限和配额

---

通过这个双模式架构，DeepSearch为您提供了最大的灵活性和兼容性，让您可以根据具体需求选择最适合的API服务和模型配置。 