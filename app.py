"""
DeepSearch - 智能深度研究助手
基于 Streamlit 的主应用程序，支持双模式API和模块化设计
"""

import streamlit as st
import asyncio
import json
import os
import time
import threading
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, List
from enum import Enum
import queue

# --- 导入核心组件 ---
from core.research_engine import ResearchEngine
from core.state_manager import TaskStatus
from core.api_config import APIConfig, APIMode
from core.model_config import get_model_config, set_user_model
from utils.debug_logger import enable_debug, disable_debug, get_debug_logger
from utils.streamlit_helpers import (
    json_serializable,
    create_markdown_content,
    display_task_analysis,
    display_search_results,
    display_final_answer,
)

# --- 页面和样式配置 ---
st.set_page_config(
    page_title="🔍 DeepResearch",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 全局常量 ---
AVAILABLE_MODELS = {
    "gemini-2.0-flash": "🚀 Gemini 2.0 Flash - 便宜最快",
    "gemini-2.5-flash": "⚡ Gemini 2.5 Flash",
    "gemini-2.5-pro": "💫 Gemini 2.5 Pro"
}
TASK_MODEL_MAPPING = {
    "search": "搜索模型", "task_analysis": "任务分析模型", 
    "reflection": "反思分析模型", "answer": "答案生成模型"
}
API_MODE_OPTIONS = {
    APIMode.GENAI: "🔵 Google GenAI SDK",
    APIMode.OPENAI: "🟠 OpenAI兼容 HTTP API"
}

# --- 会话状态管理 ---
def initialize_session_state():
    """初始化会话状态"""
    defaults = {
        "research_engine": None,
        "is_researching": False,
        "research_complete": False,
        "research_error": None,
        "research_results": [],
        "progress_messages": [],
        "current_step": "",
        "progress_percentage": 0,
        "api_mode": APIMode.GENAI,
        "model_name": "gemini-2.0-flash",
        "gemini_api_key": "",
        "openai_config": {'base_url': 'https://api.openai.com/v1', 'api_key': '', 'timeout': 30},
        "task_models": {'search': 'gemini-2.0-flash', 'task_analysis': 'gemini-2.5-flash', 'reflection': 'gemini-2.5-flash', 'answer': 'gemini-2.5-pro'},
        "custom_models": [],
        "config_changed": True,
        "debug_enabled": False,
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# --- 核心逻辑 ---
def validate_and_setup_engine():
    """验证API密钥并设置引擎"""
    active_api_key = ""
    if st.session_state.api_mode == APIMode.GENAI:
        active_api_key = st.session_state.gemini_api_key
    elif st.session_state.api_mode == APIMode.OPENAI:
        active_api_key = st.session_state.openai_config.get("api_key", "")

    if not active_api_key or len(active_api_key) < 10:
        st.session_state.research_engine = None
        return
    
    try:
        if st.session_state.config_changed or st.session_state.research_engine is None:
            if st.session_state.api_mode == APIMode.GENAI:
                engine = ResearchEngine(api_key=active_api_key, model_name=st.session_state.model_name, api_mode=APIMode.GENAI)
            else:
                engine = ResearchEngine(
                    api_key="dummy", model_name=st.session_state.model_name, api_mode=APIMode.OPENAI,
                    openai_api_key=st.session_state.openai_config.get("api_key"),
                    base_url=st.session_state.openai_config.get("base_url"),
                    timeout=st.session_state.openai_config.get("timeout")
                )
            st.session_state.research_engine = engine
            st.session_state.config_changed = False
            
    except Exception as e:
        st.sidebar.error(f"引擎初始化失败: {e}")
        st.session_state.research_engine = None

# --- UI渲染 ---
def setup_api_key():
    st.sidebar.header("🔑 API密钥")
    
    # Gemini
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password", value=st.session_state.gemini_api_key)
    if gemini_key != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = gemini_key
        st.session_state.config_changed = True

    # OpenAI
    if st.session_state.api_mode == APIMode.OPENAI:
        openai_key = st.sidebar.text_input("OpenAI API Key", type="password", value=st.session_state.openai_config['api_key'])
        if openai_key != st.session_state.openai_config['api_key']:
            st.session_state.openai_config['api_key'] = openai_key
            st.session_state.config_changed = True

def setup_api_configuration():
    st.sidebar.subheader("🔧 API配置")
    
    mode = st.sidebar.selectbox("API模式", options=list(API_MODE_OPTIONS.keys()), format_func=lambda x: API_MODE_OPTIONS[x])
    if mode != st.session_state.api_mode:
        st.session_state.api_mode = mode
        st.session_state.config_changed = True
    
    if st.session_state.api_mode == APIMode.OPENAI:
        base_url = st.sidebar.text_input("Base URL", value=st.session_state.openai_config['base_url'])
        if base_url != st.session_state.openai_config['base_url']:
            st.session_state.openai_config['base_url'] = base_url
            st.session_state.config_changed = True

def setup_model_configuration():
    st.sidebar.subheader("🎯 模型配置")
    model = st.sidebar.selectbox("主要模型", options=list(AVAILABLE_MODELS.keys()), format_func=lambda x: AVAILABLE_MODELS.get(x,x))
    if model != st.session_state.model_name:
        st.session_state.model_name = model
        st.session_state.config_changed = True

def sidebar_content():
    st.sidebar.title("🚀 DeepResearch")
    st.sidebar.markdown("---")
    setup_api_key()
    
    with st.sidebar.expander("⚙️ 高级配置", expanded=True):
        setup_api_configuration()
        setup_model_configuration()
    
    # 触发引擎更新
    validate_and_setup_engine()

def research_interface():
    st.title("🔍 DeepSearch - 智能深度研究助手")
    if not st.session_state.research_engine:
        st.warning("请在侧边栏配置有效的API密钥以开始使用。")
    # ... (其他UI代码) ...

def main():
    initialize_session_state()
    sidebar_content()
    research_interface()

if __name__ == "__main__":
    main() 