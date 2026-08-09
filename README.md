# 📚 沉浸式故事音樂閱讀器 (Story Music Reader)

一個基於 Python 與 Streamlit 開發的線上閱讀工具。上傳 Word (.docx) 格式的故事檔案，系統會自動解析章節結構，並即時搭配對應的背景音樂，為讀者提供沉浸式的閱讀體驗。

## ✨ 核心特色

* **多故事集管理**：支援同時上傳多個 Word 檔案，選單隨時切換，資料獨立不干擾。
* **章節自動解析**：自動識別 Word 中的章節標題（如 `①`、`②` 或 `第X章`）。
* **背景音樂連動**：偵測章節內嵌入的 MP3 / 音訊 direct URL 連結，動態生成 HTML5 播放器。
* **雲端極速部署**：完全相容 Streamlit Cloud，開啟瀏覽器即可使用。

## 🛠️ 技術棧 (Tech Stack)

* **Language:** Python 3.9+
* **Frontend/Framework:** [Streamlit](https://streamlit.io/)
* **Document Parsing:** [python-docx](https://python-docx.readthedocs.io/)
* **Hosting:** GitHub + Streamlit Cloud

## 🚀 快速開始 (Quick Start)

### 本地端執行 (Local Development)

1. **克隆專案 (Clone Repository)**
   ```bash
   git clone [https://github.com/你的帳號/story-audio-reader.git](https://github.com/你的帳號/story-audio-reader.git)
   cd story-audio-reader
