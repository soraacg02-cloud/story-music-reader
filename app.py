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

# 1. 頁面基本配置（支援手機自適應滿版）
st.set_page_config(
    page_title="雲端沉浸式故事音樂書櫃", page_icon="📚", layout="wide"
)

# 2. Session State 記憶狀態初始化
if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id = None
if "ch_index" not in st.session_state:
    st.session_state.ch_index = 0
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 黑底模式"

# 3. 側邊欄：黑底 / 白底主題切換
st.sidebar.header("🎨 視覺風格設定")
st.session_state.theme_mode = st.sidebar.radio(
    "選擇閱讀配色：",
    ["🌙 黑底模式", "☀️ 白底模式"],
    index=0 if st.session_state.theme_mode == "🌙 黑底模式" else 1,
    key="theme_radio",
)

# 依據選擇動態注入 CSS 樣式與手機按鈕加大優化
if st.session_state.theme_mode == "🌙 黑底模式":
    bg_color, text_color, card_bg, border_color = (
        "#0e1117",
        "#e0e0e0",
        "#1f232a",
        "#30363d",
    )
else:
    bg_color, text_color, card_bg, border_color = (
        "#f9f9fb",
        "#1f232a",
        "#ffffff",
        "#e1e4e8",
    )

st.markdown(
    f"""
<style>
    .stApp {{ background-color: {bg_color} !important; }}
    div[data-testid="stSidebar"] {{ background-color: {card_bg} !important; border-right: 1px solid {border_color}; }}
    div[data-testid="stContainer"] {{ background-color: {card_bg} !important; border: 1px solid {border_color} !important; border-radius: 12px; padding: 12px; }}
    p, h1, h2, h3, h4, span, label {{ color: {text_color} !important; }}
    /* 手機端按鈕加大高度，方便手指舒適點擊 */
    button {{ min-height: 44px !important; border-radius: 8px !important; }}
</style>
""",
    unsafe_allow_html=True,
)


# 4. 初始化 Cloudinary 連線
def init_cloudinary():
    if "cloudinary" not in st.secrets:
        return False
    cfg = st.secrets["cloudinary"]
    cloudinary.config(
        cloud_name=str(cfg.get("cloud_name", "")).strip(),
        api_key=str(cfg.get("api_key", "")).strip(),
        api_secret=str(cfg.get("api_secret", "")).strip(),
        secure=True,
    )
    return True


# 5. Word 文件解析器（完整保留留白與標題）
def parse_docx_bytes(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    for p in doc.paragraphs:
        text = p.text.rstrip()
        style_name = p.style.name.lower()
        is_heading = (
            "heading" in style_name or "標題" in style_name
        ) and text.strip() != ""

        if is_heading:
            if current_chapter["title"]:
                chapters.append(current_chapter)
            current_chapter = {
                "title": text.strip(),
                "music_url": "",
                "content": [],
            }
        elif text.strip().startswith("http://") or text.strip().startswith(
            "https://"
        ):
            current_chapter["music_url"] = text.strip()
        else:
            if not current_chapter["title"]:
                current_chapter["title"] = "前言/序章"
            current_chapter["content"].append(text)

    if current_chapter["title"]:
        chapters.append(current_chapter)

    return chapters


has_cloud = init_cloudinary()

st.title("📚 雲端沉浸式故事音樂書櫃")

# 6. 側邊欄控制與新增檔案功能
if has_cloud:
    st.sidebar.divider()
    if not st.session_state.selected_book_id:
        st.sidebar.header("📤 新增故事入庫")
        new_file = st.sidebar.file_uploader(
            "上傳 Word 故事檔 (.docx)", type=["docx"]
        )
        if new_file:
            if st.sidebar.button(
                "💾 確認存入雲端書櫃", use_container_width=True
            ):
                with st.spinner("正在上傳至雲端..."):
                    try:
                        safe_filename = quote(new_file.name)
                        cloudinary.uploader.upload(
                            new_file,
                            resource_type="raw",
                            public_id=f"story_books/{safe_filename}",
                            overwrite=True,
                        )
                        st.sidebar.success(f"《{new_file.name}》已成功收錄！")
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"上傳失敗：{e}")

# 7. 主區域展示
if has_cloud:
    try:
        resources = cloudinary.api.resources(
            type="upload", prefix="story_books/", resource_type="raw"
        )["resources"]

        if resources:
            # 模式 A：圖書卡片總展覽區
            if not st.session_state.selected_book_id:
                st.header("📖 您的故事書櫃")
                cols = st.columns(3)

                for idx, res in enumerate(resources):
                    col = cols[idx % 3]
                    public_id = res["public_id"]
                    book_title = unquote(public_id.replace("story_books/", ""))
                    created_at_str = res.get("created_at", "")
                    date_display = (
                        datetime.strptime(
                            created_at_str, "%Y-%m-%dT%H:%M:%SZ"
                        ).strftime("%Y-%m-%d %H:%M")
                        if created_at_str
                        else "未知時間"
                    )

                    with col:
                        with st.container(border=True):
                            st.subheader(f"📘 {book_title}")
                            st.caption(f"📅 上傳時間：{date_display}")
                            b1, b2 = st.columns([2, 1])
                            with b1:
                                if st.button(
                                    "📖 點擊閱讀",
                                    key=f"read_{public_id}",
                                    use_container_width=True,
                                ):
                                    st.session_state.selected_book_id = (
                                        public_id
                                    )
                                    st.session_state.ch_index = 0
                                    st.rerun()
                            with b2:
                                if st.button(
                                    "🗑️ 刪除",
                                    key=f"del_{public_id}",
                                    use_container_width=True,
                                ):
                                    cloudinary.uploader.destroy(
                                        public_id, resource_type="raw"
                                    )
                                    st.toast(f"已刪除《{book_title}》")
                                    st.rerun()

            # 模式 B：閱讀器模式（側邊欄懸浮面板 + 內文區）
            else:
                selected_res = next(
                    (
                        r
                        for r in resources
                        if r["public_id"] == st.session_state.selected_book_id
                    ),
                    None,
                )
                if selected_res:
                    book_url = selected_res["secure_url"]
                    book_name = unquote(
                        selected_res["public_id"].replace("story_books/", "")
                    )

                    response = requests.get(book_url)
                    chapters = parse_docx_bytes(response.content)
                    total_chapters = len(chapters)

                    if st.session_state.ch_index >= total_chapters:
                        st.session_state.ch_index = 0

                    chapter_titles = [ch["title"] for ch in chapters]

                    # 側邊欄：懸浮控制面板
                    st.sidebar.header("🎛️ 閱讀控制面板")
                    if st.sidebar.button(
                        "📚 返回圖書總書櫃", use_container_width=True
                    ):
                        st.session_state.selected_book_id = None
                        st.rerun()

                    st.sidebar.divider()
                    st.sidebar.subheader(f"📖 《{book_name}》")

                    selected_ch_title = st.sidebar.selectbox(
                        "📌 快速選章",
                        chapter_titles,
                        index=st.session_state.ch_index,
                        key="sb_side_select",
                    )
                    new_idx = chapter_titles.index(selected_ch_title)
                    if new_idx != st.session_state.ch_index:
                        st.session_state.ch_index = new_idx
                        st.rerun()

                    nav_c1, nav_c2 = st.sidebar.columns(2)
                    with nav_c1:
                        if st.button(
                            "⬅️ 上一章",
                            disabled=(st.session_state.ch_index <= 0),
                            use_container_width=True,
                            key="side_prev",
                        ):
                            st.session_state.ch_index -= 1
                            st.rerun()
                    with nav_c2:
                        if st.button(
                            "下一章 ➡️",
                            disabled=(
                                st.session_state.ch_index >= total_chapters - 1
                            ),
                            use_container_width=True,
                            key="side_next",
                        ):
                            st.session_state.ch_index += 1
                            st.rerun()

                    st.sidebar.divider()
                    current_ch = chapters[st.session_state.ch_index]
                    st.sidebar.subheader("🎵 章節音樂")
                    if current_ch["music_url"]:
                        url = current_ch["music_url"]
                        if "youtube.com" in url or "youtu.be" in url:
                            st.sidebar.video(url)
                        else:
                            st.sidebar.audio(url)
                    else:
                        st.sidebar.caption("本章未設定音樂")

                    # 文章閱讀主區域
                    st.header(f"《{book_name}》")
                    st.subheader(current_ch["title"])
                    st.divider()

                    for line in current_ch["content"]:
                        if line.strip() == "":
                            st.markdown("&nbsp;")
                        else:
                            st.write(line)

                    st.divider()

                    # 底部快速換章按鈕（貼心服務手機端滑至底部的讀者）
                    bot_c1, bot_c2 = st.columns(2)
                    with bot_c1:
                        if st.button(
                            "⬅️ 上一章",
                            disabled=(st.session_state.ch_index <= 0),
                            use_container_width=True,
                            key="bot_prev",
                        ):
                            st.session_state.ch_index -= 1
                            st.rerun()
                    with bot_c2:
                        if st.button(
                            "下一章 ➡️",
                            disabled=(
                                st.session_state.ch_index >= total_chapters - 1
                            ),
                            use_container_width=True,
                            key="bot_next",
                        ):
                            st.session_state.ch_index += 1
                            st.rerun()

        else:
            st.info("📚 雲端書櫃目前是空的，請在上傳區存入故事！")
    except Exception as e:
        st.error(f"連線至雲端書櫃時發生錯誤：{e}")
else:
    st.warning("⚠️ 請先在 Streamlit Cloud 設定 Cloudinary API 金鑰。")
