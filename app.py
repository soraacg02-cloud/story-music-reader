def parse_docx_bytes(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    chapters = []
    current_chapter = {"title": "", "music_url": "", "content": []}

    # 正則表達式：支援「第一章」、「第1章」、「第 1 章」等章節格式
    chapter_regex = re.compile(r"^第[0-9一二三四五六七八九十百千]+章")

    for p in doc.paragraphs:
        text = p.text.rstrip()
        
        # 安全取得 style_name，避免 NoneType 報錯
        style_name = ""
        if p.style and hasattr(p.style, "name") and p.style.name:
            style_name = p.style.name.lower()

        clean_text = text.strip()

        # 判定是否為標題：樣式包含 heading/標題，或是文字開頭符合「第X章」
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
            current_chapter["music_url"] = clean_text
        else:
            if not current_chapter["title"]:
                current_chapter["title"] = "前言/序章"
            if clean_text != "":
                current_chapter["content"].append(text)

    if current_chapter["title"] or current_chapter["content"]:
        chapters.append(current_chapter)

    # 若全文都沒有章節標題，自動包裝為單一章節防呆
    if not chapters:
        chapters.append({
            "title": "全一冊",
            "music_url": "",
            "content": [p.text for p in doc.paragraphs if p.text.strip() != ""]
        })

    return chapters
