import streamlit as st

# ... (前面的 Session State 與初始設定保持不變)

# 關鍵技術：在章節切換後，自動注入平滑捲動指令
def scroll_to_top():
    st.components.v1.html(
        """
        <script>
            // 讓網頁平滑捲動到最頂端
            window.parent.scrollTo({top: 0, behavior: 'smooth'});
        </script>
        """,
        height=0,
    )

# 在切換章節的 Callback 函式中呼叫它
def prev_chapter_cb():
    if st.session_state.ch_index > 0:
        st.session_state.ch_index -= 1
        st.session_state.reading_pct = 0
        scroll_to_top() # 觸發捲動

def next_chapter_cb():
    if st.session_state.ch_index < st.session_state.max_chapters - 1:
        st.session_state.ch_index += 1
        st.session_state.reading_pct = 0
        scroll_to_top() # 觸發捲動
