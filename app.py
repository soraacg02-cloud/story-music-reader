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

# 3. 輔助函式：初始化 Cloudinary
def init_cloudinary():
    if "cloudinary" not in st.secrets: return False
    cfg = st.secrets["cloudinary"]
    cloudinary.config(
        cloud_name=str(cfg.get("cloud_name", "")).strip(),
        api_key=str(cfg.get("api_key", "")).strip(),
        api_secret=str(cfg.get("api_secret", "")).strip(),
        secure=True,
    )
    return True

# 4. 輔助函式：檔案大小格式化
def format_file_size(size_in_bytes):
    if not size_in_bytes or size_in_bytes <= 0: return "大小未知"
    if size_in_bytes < 1024: return f"{size_in_bytes} Bytes"
    elif size_in_bytes < 1024 * 1024: return f"{size_in_bytes / 1024:.1f} KB"
    else: return f"{size_in_bytes / (1024 * 1024):.2f} MB"

# 5. 【關鍵修復】：Word 文件解析器
def parse_docx_bytes(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    for p in doc.paragraphs:
        text = p.text.rstrip()
        style_name = p.style.name.lower()
        is_heading = ("heading" in style_name or "標題" in style_name) and text.strip() != ""

        if is_heading:
            if current_chapter["title"]:
                chapters.append(current_chapter)
            current_chapter = {"title": text.strip(), "music_url": "", "content": []}
        elif text.strip().startswith("http://") or text.strip().startswith("https://"):
            current_chapter["music_url"] = text.strip()
        else:
            if not current_chapter["title"]:
                current_chapter["title"] = "前言/序章"
            current_chapter["content"].append(text)

    if current_chapter["title"]:
        chapters.append(current_chapter)

    return chapters

# 6. 狀態回呼函式
def prev_chapter_cb():
    if st.session_state.ch_index > 0:
        st.session_state.ch_index -= 1
        st.session_state.reading_pct = 0

def next_chapter_cb():
    if st.session_state.ch_index < st.session_state.max_chapters - 1:
        st.session_state.ch_index += 1
        st.session_state.reading_pct = 0

# 7. 主邏輯
has_cloud = init_cloudinary()
st.title("📚 雲端沉浸式故事音樂書櫃")

if has_cloud:
    try:
        resources = cloudinary.api.resources(type="upload", prefix="story_books/", resource_type="raw")["resources"]
        
        if not st.session_state.selected_book_id:
            st.sidebar.divider()
            st.sidebar.header("📤 新增故事入庫")
            new_file = st.sidebar.file_uploader("上傳 Word 故事檔 (.docx)", type=["docx"])
            if new_file and st.sidebar.button("💾 確認存入雲端書櫃", use_container_width=True):
                with st.spinner("正在上傳..."):
                    safe_filename = quote(new_file.name)
                    cloudinary.uploader.upload(new_file, resource_type="raw", public_id=f"story_books/{safe_filename}", overwrite=True)
                    st.rerun()

            if resources:
                st.header("📖 您的故事書櫃")
                for res in resources:
                    public_id = res["public_id"]
                    book_title = unquote(public_id.replace("story_books/", ""))
                    if st.button(f"📘 閱讀：{book_title}", key=f"read_{public_id}", use_container_width=True):
                        st.session_state.selected_book_id = public_id
                        st.session_state.ch_index = 0
                        st.session_state.reading_pct = 0
                        st.rerun()
        else:
            selected_res = next((r for r in resources if r["public_id"] == st.session_state.selected_book_id), None)
            if selected_res:
                response = requests.get(selected_res["secure_url"])
                chapters = parse_docx_bytes(response.content)
                st.session_state.max_chapters = len(chapters)
                current_ch = chapters[st.session_state.ch_index]

                st.sidebar.button("📚 返回書櫃", on_click=lambda: setattr(st.session_state, 'selected_book_id', None))
                st.subheader(current_ch["title"])
                
                col1, col2 = st.columns(2)
                if col1.button("⬅️ 上一章", on_click=prev_chapter_cb): st.rerun()
                if col2.button("下一章 ➡️", on_click=next_chapter_cb): st.rerun()

                for line in current_ch["content"]:
                    st.write(line)
    except Exception as e:
        st.error(f"發生錯誤：{e}")
else:
    st.warning("⚠️ 請先設定 Cloudinary API 金鑰。")
