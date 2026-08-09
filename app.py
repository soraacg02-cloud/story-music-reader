import streamlit as st

# 1. 設定網頁頁面配置
st.set_page_config(page_title="雲端故事音樂書櫃", page_icon="📚", layout="wide")

# 2. 初始化主題紀錄 (預設為黑底模式)
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 黑底模式"

# 3. 側邊欄：主題模式切換按鈕（手機點擊友善）
st.sidebar.header("🎨 視覺與色彩設定")
st.session_state.theme_mode = st.sidebar.radio(
    "選擇閱讀背景風格：",
    ["🌙 黑底模式", "☀️ 白底模式"],
    index=0 if st.session_state.theme_mode == "🌙 黑底模式" else 1
)

# 4. 根據切換狀態，指定對應的顏色彩代碼
if st.session_state.theme_mode == "🌙 黑底模式":
    bg_color = "#0e1117"      # 深黑背景
    text_color = "#e0e0e0"    # 舒適軟白字
    card_bg = "#1f232a"       # 卡片深灰色
else:
    bg_color = "#f9f9fb"      # 柔和米白背景
    text_color = "#1f232a"    # 深灰黑字
    card_bg = "#ffffff"       # 卡片純白色

# 5. 注入 CSS 樣式（就像幫網頁即時換衣服）
theme_css = f"""
<style>
    .stApp {{
        background-color: {bg_color} !important;
    }}
    div[data-testid="stSidebar"] {{
        background-color: {card_bg} !important;
    }}
    div[data-testid="stContainer"] {{
        background-color: {card_bg} !important;
        border-radius: 10px;
    }}
    p, h1, h2, h3, h4, span, label {{
        color: {text_color} !important;
    }}
</style>
"""
st.markdown(theme_css, unsafe_allow_html=True)

# 6. 主要內容展示區
st.title("📚 雲端沉浸式故事音樂書櫃")
st.write("這是一段範例文字。點擊左側選單的單選按鈕，就能即時在黑底與白底模式之間無縫切換！")
