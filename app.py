import docx
import streamlit as st

# 1. 頁面基本設定
st.set_page_config(
    page_title="小說故事音樂閱讀器", page_icon="📚", layout="wide"
)

st.title("📖 沉浸式故事音樂閱讀器")
st.caption("上傳您的 Word 故事檔，體驗章節與背景音樂同步的閱讀享受。")

# 2. 左側邊欄：多檔案上傳區 (可同時上傳多個 Word 故事集)
st.sidebar.header("📂 故事集上傳區")
uploaded_files = st.sidebar.file_uploader(
    "上傳 Word 故事檔 (.docx)", type=["docx"], accept_multiple_files=True
)


def parse_word_story(file):
    """解析 Word (.docx) 檔案，自動提取章節標題、音樂網址與故事內文"""
    doc = docx.Document(file)
    chapters = []
    current_chapter = {"title": "前言/序章", "music_url": "", "content": []}

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        # 檢測是否為新章節 (比對標題符號或「第X章」)
        if any(
            text.startswith(prefix)
            for prefix in ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
        ) or "章" in text[:4]:
            if current_chapter["content"] or current_chapter["music_url"]:
                chapters.append(current_chapter)
            current_chapter = {"title": text, "music_url": "", "content": []}

        # 檢測音樂網址 (若內文出現 http 連結)
        elif text.startswith("http://") or text.startswith("https://"):
            current_chapter["music_url"] = text

        # 檢測音樂印象曲標題 (若尚未填入網址，可作備註說明)
        elif "印象曲" in text and not current_chapter["music_url"]:
            current_chapter["content"].append(f"*(音樂：{text})*")

        # 一般小說內文
        else:
            current_chapter["content"].append(text)

    # 加入最後一個章節
    if current_chapter["content"] or current_chapter["music_url"]:
        chapters.append(current_chapter)

    return chapters


# 3. 主要呈現邏輯
if uploaded_files:
    # 使用檔案名稱建立字典，達成多檔案獨立不干擾
    stories = {file.name: file for file in uploaded_files}

    # 選擇故事集
    selected_story_name = st.sidebar.selectbox(
        "📚 選擇故事集", list(stories.keys())
    )

    if selected_story_name:
        story_file = stories[selected_story_name]
        chapters = parse_word_story(story_file)

        # 章節選單
        chapter_titles = [ch["title"] for ch in chapters]
        selected_ch_title = st.selectbox("📌 請選擇閱讀章節", chapter_titles)

        # 取得當前章節
        current_ch = next(
            ch for ch in chapters if ch["title"] == selected_ch_title
        )

        st.divider()
        st.header(current_ch["title"])

        # 音樂播放介面
        if current_ch["music_url"]:
            st.audio(current_ch["music_url"])
            st.success("🎵 背景音樂載入成功！請點擊播放按鈕開始聆聽。")
        else:
            st.info(
                "💡 提示：若要在本章節自動載入音樂，請在 Word 該章節開頭加入 MP3 的 direct URL 網址（如：https://example.com/song.mp3）。"
            )

        st.divider()

        # 呈現故事內文
        for paragraph in current_ch["content"]:
            st.write(paragraph)

else:
    st.info("👈 請先在左側邊欄上傳一個或多個 Word (.docx) 故事檔案開始體驗。")
