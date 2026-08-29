import io
import re
import urllib.request
import streamlit as st
import docx
import cloudinary
import cloudinary.api

# ==========================================
# 1. 頁面基本配置 (Page Config)
# ==========================================
st.set_page_config(
    page_title="雲端故事音樂書櫃",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 自訂 CSS 樣式 (注入主題與精準排版)
# ==========================================
def apply_custom_css(theme_mode):
    if theme_mode == "暗黑模式 (Dark)":
        bg_color = "#121212"
        text_color = "#E0E0E0"
        card_bg = "#181818"
        border_color = "#2A2A2A"
        accent_color = "#4DA6FF"
    else:  # 明亮模式 (Light)
        bg_color = "#F8F9FA"
        text_color = "#212529"
        card_bg = "#FFFFFF"
        border_color = "#E9ECEF"
        accent_color = "#0066CC"

    custom_css = f"""
    <style>
    /* 全域字體與背景設定 */
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", sans-serif;
    }}
    
    /* 文章閱讀內文控制容器 */
    .story-container {{
        background-color: {card_bg};
        padding: 2.5rem;
        border-radius: 12px;
        border: 1px solid {border_color};
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
    }}
    
    /* 修正段落上下距，精準還原單行間距 */
    .story-line {{
        margin: 0;
        padding: 0;
        line-height: 1.85;
        font-size: 1.125rem;
        color: {text_color};
        word-wrap: break-word;
    }}
    
    /* Word 檔案空行/Enter 間距比例區塊 */
    .empty-line-spacer {{
        height: 1.25rem;
        width: 100%;
    }}

    /* 章節標題樣式 */
    .chapter-title {{
        color: {accent_color};
        font-weight: 700;
        font-size: 1.75rem;
        margin-bottom: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid {border_color};
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 3. Cloudinary 與 檔案解析 (Cached Functions)
# ==========================================
@st.cache_data(ttl=600)
def fetch_cloudinary_catalog():
    """從 Cloudinary 抓取所有 docx 檔案清單"""
    try:
        # 設定 Cloudinary API 憑證 (已修復舊版 Api 匯入問題)
        cloudinary.config(
            cloud_name=st.secrets["cloudinary"]["cloud_name"],
            api_key=st.secrets["cloudinary"]["api_key"],
            api_secret=st.secrets["cloudinary"]["api_secret"]
        )
        
        # 抓取資源類型為 raw 的所有 .docx 檔案
        resources = cloudinary.api.resources(type="upload", resource_type="raw", max_results=500)
        file_list = []
        for res in resources.get("resources", []):
            filename = res.get("public_id", "")
            if filename.endswith(".docx"):
                file_list.append({
                    "public_id": filename,
                    "url": res.get("secure_url")
                })
        return file_list
    except Exception as e:
        st.error(f"無法從 Cloudinary 載入檔案清單: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_docx_bytes(url):
    """下載 DOCX 檔案位元組"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return response.read()
    except Exception as e:
        st.error(f"下載 Word 檔案失敗: {e}")
        return None

def parse_docx_bytes(file_bytes):
    """
    【核心排版修復】：精準解析 Word 檔案內容與空行
    完整保留 text 為空字串（按 Enter 產生）的段落，維持與原始 Word 文件完全一致的空間間距
    """
    doc = docx.Document(io.BytesIO(file_bytes))
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    # 匹配「第一章」、「第1章」等標題的正則表達式
    chapter_regex = re.compile(r"^第\s*[0-9一二三四五六七八九十百千]+\s*章")

    for p in doc.paragraphs:
        text = p.text.rstrip("\r\n")  # 保留內容，僅清除末尾換行符

        style_name = ""
        if p.style and hasattr(p.style, "name") and p.style.name:
            style_name = p.style.name.lower()

        clean_text = text.strip()

        # 判斷是否為章節標題
        is_heading = (
            ("heading" in style_name or "標題" in style_name) and clean_text != ""
        ) or bool(chapter_regex.match(clean_text))

        if is_heading:
            if current_chapter["title"] or current_chapter["content"]:
                chapters.append(current_chapter)
            current_chapter = {
                "title": clean_text,
                "music_url": "",
                "content": [],
            }
        elif clean_text.startswith("http://") or clean_text.startswith("https://"):
            # 如果整行是音樂/音訊網址，設為章節背景音訊
            current_chapter["music_url"] = clean_text
        else:
            if not current_chapter["title"]:
                current_chapter["title"] = "前言/序章"
            
            # 【關鍵修復點】：保留空字串，以反映 Word 當中的 Enter 空行
            current_chapter["content"].append(text)

    if current_chapter["title"] or current_chapter["content"]:
        chapters.append(current_chapter)

    # 若未偵測到章節標題，預設作為單一章節
    if not chapters:
        chapters.append({
            "title": "全一冊",
            "music_url": "",
            "content": [p.text.rstrip("\r\n") for p in doc.paragraphs]
        })

    return chapters

# ==========================================
# 4. Callback 函式 (狀態維護)
# ==========================================
def prev_chapter_cb():
    if st.session_state.current_chapter_idx > 0:
        st.session_state.current_chapter_idx -= 1
        st.session_state.selected_line_idx = 0

def next_chapter_cb(max_idx):
    if st.session_state.current_chapter_idx < max_idx:
        st.session_state.current_chapter_idx += 1
        st.session_state.selected_line_idx = 0

def on_book_change_cb():
    st.session_state.current_chapter_idx = 0
    st.session_state.selected_line_idx = 0

# ==========================================
# 5. 主程式流程
# ==========================================
def main():
    # 初始化 Session State
    if "current_chapter_idx" not in st.session_state:
        st.session_state.current_chapter_idx = 0
    if "selected_line_idx" not in st.session_state:
        st.session_state.selected_line_idx = 0

    # 側邊欄：主題與藏書選擇
    with st.sidebar:
        st.title("📚 雲端故事音樂書櫃")
        
        theme_mode = st.radio(
            "🎨 顯示主題",
            ["暗黑模式 (Dark)", "明亮模式 (Light)"],
            index=0
        )
        
        st.divider()

        # 抓取 Cloudinary 書庫
        catalog = fetch_cloudinary_catalog()
        if not catalog:
            st.warning("目前書櫃中沒有找到 Word (.docx) 檔案。")
            return

        book_names = [b["public_id"] for b in catalog]
        selected_book_name = st.selectbox(
            "📖 選擇書籍",
            book_names,
            on_change=on_book_change_cb
        )

        selected_book_info = next(b for b in catalog if b["public_id"] == selected_book_name)

    # 載入 CSS
    apply_custom_css(theme_mode)

    # 下載並解析 Word 檔案
    file_bytes = fetch_docx_bytes(selected_book_info["url"])
    if not file_bytes:
        st.error("無法開啟書籍檔案。")
        return

    chapters = parse_docx_bytes(file_bytes)
    total_chapters = len(chapters)

    # 安全索引邊界處理
    if st.session_state.current_chapter_idx >= total_chapters:
        st.session_state.current_chapter_idx = 0

    current_ch = chapters[st.session_state.current_chapter_idx]

    # 側邊欄：章節導覽與段落跳轉
    with st.sidebar:
        st.divider()
        st.subheader("📑 章節選單")
        
        chapter_titles = [f"{i+1}. {ch['title']}" for i, ch in enumerate(chapters)]
        
        selected_ch_idx = st.selectbox(
            "跳轉章節",
            range(total_chapters),
            format_func=lambda x: chapter_titles[x],
            index=st.session_state.current_chapter_idx
        )
        if selected_ch_idx != st.session_state.current_chapter_idx:
            st.session_state.current_chapter_idx = selected_ch_idx
            st.session_state.selected_line_idx = 0
            st.rerun()

        # 精準段落跳轉 Slider
        content_lines = current_ch["content"]
        if content_lines:
            st.subheader("🎯 段落定位")
            max_lines = len(content_lines) - 1
            if max_lines > 0:
                st.session_state.selected_line_idx = st.slider(
                    "跳轉至行號",
                    0, max_lines,
                    value=min(st.session_state.selected_line_idx, max_lines)
                )

    # 主閱讀區塊
    st.markdown(f"<div class='chapter-title'>{current_ch['title']}</div>", unsafe_allow_html=True)

    # 如果章節有背景音樂，播放音訊
    if current_ch["music_url"]:
        st.audio(current_ch["music_url"])
        st.caption("🎵 背景配樂播放中")

    # 閱讀區核心渲染
    st.markdown("<div class='story-container'>", unsafe_allow_html=True)
    
    for idx, line in enumerate(content_lines):
        # 建立 HTML 錨點 (Anchor) 供平滑滾動跳轉
        st.markdown(f'<div id="line-anchor-{idx}"></div>', unsafe_allow_html=True)
        
        # 【排版關鍵】：判斷是否為 Word 中的 Enter 空行
        if line.strip() == "":
            # 渲染一個固定高度的空白 spacer，完美還原 Word 連續 Enter 的空行數
            st.markdown("<div class='empty-line-spacer'></div>", unsafe_allow_html=True)
        else:
            # 渲染正常文字段落
            st.markdown(f"<p class='story-line'>{line}</p>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # JS 自動平滑滾動至 slider 所選取的段落（具備重試機制，確保 DOM 載入完畢）
    if st.session_state.selected_line_idx > 0:
        target_line_idx = st.session_state.selected_line_idx
        js_scroll = f"""
        <script>
            function scrollToAnchor(targetId, retries = 5) {{
                const pDoc = window.parent.document;
                const targetAnchor = pDoc.getElementById(targetId);
                if (targetAnchor) {{
                    targetAnchor.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }} else if (retries > 0) {{
                    setTimeout(() => scrollToAnchor(targetId, retries - 1), 100);
                }}
            }}
            scrollToAnchor("line-anchor-{target_line_idx}");
        </script>
        """
        st.components.v1.html(js_scroll, height=0)

    # 頁面底部：章節切換按鈕
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.button(
            "⬅️ 上一章",
            on_click=prev_chapter_cb,
            disabled=(st.session_state.current_chapter_idx == 0),
            use_container_width=True
        )
    with col2:
        st.write(f"<p style='text-align: center;'>章節 {st.session_state.current_chapter_idx + 1} / {total_chapters}</p>", unsafe_allow_html=True)
    with col3:
        st.button(
            "下一章 ➡️",
            on_click=next_chapter_cb,
            args=(total_chapters - 1,),
            disabled=(st.session_state.current_chapter_idx == total_chapters - 1),
            use_container_width=True
        )

if __name__ == "__main__":
    # 確保 Secrets 安全設定提示
    if "cloudinary" not in st.secrets:
        st.warning("⚠️ 請先在 Streamlit Cloud 的 Secrets 設定檔中配置 Cloudinary API 金鑰（st.secrets['cloudinary']）。")
    else:
        main()
