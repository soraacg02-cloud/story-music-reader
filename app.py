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

# 2. Session State 記憶狀態初始化
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

# 3. 側邊欄：視覺風格切換
st.sidebar.header("🎨 視覺風格設定")
st.session_state.theme_mode = st.sidebar.radio(
    "選擇閱讀配色：",
    ["🌙 黑底模式", "☀️ 白底模式"],
    index=0 if st.session_state.theme_mode == "🌙 黑底模式" else 1,
    key="theme_radio",
)

# 4. 高對比度與手機介面優化 CSS
if st.session_state.theme_mode == "🌙 黑底模式":
    css_style = """
    <style>
        .stApp { background-color: #0e1117 !important; }
        [data-testid="stSidebar"], [data-testid="stSidebarContent"] { background-color: #161920 !important; }
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #f0f2f6 !important; }

        div[data-testid="stPopoverBody"] {
            background-color: #1f232a !important;
            border: 1px solid #30363d !important;
            border-radius: 12px !important;
        }
        div[data-testid="stPopoverBody"] * { color: #ffffff !important; }

        div[data-testid="stContainer"] { 
            background-color: #1f232a !important; 
            border: 1px solid #30363d !important; 
            border-radius: 12px; 
        }

        div.stButton > button, div[data-testid="stPopover"] > button { 
            background-color: #262c36 !important; 
            color: #ffffff !important; 
            border: 1px solid #4f5866 !important; 
            font-weight: bold !important;
            min-height: 48px !important;
            border-radius: 8px !important;
        }
        div.stButton > button:disabled { 
            background-color: #12151a !important; 
            color: #555e6d !important; 
            border: 1px solid #222730 !important; 
        }
        p, h1, h2, h3, h4, span, label { color: #e0e0e0 !important; }
    </style>
    """
else:
    css_style = """
    <style>
        .stApp { background-color: #f9f9fb !important; }
        [data-testid="stSidebar"], [data-testid="stSidebarContent"] { background-color: #ffffff !important; }
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #1f232a !important; }

        div[data-testid="stPopoverBody"] {
            background-color: #ffffff !important;
            border: 1px solid #e1e4e8 !important;
            border-radius: 12px !important;
        }

        div[data-testid="stContainer"] { 
            background-color: #ffffff !important; 
            border: 1px solid #e1e4e8 !important; 
            border-radius: 12px; 
        }
        div.stButton > button, div[data-testid="stPopover"] > button { 
            background-color: #ffffff !important; 
            color: #1f232a !important; 
            border: 1px solid #c0c4cc !important; 
            font-weight: bold !important;
            min-height: 48px !important;
            border-radius: 8px !important;
        }
        div.stButton > button:disabled { 
            background-color: #f0f2f5 !important; 
            color: #a8abb2 !important; 
            border: 1px solid #e4e7ed !important; 
        }
        p, h1, h2, h3, h4, span, label { color: #1f232a !important; }
    </style>
    """

st.markdown(css_style, unsafe_allow_html=True)


# 5. 初始化 Cloudinary 連線
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


# 6. 安全無參數回呼函式 (Parameterless Callbacks)
def prev_chapter_cb():
    if st.session_state.ch_index > 0:
        st.session_state.ch_index -= 1


def next_chapter_cb():
    if st.session_state.ch_index < st.session_state.max_chapters - 1:
        st.session_state.ch_index += 1


def on_radio_change_cb():
    selected = st.session_state.get("sb_popover_radio")
    titles = st.session_state.get("chapter_titles", [])
    if selected in titles:
        st.session_state.ch_index = titles.index(selected)


# 7. Word 文件解析器
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


# 8. 音樂播放器輔助函式（收納於左側邊欄）
def render_music_player(music_url, is_autoplay):
    if music_url:
        if "youtube.com" in music_url or "youtu.be" in music_url:
            st.sidebar.video(music_url, autoplay=is_autoplay)
        else:
            st.sidebar.audio(music_url, autoplay=is_autoplay)
    else:
        st.sidebar.caption("🎵 本章節未設定背景音樂")


has_cloud = init_cloudinary()
st.title("📚 雲端沉浸式故事音樂書櫃")

# 9. 主邏輯區域
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
            if new_file:
                if st.sidebar.button(
                    "💾 確認存入雲端書櫃", use_container_width=True
                ):
                    with st.spinner("正在上傳..."):
                        try:
                            safe_filename = quote(new_file.name)
                            cloudinary.uploader.upload(
                                new_file,
                                resource_type="raw",
                                public_id=f"story_books/{safe_filename}",
                                overwrite=True,
                            )
                            st.sidebar.success(
                                f"《{new_file.name}》已成功收錄！"
                            )
                            st.rerun()
                        except Exception as e:
                            st.sidebar.error(f"上傳失敗：{e}")

            if resources:
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

                # 更新 Session State 中的章節元數據，供 Callback 無參數調用
                st.session_state.max_chapters = len(chapters)
                st.session_state.chapter_titles = [ch["title"] for ch in chapters]

                if st.session_state.ch_index >= st.session_state.max_chapters:
                    st.session_state.ch_index = 0

                current_ch = chapters[st.session_state.ch_index]

                # 側邊欄懸浮控制區
                st.sidebar.divider()
                st.sidebar.header("🎛️ 閱讀控制面板")
                if st.sidebar.button(
                    "📚 返回圖書總書櫃", use_container_width=True
                ):
                    st.session_state.selected_book_id = None
                    st.rerun()

                st.sidebar.subheader(f"📖 《{book_name}》")

                # 【1】音樂播放區：收納於左側邊欄
                st.sidebar.subheader("🎵 懸浮音樂控制箱")
                render_music_player(
                    current_ch["music_url"], st.session_state.auto_play
                )

                st.sidebar.divider()

                # 氣泡章節跳轉選單（手機點擊零鍵盤彈出）
                with st.sidebar.popover(
                    f"📌 章節跳轉：{current_ch['title']}",
                    use_container_width=True,
                ):
                    st.radio(
                        "請選擇要閱讀的章節：",
                        st.session_state.chapter_titles,
                        index=st.session_state.ch_index,
                        key="sb_popover_radio",
                        on_change=on_radio_change_cb,
                    )

                # 上下章控制按鈕（無參數綁定 Callback）
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

                # ---------------- 文章閱讀主區域 ----------------
                st.header(f"《{book_name}》")

                # 【2】主閱讀區最上方：僅保留自動播放開關與手機提醒
                with st.container(border=True):
                    st.session_state.auto_play = st.toggle(
                        "▶️ 切換章節自動播放音樂", value=st.session_state.auto_play
                    )
                    if st.session_state.auto_play:
                        st.caption(
                            "📱 **手機讀者小提示**：受限於手機系統安全機制，換頁後若音樂未自動響起，只需拉開左側選單點擊一次播放按鈕即可！"
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

                # 文章段落還原
                for line in current_ch["content"]:
                    if line.strip() == "":
                        st.markdown("&nbsp;")
                    else:
                        st.write(line)

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
