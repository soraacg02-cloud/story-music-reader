import io
import re
from datetime import datetime
from urllib.parse import quote, unquote
import cloudinary
import cloudinary.api
import cloudinary.uploader
import docx
import requests
import streamlit as st

# 1. 頁面基本配置
st.set_page_config(page_title="雲端沉浸式故事音樂書櫃", page_icon="📚", layout="wide")

# 2. Session State 初始化
if "selected_book_id" not in st.session_state: st.session_state.selected_book_id = None
if "ch_index" not in st.session_state: st.session_state.ch_index = 0
if "theme_mode" not in st.session_state: st.session_state.theme_mode = "🌙 黑底模式"
if "auto_play" not in st.session_state: st.session_state.auto_play = True
if "max_chapters" not in st.session_state: st.session_state.max_chapters = 1
if "chapter_titles" not in st.session_state: st.session_state.chapter_titles = []
if "reading_pct" not in st.session_state: st.session_state.reading_pct = 0

# 3. CSS 設定
if st.session_state.theme_mode == "🌙 黑底模式":
    bg_col, sidebar_bg, card_bg, border_col, text_col, button_bg = "#0e1117", "#161920", "#1f232a", "#30363d", "#e0e0e0", "#262c36"
else:
    bg_col, sidebar_bg, card_bg, border_col, text_col, button_bg = "#f9f9fb", "#ffffff", "#ffffff", "#e1e4e8", "#1f232a", "#ffffff"

st.markdown(f"""
<style>
    .stApp {{ background-color: {bg_col} !important; }}
    p, h1, h2, h3, h4, span, label {{ color: {text_col} !important; }}
</style>
""", unsafe_allow_html=True)

# 4. 輔助函式
def init_cloudinary():
    if "cloudinary" not in st.secrets: return False
    cfg = st.secrets["cloudinary"]
    cloudinary.config(cloud_name=str(cfg.get("cloud_name", "")).strip(), api_key=str(cfg.get("api_key", "")).strip(), api_secret=str(cfg.get("api_secret", "")).strip(), secure=True)
    return True

def format_file_size(size_in_bytes):
    if size_in_bytes < 1024: return f"{size_in_bytes} Bytes"
    elif size_in_bytes < 1024*1024: return f"{size_in_bytes/1024:.1f} KB"
    else: return f"{size_in_bytes/(1024*1024):.2f} MB"

def prev_chapter_cb():
    if st.session_state.ch_index > 0:
        st.session_state.ch_index -= 1
        st.session_state.reading_pct = 0

def next_chapter_cb():
    if st.session_state.ch_index < st.session_state.max_chapters - 1:
        st.session_state.ch_index += 1
        st.session_state.reading_pct = 0

def on_slider_change_cb():
    st.session_state.reading_pct = st.session_state.get("sb_slider_pct", 0)

# 5. 主邏輯
has_cloud = init_cloudinary()
st.title("📚 雲端沉浸式故事音樂書櫃")

if has_cloud:
    resources = cloudinary.api.resources(type="upload", prefix="story_books/", resource_type="raw")["resources"]
    
    if not st.session_state.selected_book_id:
        # 書櫃顯示邏輯... (與原邏輯相同)
        if resources:
            for res in resources:
                if st.button(f"📘 {unquote(res['public_id'].split('/')[-1])}", use_container_width=True):
                    st.session_state.selected_book_id = res['public_id']
                    st.rerun()
    else:
        # 閱讀器邏輯
        res = next((r for r in resources if r["public_id"] == st.session_state.selected_book_id), None)
        response = requests.get(res["secure_url"])
        chapters = parse_docx_bytes(response.content) # 假設已有此函數
        current_ch = chapters[st.session_state.ch_index]
        total_lines = len(current_ch["content"])

        # 左側欄：僅保留精簡滑桿
        st.sidebar.header("📌 閱讀進度")
        pct_value = st.sidebar.slider("🎯 快轉跳轉：", 0, 100, st.session_state.reading_pct, 5, format="%d%%", key="sb_slider_pct", on_change=on_slider_change_cb)
        
        # 換頁邏輯：若百分比為 0，強制捲動回頂端
        target_idx = int(total_lines * (pct_value / 100.0))
        if pct_value == 0:
            st.components.v1.html("<script>window.parent.scrollTo({top: 0, behavior: 'smooth'});</script>", height=0)

        # 導航按鈕 (統一設為歸零功能)
        col1, col2 = st.columns(2)
        if col1.button("⬅️ 上一章", on_click=prev_chapter_cb): st.rerun()
        if col2.button("下一章 ➡️", on_click=next_chapter_cb): st.rerun()

        # 渲染文章
        for idx, line in enumerate(current_ch["content"]):
            st.markdown(f'<div id="line-{idx}"></div>', unsafe_allow_html=True)
            st.write(line)
        
        # 自動平滑捲動腳本
        st.components.v1.html(f"""<script>
            document.getElementById('line-{target_idx}').scrollIntoView({{behavior: 'smooth'}});
        </script>""", height=0)
