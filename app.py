import io
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

# 2. 初始化 Cloudinary 連線 (讀取 Secrets 設定)
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True,
    )


def parse_docx_bytes(file_bytes):
    """解析下載好的 Word 檔案內容，並保留段落留白與樣式"""
    doc = docx.Document(io.BytesIO(file_bytes))
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    for p in doc.paragraphs:
        text = p.text.rstrip()
        style_name = p.style.name.lower()

        # 判定標題樣式
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


# 3. 側邊欄：新書上傳區 (同步上傳至 Cloudinary 雲端)
st.sidebar.header("📤 新增故事入庫")
new_file = st.sidebar.file_uploader("上傳 Word 故事檔 (.docx)", type=["docx"])

if new_file and "cloudinary" in st.secrets:
    if st.sidebar.button("💾 確認存入雲端書櫃"):
        with st.spinner("正在上傳至雲端書櫃..."):
            # 上傳原始 Word 檔案至 Cloudinary 的 raw 目錄
            cloudinary.uploader.upload(
                new_file,
                resource_type="raw",
                public_id=f"story_books/{new_file.name}",
                overwrite=True,
            )
            st.sidebar.success(f"《{new_file.name}》已成功收錄進書櫃！")

# 4. 主頁面：雲端書櫃選單
st.sidebar.divider()
st.sidebar.header("📖 您的雲端書櫃")

if "cloudinary" in st.secrets:
    try:
        # 向 Cloudinary 查詢 story_books/ 目錄下的所有書籍
        resources = cloudinary.api.resources(
            type="upload", prefix="story_books/", resource_type="raw"
        )["resources"]

        if resources:
            book_options = {
                res["public_id"].replace("story_books/", ""): res["secure_url"]
                for res in resources
            }
            selected_book_name = st.sidebar.selectbox(
                "請選擇想閱讀的故事書", list(book_options.keys())
            )

            if selected_book_name:
                # 下載選中的 Word 檔案
                book_url = book_options[selected_book_name]
                response = requests.get(book_url)

                # 解析並呈現故事
                chapters = parse_docx_bytes(response.content)

                chapter_titles = [ch["title"] for ch in chapters]
                selected_ch_title = st.selectbox(
                    "📌 請選擇章節", chapter_titles
                )
                current_ch = next(
                    ch for ch in chapters if ch["title"] == selected_ch_title
                )

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
        else:
            st.info("📚 雲端書櫃目前是空的，請在左側上傳您的第一本故事書！")
    except Exception as e:
        st.error(f"連線至雲端書櫃時發生錯誤：{e}")
else:
    st.warning("⚠️ 請先在 Streamlit Cloud 設定 Cloudinary API 金鑰。")
