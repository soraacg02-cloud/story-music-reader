import docx
import streamlit as st

# 設定網頁標題與寬度
st.set_page_config(
    page_title="沉浸式故事音樂閱讀器", page_icon="📚", layout="wide"
)

st.title("📖 沉浸式故事音樂閱讀器")
st.caption(
    "上傳 Word 故事檔，程式會自動識別 Word 中的『標題樣式』進行章節拆解！"
)

# 左側邊欄：支援多檔案上傳
st.sidebar.header("📂 故事集上傳區")
uploaded_files = st.sidebar.file_uploader(
    "上傳 Word 故事檔 (.docx)", type=["docx"], accept_multiple_files=True
)


def parse_story_by_style(file):
    """透過 Word 的『段落樣式 (Style)』來精準辨識章節標題"""
    doc = docx.Document(file)
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        # 核心判斷：檢查該段落的樣式名稱是否包含 "Heading" 或 "標題"
        # 只要您在 Word 裡設為「標題 1」、「標題 2」等，style.name 都會包含這些關鍵字
        style_name = p.style.name.lower()
        is_heading = "heading" in style_name or "標題" in style_name

        if is_heading:
            # 如果目前已經有讀取的章節，先存入清單中
            if current_chapter["title"]:
                chapters.append(current_chapter)
            # 開啟新章節
            current_chapter = {"title": text, "music_url": "", "content": []}

        # 檢測音樂網址 (包含 YouTube 或 MP3 網址)
        elif text.startswith("http://") or text.startswith("https://"):
            current_chapter["music_url"] = text

        # 一般故事內文
        else:
            if not current_chapter["title"]:
                # 萬一文件開頭沒有設標題，預設為「前言/序章」
                current_chapter["title"] = "前言/序章"
            current_chapter["content"].append(text)

    # 存入最後一個章節
    if current_chapter["title"]:
        chapters.append(current_chapter)

    return chapters


# 主要渲染邏輯
if uploaded_files:
    stories = {file.name: file for file in uploaded_files}
    selected_story_name = st.sidebar.selectbox(
        "📚 請選擇故事集", list(stories.keys())
    )

    if selected_story_name:
        story_file = stories[selected_story_name]
        chapters = parse_story_by_style(story_file)

        # 提取章節選單
        chapter_titles = [ch["title"] for ch in chapters]
        selected_ch_title = st.selectbox("📌 請選擇閱讀章節", chapter_titles)

        # 取得目前選取的章節內容
        current_ch = next(
            ch for ch in chapters if ch["title"] == selected_ch_title
        )

        st.divider()
        st.header(current_ch["title"])

        # 自動播放背景音樂 (支援 YouTube 影片與 MP3 音訊)
        if current_ch["music_url"]:
            url = current_ch["music_url"]
            if "youtube.com" in url or "youtu.be" in url:
                st.video(url)
            else:
                st.audio(url)
            st.success("🎵 背景音樂已成功載入！")

        st.divider()

        # 渲染章節故事內文
        for line in current_ch["content"]:
            st.write(line)
else:
    st.info("👈 請先在左側邊欄上傳一個或多個 Word (.docx) 故事檔案。")
