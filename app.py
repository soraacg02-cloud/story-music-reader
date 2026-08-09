import io
from datetime import datetime
from urllib.parse import quote, unquote
import cloudinary
import cloudinary.api
import cloudinary.uploader
import docx
import requests
import streamlit as st

# 1. 頁面基本設定
st.set_page_config(
    page_title="雲端故事音樂書櫃", page_icon="📚", layout="wide"
)
st.title("📚 雲端沉浸式故事音樂書櫃")


# 2. 初始化 Cloudinary 連線
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


# 3. 初始化 Session State (記憶選中的書籍與目前章節索引)
if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id = None
if "ch_index" not in st.session_state:
    st.session_state.ch_index = 0


def parse_docx_bytes(file_bytes):
    """解析下載好的 Word 檔案內容，並保留段落留白與樣式"""
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


def render_nav_buttons(loc_key, total_chapters):
    """渲染導航控制按鈕的通用函式 (需要獨立的 key 防止元件衝突)"""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        is_first = st.session_state.ch_index <= 0
        if st.button(
            "⬅️ 上一章",
            key=f"prev_{loc_key}",
            disabled=is_first,
            use_container_width=True,
        ):
            st.session_state.ch_index -= 1
            st.rerun()

    with col3:
        is_last = st.session_state.ch_index >= total_chapters - 1
        if st.button(
            "下一章 ➡️",
            key=f"next_{loc_key}",
            disabled=is_last,
            use_container_width=True,
        ):
            st.session_state.ch_index += 1
            st.rerun()


has_cloud = init_cloudinary()

# 4. 側邊欄：新增故事入庫
st.sidebar.header("📤 新增故事入庫")
new_file = st.sidebar.file_uploader("上傳 Word 故事檔 (.docx)", type=["docx"])

if new_file and has_cloud:
    if st.sidebar.button("💾 確認存入雲端書櫃"):
        with st.spinner("正在上傳至雲端書櫃..."):
            try:
                safe_filename = quote(new_file.name)
                cloudinary.uploader.upload(
                    new_file,
                    resource_type="raw",
                    public_id=f"story_books/{safe_filename}",
                    overwrite=True,
                )
                st.sidebar.success(f"《{new_file.name}》已成功收錄進書櫃！")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"上傳失敗：{e}")

# 5. 主區域：圖書卡片展覽區
st.header("📖 您的雲端故事書櫃")

if has_cloud:
    try:
        resources = cloudinary.api.resources(
            type="upload", prefix="story_books/", resource_type="raw"
        )["resources"]

        if resources:
            cols = st.columns(3)

            for idx, res in enumerate(resources):
                col = cols[idx % 3]
                public_id = res["public_id"]
                raw_title = public_id.replace("story_books/", "")
                book_title = unquote(raw_title)

                created_at_str = res.get("created_at", "")
                if created_at_str:
                    dt = datetime.strptime(
                        created_at_str, "%Y-%m-%dT%H:%M:%SZ"
                    )
                    date_display = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    date_display = "未知時間"

                with col:
                    with st.container(border=True):
                        st.subheader(f"📘 {book_title}")
                        st.caption(f"📅 上傳時間：{date_display}")

                        b_col1, b_col2 = st.columns([2, 1])
                        with b_col1:
                            if st.button(
                                "📖 點擊閱讀", key=f"read_{public_id}"
                            ):
                                st.session_state.selected_book_id = public_id
                                st.session_state.ch_index = (
                                    0  # 切換書籍時重置章節為第一章
                                )
                                st.rerun()

                        with b_col2:
                            if st.button("🗑️ 刪除", key=f"del_{public_id}"):
                                cloudinary.uploader.destroy(
                                    public_id, resource_type="raw"
                                )
                                if (
                                    st.session_state.selected_book_id
                                    == public_id
                                ):
                                    st.session_state.selected_book_id = None
                                st.toast(f"已從雲端刪除《{book_title}》")
                                st.rerun()

            st.divider()

            # 6. 當點擊閱讀時，進入故事閱讀模式
            if st.session_state.selected_book_id:
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

                    st.subheader(f"📖 當前正在閱讀：《{book_name}》")
                    response = requests.get(book_url)
                    chapters = parse_docx_bytes(response.content)
                    total_chapters = len(chapters)

                    # 確保章節索引沒有越界
                    if st.session_state.ch_index >= total_chapters:
                        st.session_state.ch_index = 0

                    chapter_titles = [ch["title"] for ch in chapters]

                    # 下拉選單：同步當前章節索引
                    selected_ch_title = st.selectbox(
                        "📌 快速跳轉章節",
                        chapter_titles,
                        index=st.session_state.ch_index,
                        key="sb_chapter_select",
                    )

                    # 如果使用者自行由下拉選單切換章節，更新 session_state
                    new_selected_idx = chapter_titles.index(selected_ch_title)
                    if new_selected_idx != st.session_state.ch_index:
                        st.session_state.ch_index = new_selected_idx
                        st.rerun()

                    # 頂部導航按鈕 (Top Navigation)
                    render_nav_buttons("top", total_chapters)

                    current_ch = chapters[st.session_state.ch_index]

                    st.divider()
                    st.header(current_ch["title"])

                    # 背景音樂播放器
                    if current_ch["music_url"]:
                        url = current_ch["music_url"]
                        if "youtube.com" in url or "youtu.be" in url:
                            st.video(url)
                        else:
                            st.audio(url)
                        st.success("🎵 背景音樂載入成功！")

                    st.divider()

                    # 還原排版與段落留白
                    for line in current_ch["content"]:
                        if line.strip() == "":
                            st.markdown("&nbsp;")
                        else:
                            st.write(line)

                    st.divider()

                    # 底部導航按鈕 (Bottom Navigation)
                    render_nav_buttons("bottom", total_chapters)

        else:
            st.info("📚 雲端書櫃目前是空的，請在左側上傳您的第一本故事書！")
    except Exception as e:
        st.error(f"連線至雲端書櫃時發生錯誤：{e}")
else:
    st.warning("⚠️ 請先在 Streamlit Cloud 設定 Cloudinary API 金鑰。")
