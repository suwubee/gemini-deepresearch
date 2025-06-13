"""
测试 SearchAgent 类的功能
用于验证和优化 search_agent.py 中的搜索功能
"""

import os
import asyncio
from google.genai import Client
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

async def test_search_response():
    """测试 Gemini API 的原始搜索响应格式"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("请设置 GOOGLE_API_KEY 环境变量")

    client = Client(api_key=api_key)
    model_id = "gemini-2.0-flash"

    # 测试查询
    query = "2024年温网男单冠军是谁？"
    print(f"\n测试查询: {query}")
    print("-" * 50)

    # 配置搜索工具
    google_search_tool = Tool(
        google_search=GoogleSearch()
    )

    # 发送请求
    response = client.models.generate_content(
        model=model_id,
        contents=query,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            response_modalities=["TEXT"],
        )
    )

    # 分析响应结构
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        
        # 1. 检查文本内容
        print("\n1. 文本内容:")
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                print(part.text)
        
        # 2. 检查 grounding metadata
        if hasattr(candidate, 'grounding_metadata'):
            metadata = candidate.grounding_metadata
            print("\n2. Grounding Metadata 结构:")
            
            # 2.1 搜索查询
            if hasattr(metadata, 'web_search_queries'):
                print("\n2.1 搜索查询:")
                print(metadata.web_search_queries)
            
            # 2.2 Grounding Chunks
            if hasattr(metadata, 'grounding_chunks'):
                print("\n2.2 Grounding Chunks:")
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web'):
                        print(f"标题: {chunk.web.title}")
                        print(f"URI: {chunk.web.uri}")
                        print("---")
            
            # 2.3 Grounding Supports
            if hasattr(metadata, 'grounding_supports'):
                print("\n2.3 Grounding Supports:")
                for support in metadata.grounding_supports:
                    print(f"文本片段: {support.segment.text}")
                    print(f"置信度: {support.confidence_scores}")
                    print(f"Chunk索引: {support.grounding_chunk_indices}")
                    print("---")

if __name__ == "__main__":
    asyncio.run(test_search_response()) 