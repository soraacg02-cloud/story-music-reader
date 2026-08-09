import docx
import streamlit as st

# 1. 設定網頁分頁標題與寬度
st.set_page_config(
    page_title="沉浸式故事音樂閱讀器", page_icon="📚", layout="wide"
)

st.title("📖 沉浸式故事音樂閱讀器")
st.caption("忠實還原 Word 文件段落留白與章節背景音樂。")

# 2. 側邊欄：多檔案上傳區
st.sidebar.header("📂 故事集上傳區")
uploaded_files = st.sidebar.file_uploader(
    "上傳 Word 故事檔 (.docx)", type=["docx"], accept_multiple_files=True
)


def parse_story_preserve_spacing(file):
    """解析 Word 檔案，並完整保留作者設定的空白行與段落間距"""
    doc = docx.Document(file)
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    for p in doc.paragraphs:
        text = p.text.rstrip()
        style_name = p.style.name.lower()

        # 判定是否為章節標題 (需套用標題樣式且非空字串)
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

        # 判定是否為音樂網址
        elif text.strip().startswith("http://") or text.strip().startswith(
            "https://"
        ):
            current_chapter["music_url"] = text.strip()

        # 一般故事內文 (包含空白段落)
        else:
            if not current_chapter["title"]:
                current_chapter["title"] = "前言/序章"
            # 關鍵修改：保留原始段落文字，即使是空行也不跳過
            current_chapter["content"].append(text)

    if current_chapter["title"]:
        chapters.append(current_chapter)

    return chapters


# 3. 網頁渲染邏輯
if uploaded_files:
    stories = {file.name: file for file in uploaded_files}
    selected_story_name = st.sidebar.selectbox(
        "📚 請選擇故事集", list(stories.keys())
    )

    if selected_story_name:
        story_file = stories[selected_story_name]
        chapters = parse_story_preserve_spacing(story_file)

        # 章節選單
        chapter_titles = [ch["title"] for ch in chapters]
        selected_ch_title = st.selectbox("📌 請選擇閱讀章節", chapter_titles)

        current_ch = next(
            ch for ch in chapters if ch["title"] == selected_ch_title
        )

        st.divider()
        st.header(current_ch["title"])

        # 音樂播放器
        if current_ch["music_url"]:
            url = current_ch["music_url"]
            if "youtube.com" in url or "youtu.be" in url:
                st.video(url)
            else:
                st.audio(url)
            st.success("🎵 背景音樂已成功載入！")

        st.divider()

        # 4. 忠實還原排版：遇空行輸出 HTML 不換行空格 &nbsp;
        for line in current_ch["content"]:
            if line.strip() == "":
                st.markdown("&nbsp;")  # 輸出一個空行高度
            else:
                st.write(line)
else:
    st.info("👈 請先在左側邊欄上傳一個或多個 Word (.docx) 故事檔案。")
