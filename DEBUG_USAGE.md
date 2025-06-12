# 🐛 Debug功能使用指南

Debug功能可以帮助您调试DeepSearch应用中的API请求和数据获取问题，将所有请求和响应数据保存到JSON文件中供分析。

## 📋 功能特点

- ✅ **API请求记录** - 记录所有发送到Gemini API的请求
- ✅ **API响应记录** - 记录所有来自API的响应数据
- ✅ **搜索结果记录** - 记录搜索功能的完整结果
- ✅ **工作流步骤记录** - 记录研究过程中的每个步骤
- ✅ **错误记录** - 记录所有错误和异常
- ✅ **会话摘要** - 生成统计摘要信息
- ✅ **大数据处理** - 自动截断过大的数据以避免文件过大

## 🚀 使用方法

### 1. 启用Debug模式

在DeepSearch应用的侧边栏中：

1. 确保您的API密钥已正确配置
2. 向下滚动到"🐛 Debug模式"部分
3. 勾选"启用调试模式"复选框
4. 您会看到提示："Debug模式已启用"

### 2. 进行研究操作

启用Debug模式后，正常使用DeepSearch进行研究：

1. 输入您的研究问题
2. 选择研究强度
3. 点击"🚀 开始研究"
4. Debug功能会在后台自动记录所有活动

### 3. 查看Debug统计

在Debug模式启用后，侧边栏会显示：

- 📝 **会话ID** - 当前debug会话的唯一标识
- 📊 **Debug统计** - 实时统计信息
  - API请求数量
  - 搜索次数
  - 错误数量

### 4. 保存Debug日志

- **自动保存**: 研究完成后自动保存
- **手动保存**: 点击"💾 保存Debug日志"按钮立即保存

## 📁 文件结构

Debug日志保存在 `debug_logs/` 目录下：

```
debug_logs/
├── debug_session_20250612_215439.json          # 完整会话数据
└── debug_session_20250612_215439_summary.json  # 会话摘要
```

### 完整会话文件结构

```json
{
  "session_info": {
    "session_id": "debug_session_20250612_215439",
    "start_time": "2025-06-12T21:54:39.123456",
    "end_time": "2025-06-12T21:56:12.789012"
  },
  "api_requests": [
    {
      "timestamp": "2025-06-12T21:54:40.123456",
      "request_id": "search_1734567890123",
      "request_type": "search_with_grounding",
      "model": "gemini-2.0-flash",
      "prompt": "用户查询内容...",
      "config": {
        "temperature": 0.1,
        "max_output_tokens": 8192
      },
      "response": {
        "timestamp": "2025-06-12T21:54:42.456789",
        "text": "API响应内容...",
        "metadata": {
          "has_grounding": true,
          "search_queries": ["查询1", "查询2"]
        },
        "status": "success"
      }
    }
  ],
  "search_results": [
    {
      "timestamp": "2025-06-12T21:54:42.456789",
      "query": "用户查询",
      "search_type": "grounding",
      "success": true,
      "content_length": 1500,
      "citations_count": 3,
      "has_grounding": true,
      "full_result": {
        // 完整的搜索结果数据
      }
    }
  ],
  "workflow_steps": [
    {
      "timestamp": "2025-06-12T21:54:39.123456",
      "step_name": "research_start",
      "step_status": "running",
      "input_data": {
        "user_query": "用户查询",
        "max_search_rounds": 3,
        "effort_level": "medium"
      }
    }
  ],
  "research_results": [
    {
      "timestamp": "2025-06-12T21:56:12.123456",
      "user_query": "用户查询",
      "final_answer_length": 2500,
      "success": true,
      "full_result": {
        // 完整的研究结果
      }
    }
  ],
  "errors": [
    {
      "timestamp": "2025-06-12T21:55:30.123456",
      "error_type": "SearchError",
      "error_message": "错误描述",
      "context": {
        "query": "导致错误的查询",
        "model": "gemini-2.0-flash"
      },
      "stacktrace": "Python错误堆栈..."
    }
  ]
}
```

### 摘要文件结构

```json
{
  "session_id": "debug_session_20250612_215439",
  "total_api_requests": 5,
  "successful_api_requests": 4,
  "total_searches": 3,
  "successful_searches": 3,
  "total_workflow_steps": 8,
  "completed_steps": 7,
  "total_errors": 1,
  "research_results": 1
}
```

## 🔍 分析Debug数据

### 1. 验证API请求

检查API请求是否正确发送：

```python
import json

# 加载debug数据
with open('debug_logs/debug_session_xxx.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 查看API请求
for request in data['api_requests']:
    print(f"请求ID: {request['request_id']}")
    print(f"模型: {request['model']}")
    print(f"状态: {request.get('response', {}).get('status', '无响应')}")
```

### 2. 分析搜索结果

检查搜索是否获取了正确的数据：

```python
# 查看搜索结果
for search in data['search_results']:
    print(f"查询: {search['query']}")
    print(f"成功: {search['success']}")
    print(f"内容长度: {search['content_length']}")
    print(f"引用数量: {search['citations_count']}")
```

### 3. 追踪工作流执行

了解研究过程的每个步骤：

```python
# 查看工作流步骤
for step in data['workflow_steps']:
    print(f"{step['timestamp']}: {step['step_name']} - {step['step_status']}")
```

## ⚠️ 注意事项

1. **数据敏感性**: Debug文件可能包含API密钥信息，请妥善保管
2. **文件大小**: 长时间的研究会产生较大的JSON文件
3. **性能影响**: Debug模式会轻微影响性能，不建议在生产环境中长期开启
4. **存储空间**: 定期清理旧的debug文件以节省存储空间

## 🛠️ 故障排除

### 问题1: Debug文件未生成

**可能原因**:
- Debug模式未正确启用
- 研究过程中出现严重错误

**解决方案**:
1. 确认侧边栏显示"Debug模式已启用"
2. 手动点击"保存Debug日志"按钮
3. 检查 `debug_logs/` 目录权限

### 问题2: JSON文件格式错误

**可能原因**:
- 数据过大导致截断
- 特殊字符编码问题

**解决方案**:
1. 使用支持大文件的JSON查看器
2. 检查文件编码是否为UTF-8

### 问题3: 找不到debug_logs目录

**解决方案**:
1. 目录会在首次启用Debug模式时自动创建
2. 手动创建 `debug_logs/` 目录
3. 检查应用运行目录的写入权限

## 📞 支持

如果遇到Debug功能相关问题：

1. 查看控制台输出中的debug信息
2. 检查JSON文件的格式完整性
3. 尝试重新启用Debug模式
4. 查看应用日志中的错误信息

---

*Happy Debugging! 🐛* 