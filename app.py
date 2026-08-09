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


# 3. 初始化 Session State 記憶狀態
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


has_cloud = init_cloudinary()

# 4. 側邊欄：依據「選書狀態」呈現上傳介面或閱讀懸浮控制區
if has_cloud:
    if not st.session_state.selected_book_id:
        # 未選書時：顯示新增故事上傳區
        st.sidebar.header("📤 新增故事入庫")
        new_file = st.sidebar.file_uploader(
            "上傳 Word 故事檔 (.docx)", type=["docx"]
        )

        if new_file:
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
                        st.sidebar.success(
                            f"《{new_file.name}》已成功收錄進書櫃！"
                        )
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"上傳失敗：{e}")

# 5. 主區域：圖書卡片展覽區與閱讀器渲染
if has_cloud:
    try:
        resources = cloudinary.api.resources(
            type="upload", prefix="story_books/", resource_type="raw"
        )["resources"]

        if resources:
            # 模式 A：尚未選取書籍，顯示 3 欄式卡片書櫃
            if not st.session_state.selected_book_id:
                st.header("📖 您的雲端故事書櫃")
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
                                    st.session_state.selected_book_id = (
                                        public_id
                                    )
                                    st.session_state.ch_index = 0
                                    st.rerun()

                            with b_col2:
                                if st.button(
                                    "🗑️ 刪除", key=f"del_{public_id}"
                                ):
                                    cloudinary.uploader.destroy(
                                        public_id, resource_type="raw"
                                    )
                                    st.toast(f"已從雲端刪除《{book_title}》")
                                    st.rerun()

            # 模式 B：已點擊閱讀，進入閱讀器模式（將控制項全部置於側邊欄）
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

                    # 從雲端下載並解析文章
                    response = requests.get(book_url)
                    chapters = parse_docx_bytes(response.content)
                    total_chapters = len(chapters)

                    if st.session_state.ch_index >= total_chapters:
                        st.session_state.ch_index = 0

                    chapter_titles = [ch["title"] for ch in chapters]

                    # ----------------- 側邊欄：懸浮控制面板 -----------------
                    st.sidebar.header("🎛️ 閱讀與音樂控制箱")
                    if st.sidebar.button(
                        "📚 返回圖書總書櫃", use_container_width=True
                    ):
                        st.session_state.selected_book_id = None
                        st.rerun()

                    st.sidebar.divider()
                    st.sidebar.subheader(f"📖 《{book_name}》")

                    # 側邊欄：快速跳轉章節選單
                    selected_ch_title = st.sidebar.selectbox(
                        "📌 快速選擇章節",
                        chapter_titles,
                        index=st.session_state.ch_index,
                        key="sb_side_chapter_select",
                    )

                    new_idx = chapter_titles.index(selected_ch_title)
                    if new_idx != st.session_state.ch_index:
                        st.session_state.ch_index = new_idx
                        st.rerun()

                    # 側邊欄：上一章 / 下一章 控制按鈕
                    nav_c1, nav_c2 = st.sidebar.columns(2)
                    with nav_c1:
                        if st.button(
                            "⬅️ 上一章",
                            disabled=(st.session_state.ch_index <= 0),
                            use_container_width=True,
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
                        ):
                            st.session_state.ch_index += 1
                            st.rerun()

                    st.sidebar.divider()

                    # 側邊欄：音樂播放器（隨時可點擊暫停/播放）
                    current_ch = chapters[st.session_state.ch_index]
                    st.sidebar.subheader("🎵 章節背景音樂")
                    if current_ch["music_url"]:
                        url = current_ch["music_url"]
                        if "youtube.com" in url or "youtu.be" in url:
                            st.sidebar.video(url)
                        else:
                            st.sidebar.audio(url)
                    else:
                        st.sidebar.caption("本章節未設定背景音樂。")

                    # ----------------- 主要區域：純粹內文閱讀區 -----------------
                    st.header(f"《{book_name}》")
                    st.subheader(current_ch["title"])
                    st.divider()

                    # 還原排版與段落留白
                    for line in current_ch["content"]:
                        if line.strip() == "":
                            st.markdown("&nbsp;")
                        else:
                            st.write(line)

        else:
            st.info("📚 雲端書櫃目前是空的，請在左側上傳您的第一本故事書！")
    except Exception as e:
        st.error(f"連線至雲端書櫃時發生錯誤：{e}")
else:
    st.warning("⚠️ 請先在 Streamlit Cloud 設定 Cloudinary API 金鑰。")
