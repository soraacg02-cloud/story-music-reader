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
st.set_page_config(
    page_title="雲端沉浸式故事音樂書櫃", page_icon="📚", layout="wide"
)

# 2. Session State 記憶狀態初始化 (全域共享黑板)
if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id = None
if "ch_index" not in st.session_state:
    st.session_state.ch_index = 0
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 黑底模式"
if "auto_play" not in st.session_state:
    st.session_state.auto_play = True
if "max_chapters" not in st.session_state:
    st.session_state.max_chapters = 1
if "chapter_titles" not in st.session_state:
    st.session_state.chapter_titles = []
if "reading_pct" not in st.session_state:
    st.session_state.reading_pct = 0

# ---------------- 【左側欄順序 1】：視覺風格 ----------------
st.sidebar.header("🎨 視覺風格")
st.session_state.theme_mode = st.sidebar.radio(
    "選擇閱讀配色：",
    ["🌙 黑底模式", "☀️ 白底模式"],
    index=0 if st.session_state.theme_mode == "🌙 黑底模式" else 1,
    key="theme_radio",
)

# 3. 高對比度與主題顏色 CSS 設定 (包含手機版與黑底模式下側邊欄選單文字強化)
if st.session_state.theme_mode == "🌙 黑底模式":
    bg_col, sidebar_bg, card_bg, border_col, text_col, button_bg = (
        "#0e1117",
        "#161920",
        "#1f232a",
        "#30363d",
        "#e0e0e0",
        "#262c36",
    )
else:
    bg_col, sidebar_bg, card_bg, border_col, text_col, button_bg = (
        "#f9f9fb",
        "#ffffff",
        "#ffffff",
        "#e1e4e8",
        "#1f232a",
        "#ffffff",
    )

css_style = f"""
<style>
    .stApp {{ background-color: {bg_col} !important; }}
    [data-testid="stSidebar"], [data-testid="stSidebarContent"] {{ background-color: {sidebar_bg} !important; }}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {{ color: #f0f2f6 !important; }}

    div[data-testid="stPopoverBody"] {{
        background-color: {card_bg} !important;
        border: 1px solid {border_col} !important;
        border-radius: 12px !important;
    }}
    div[data-testid="stPopoverBody"] *, div[data-testid="stPopoverBody"] label {{ 
        color: {text_col} !important; 
    }}

    div[data-testid="stContainer"] {{ 
        background-color: {card_bg} !important; 
        border: 1px solid {border_col} !important; 
        border-radius: 12px; 
    }}

    div.stButton > button, div[data-testid="stPopover"] > button {{ 
        background-color: {button_bg} !important; 
        color: {text_col} !important; 
        border: 1px solid {border_col} !important; 
        font-weight: bold !important;
        min-height: 48px !important;
        border-radius: 8px !important;
    }}

    p, h1, h2, h3, h4, span, label {{ color: {text_col} !important; }}
</style>
"""
st.markdown(css_style, unsafe_allow_html=True)


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


# 檔案大小可讀化轉換函式
def format_file_size(size_in_bytes):
    if not size_in_bytes or size_in_bytes <= 0:
        return "大小未知"
    if size_in_bytes < 1024:
        return f"{size_in_bytes} Bytes"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"


# 5. 安全狀態同步回呼函式 (換章時強制將百分比歸零並回到頂端)
def prev_chapter_cb():
    if st.session_state.ch_index > 0:
        st.session_state.ch_index -= 1
        st.session_state.reading_pct = 0


def next_chapter_cb():
    if st.session_state.ch_index < st.session_state.max_chapters - 1:
        st.session_state.ch_index += 1
        st.session_state.reading_pct = 0


def on_radio_change_cb():
    selected = st.session_state.get("sb_popover_radio")
    titles = st.session_state.get("chapter_titles", [])
    if selected in titles:
        st.session_state.ch_index = titles.index(selected)
        st.session_state.reading_pct = 0


def on_slider_change_cb():
    st.session_state.reading_pct = st.session_state.get("sb_slider_pct", 0)


# 6. Word 文件解析器
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


# 7. 音樂播放器輔助函式（收納於左側邊欄）
def render_music_player(music_url, is_autoplay):
    if music_url:
        if "youtube.com" in music_url or "youtu.be" in music_url:
            st.sidebar.video(music_url, autoplay=is_autoplay)
        else:
            st.sidebar.audio(music_url, autoplay=is_autoplay)
    else:
        st.sidebar.caption("🎵 本章節未設定背景音樂")


has_cloud = init_cloudinary()

# 清除舊的 DOM 殘影
st.components.v1.html(
    """
<script>
    const pDoc = window.parent.document;
    const old1 = pDoc.getElementById("parent-sticky-bar");
    if (old1) old1.remove();
    const old2 = pDoc.getElementById("sticky-progress-container");
    if (old2) old2.remove();
</script>
""",
    height=0,
)

st.title("📚 雲端沉浸式故事音樂書櫃")

# 8. 主邏輯區域
if has_cloud:
    try:
        resources = cloudinary.api.resources(
            type="upload", prefix="story_books/", resource_type="raw"
        )["resources"]

        # ---------------- 模式 A：總書櫃頁面 ----------------
        if not st.session_state.selected_book_id:
            st.sidebar.divider()
            st.sidebar.header("📤 新增故事入庫")
            new_file = st.sidebar.file_uploader(
                "上傳 Word 故事檔 (.docx)", type=["docx"]
            )
            cover_file = st.sidebar.file_uploader(
                "上傳書籍封面圖片 (選填)", type=["png", "jpg", "jpeg"]
            )

            if new_file:
                if st.sidebar.button(
                    "💾 確認存入雲端書櫃", use_container_width=True
                ):
                    with st.spinner("正在上傳故事與封面..."):
                        try:
                            safe_filename = quote(new_file.name)
                            # 1. 上傳 Word 故事檔
                            cloudinary.uploader.upload(
                                new_file,
                                resource_type="raw",
                                public_id=f"story_books/{safe_filename}",
                                overwrite=True,
                            )
                            # 2. 如果有上傳封面，則同步上傳至圖片專用資料夾
                            if cover_file:
                                cloudinary.uploader.upload(
                                    cover_file,
                                    resource_type="image",
                                    public_id=f"story_covers/{safe_filename}",
                                    overwrite=True,
                                )
                            st.sidebar.success(
                                f"《{new_file.name}》與封面已成功收錄！"
                            )
                            st.rerun()
                        except Exception as e:
                            st.sidebar.error(f"上傳失敗：{e}")

            if resources:
                st.header("📖 您的故事書櫃")
                cols = st.columns(3)
                cloud_name_str = st.secrets["cloudinary"].get("cloud_name", "")

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

                    file_bytes_size = res.get("bytes", 0)
                    size_display = format_file_size(file_bytes_size)
                    cover_url = f"https://res.cloudinary.com/{cloud_name_str}/image/upload/story_covers/{quote(book_title)}"

                    with col:
                        with st.container(border=True):
                            try:
                                st.image(cover_url, use_container_width=True)
                            except Exception:
                                st.caption("📷 尚無封面圖片")

                            st.subheader(f"📘 {book_title}")
                            st.caption(
                                f"📅 上傳：{date_display} ｜ 📦 大小：{size_display}"
                            )
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
                                    st.session_state.reading_pct = 0
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
                                    try:
                                        cloudinary.uploader.destroy(
                                            f"story_covers/{quote(book_title)}",
                                            resource_type="image",
                                        )
                                    except Exception:
                                        pass
                                    st.toast(f"已刪除《{book_title}》")
                                    st.rerun()

        # ---------------- 模式 B：故事閱讀器頁面 ----------------
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

                st.session_state.max_chapters = len(chapters)
                st.session_state.chapter_titles = [ch["title"] for ch in chapters]

                if st.session_state.ch_index >= st.session_state.max_chapters:
                    st.session_state.ch_index = 0

                current_ch = chapters[st.session_state.ch_index]
                content_lines = current_ch["content"]
                total_lines = len(content_lines)

                # ---------------- 側邊欄區域 ----------------
                st.sidebar.divider()

                # 【順序 2】：音樂盒
                st.sidebar.header("🎵 音樂盒")
                render_music_player(
                    current_ch["music_url"], st.session_state.auto_play
                )

                st.sidebar.divider()

                # 【順序 3】：章節切換與精簡版快轉進度
                st.sidebar.header("📌 章節切換與進度")
                
                pct_value = st.sidebar.slider(
                    "🎯 快轉跳轉：",
                    min_value=0,
                    max_value=100,
                    value=st.session_state.reading_pct,
                    step=5,
                    format="%d%%",
                    key="sb_slider_pct",
                    on_change=on_slider_change_cb,
                )

                target_line_idx = int(total_lines * (pct_value / 100.0))
                if target_line_idx >= total_lines:
                    target_line_idx = max(0, total_lines - 1)

                with st.sidebar.popover(
                    f"跳轉章節：{current_ch['title']}",
                    use_container_width=True,
                ):
                    st.radio(
                        "請選擇要閱讀的章節：",
                        st.session_state.chapter_titles,
                        index=st.session_state.ch_index,
                        key="sb_popover_radio",
                        on_change=on_radio_change_cb,
                    )

                nav_c1, nav_c2 = st.sidebar.columns(2)
                with nav_c1:
                    st.button(
                        "⬅️ 上一章",
                        disabled=(st.session_state.ch_index <= 0),
                        use_container_width=True,
                        key="side_prev",
                        on_click=prev_chapter_cb,
                    )
                with nav_c2:
                    st.button(
                        "下一章 ➡️",
                        disabled=(
                            st.session_state.ch_index >= st.session_state.max_chapters - 1
                        ),
                        use_container_width=True,
                        key="side_next",
                        on_click=next_chapter_cb,
                    )

                st.sidebar.divider()

                # 【順序 4】：控制面板
                st.sidebar.header("🎛️ 控制面板")
                if st.sidebar.button(
                    "📚 返回圖書總書櫃", use_container_width=True
                ):
                    st.session_state.selected_book_id = None
                    st.session_state.reading_pct = 0
                    st.rerun()

                # ---------------- 文章閱讀主區域 ----------------
                # 當百分比歸零時，自動透過 JavaScript 平滑捲動回頁面最頂端
                if pct_value == 0:
                    st.components.v1.html(
                        """
                    <script>
                        window.parent.scrollTo({top: 0, behavior: 'smooth'});
                    </script>
                    """,
                        height=0,
                    )

                st.header(f"《{book_name}》")

                # 自動播放開關
                with st.container(border=True):
                    st.session_state.auto_play = st.toggle(
                        "▶️ 切換章節自動播放音樂", value=st.session_state.auto_play
                    )

                st.subheader(current_ch["title"])
                st.divider()

                # 頂部導航按鈕
                top_c1, top_c2 = st.columns(2)
                with top_c1:
                    st.button(
                        "⬅️ 上一章",
                        disabled=(st.session_state.ch_index <= 0),
                        use_container_width=True,
                        key="top_prev",
                        on_click=prev_chapter_cb,
                    )
                with top_c2:
                    st.button(
                        "下一章 ➡️",
                        disabled=(
                            st.session_state.ch_index >= st.session_state.max_chapters - 1
                        ),
                        use_container_width=True,
                        key="top_next",
                        on_click=next_chapter_cb,
                    )

                st.divider()

                # 完整保留所有段落，並透過 HTML Anchor 錨點平滑捲動到對應百分比位置
                for idx, line in enumerate(content_lines):
                    anchor_html = f'<div id="line-anchor-{idx}"></div>'
                    st.markdown(anchor_html, unsafe_allow_html=True)
                    if line.strip() == "":
                        st.markdown("&nbsp;")
                    else:
                        st.write(line)

                scroll_script = f"""
                <script>
                    setTimeout(function() {{
                        const pDoc = window.parent.document;
                        const targetAnchor = pDoc.getElementById("line-anchor-{target_line_idx}");
                        if (targetAnchor) {{
                            targetAnchor.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        }}
                    }}, 200);
                </script>
                """
                st.components.v1.html(scroll_script, height=0)

                st.divider()

                # 底部導航按鈕
                bot_c1, bot_c2 = st.columns(2)
                with bot_c1:
                    st.button(
                        "⬅️ 上一章",
                        disabled=(st.session_state.ch_index <= 0),
                        use_container_width=True,
                        key="bot_prev",
                        on_click=prev_chapter_cb,
                    )
                with bot_c2:
                    st.button(
                        "下一章 ➡️",
                        disabled=(
                            st.session_state.ch_index >= st.session_state.max_chapters - 1
                        ),
                        use_container_width=True,
                        key="bot_next",
                        on_click=next_chapter_cb,
                    )

    except Exception as e:
        st.error(f"連線至雲端書櫃時發生錯誤：{e}")
else:
    st.warning("⚠️ 請先在 Streamlit Cloud 設定 Cloudinary API 金鑰。")
