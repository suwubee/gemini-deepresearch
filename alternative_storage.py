"""
使用streamlit-javascript的替代LocalStorage方案
如果streamlit-local-storage不工作，可以使用这个方案
"""

import streamlit as st
import json

# 需要安装: pip install streamlit-javascript
try:
    from streamlit_javascript import st_javascript
    JAVASCRIPT_AVAILABLE = True
except ImportError:
    JAVASCRIPT_AVAILABLE = False
    st.error("请安装 streamlit-javascript: pip install streamlit-javascript")

def safe_local_storage_get(key):
    """安全地从LocalStorage获取数据"""
    if not JAVASCRIPT_AVAILABLE:
        return None
    
    try:
        # 使用JavaScript直接访问localStorage
        js_code = f"""
        try {{
            const value = localStorage.getItem('{key}');
            return value;
        }} catch (e) {{
            console.error('LocalStorage get error:', e);
            return null;
        }}
        """
        result = st_javascript(js_code)
        return result
    except Exception as e:
        st.warning(f"LocalStorage读取失败: {e}")
        return None

def safe_local_storage_set(key, value):
    """安全地向LocalStorage保存数据"""
    if not JAVASCRIPT_AVAILABLE:
        return False
    
    try:
        # 确保value是字符串
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        
        # 转义引号
        escaped_value = value.replace("'", "\\'").replace('"', '\\"')
        
        js_code = f"""
        try {{
            localStorage.setItem('{key}', '{escaped_value}');
            return 'success';
        }} catch (e) {{
            console.error('LocalStorage set error:', e);
            return 'error';
        }}
        """
        result = st_javascript(js_code)
        return result == 'success'
    except Exception as e:
        st.warning(f"LocalStorage保存失败: {e}")
        return False

def safe_local_storage_remove(key):
    """安全地从LocalStorage删除数据"""
    if not JAVASCRIPT_AVAILABLE:
        return False
    
    try:
        js_code = f"""
        try {{
            localStorage.removeItem('{key}');
            return 'success';
        }} catch (e) {{
            console.error('LocalStorage remove error:', e);
            return 'error';
        }}
        """
        result = st_javascript(js_code)
        return result == 'success'
    except Exception as e:
        st.warning(f"LocalStorage删除失败: {e}")
        return False

# 测试函数
if __name__ == "__main__":
    st.title("替代LocalStorage方案测试")
    
    if JAVASCRIPT_AVAILABLE:
        st.success("✅ streamlit-javascript 可用")
        
        # 测试保存
        if st.button("测试保存"):
            test_data = {"test": "data", "timestamp": "2025-01-01"}
            success = safe_local_storage_set("test_key", test_data)
            if success:
                st.success("✅ 保存成功")
            else:
                st.error("❌ 保存失败")
        
        # 测试读取
        if st.button("测试读取"):
            result = safe_local_storage_get("test_key")
            st.info(f"读取结果: {result}")
            
            if result:
                try:
                    parsed = json.loads(result)
                    st.json(parsed)
                except:
                    st.text(result)
        
        # 测试删除
        if st.button("测试删除"):
            success = safe_local_storage_remove("test_key")
            if success:
                st.success("✅ 删除成功")
            else:
                st.error("❌ 删除失败")
    else:
        st.error("❌ streamlit-javascript 不可用")
        st.code("pip install streamlit-javascript") 