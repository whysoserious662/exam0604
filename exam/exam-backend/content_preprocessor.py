"""
听力/阅读内容结构化预处理
将混合文本分离为：原文段落 + 题目列表 + 选项组
用于提升 distractor_strength / question_complexity / location_difficulty 精确度
"""
import re


def extract_passage_and_questions(content, qtype):
    """
    从混合内容中分离原文和题目。

    Returns:
        dict: {
            "passage": str | None,
            "directions": str,
            "question_groups": [
                {
                    "header": str,
                    "questions": [
                        {"number": int, "stem": str, "options": [{"label":"A","text":"..."},...]}
                    ]
                }
            ],
            "total_questions": int,
            "raw": str
        }
    """
    result = {
        "passage": None,
        "directions": "",
        "question_groups": [],
        "total_questions": 0,
        "raw": content,
    }

    # 1. 提取 Directions
    dir_match = re.search(
        r'(Section\s+[A-C]\s*Directions?\s*:.*?)'
        r'(?=Questions?\s+\d+\s+(?:to|and)|$)',
        content, re.DOTALL | re.IGNORECASE
    )
    if dir_match:
        result["directions"] = _clean(dir_match.group(1))

    # 2. 对于阅读：提取原文段落
    if qtype == "阅读":
        first_q = re.search(r'Questions?\s*\d+\s*(?:to|and)\s*\d+\s*are\s*based', content)
        if first_q:
            passage = content[:first_q.start()]
            passage = _clean_noise(passage)
            if len(passage.strip()) > 100:
                result["passage"] = passage.strip()
        else:
            # 无 Questions 标记时，尝试用 Section 标记分割
            sections = re.split(r'Section\s+[A-C]', content, flags=re.I)
            if len(sections) > 1:
                result["passage"] = _clean_noise(sections[1]).strip()

    # 3. 提取题目组（同时处理正常文本和PDF合并文本如"Questions46to50"）
    qg_header = re.compile(
        r'(Questions?\s*\d+\s*(?:to|and)\s*\d+\s+are\s+based\s*(?:on|upon)[^.]*\.)',
        re.IGNORECASE
    )
    # 也尝试宽松匹配（无空格版本）
    qg_header_loose = re.compile(
        r'(Questions?\s*\d+\s*(?:to|and)\s*\d+\s*are\s*based)',
        re.IGNORECASE
    )

    splits = qg_header.split(content)
    if len(splits) < 2:
        splits = qg_header_loose.split(content)

    # splits[0] = before first "Questions", splits[1]=header1, splits[2]=body1, ...
    for j in range(1, len(splits), 2):
        header = splits[j].strip()
        body = splits[j + 1] if j + 1 < len(splits) else ""

        questions = _extract_questions_from_group(body)
        if questions:
            result["question_groups"].append({
                "header": header,
                "questions": questions,
            })
            result["total_questions"] += len(questions)

    return result


def _extract_questions_from_group(body):
    """从一个题目组的 body 文本中提取每道题和选项"""
    questions = []

    # 尝试两种格式:
    # 格式A (听力): "N. A) text B) text C) text D) text" — 无独立题干
    # 格式B (阅读SectionC): "N. stem text ? A) text B) text C) text D) text" — 有题干

    # 先检测格式: "N. A)" 或 "N. A." → 听力格式, "N. What/Why..." → 阅读格式
    listening_match = re.search(r'\d+\.\s*[A-D][\).]', body)
    reading_match = re.search(r'\d+\.\s*[E-WZ]', body)  # E-W(非ABCD) = 题干首字母

    if listening_match and (not reading_match or listening_match.start() < reading_match.start()):
        # 听力格式: "N. A) text B) text..."
        q_pattern = re.compile(r'(\d+)\.\s*([A-Z]\))')
        positions = list(q_pattern.finditer(body))

        for k, match in enumerate(positions):
            num = int(match.group(1))
            first_label = match.group(2)[0]
            start = match.end()
            end = positions[k + 1].start() if k + 1 < len(positions) else len(body)
            full_text = body[start:end].strip()

            options = _extract_options(full_text)
            if not options or options[0]["label"] != first_label:
                next_label_match = re.search(r'[A-D]\)', full_text)
                first_opt_text = full_text[:next_label_match.start()] if next_label_match else full_text
                options.insert(0, {"label": first_label, "text": _clean(first_opt_text)})

            if options:
                questions.append({"number": num, "stem": "", "options": options})

    elif reading_match:
        # 阅读格式: "N. stem text ? A. text B. text..." 或 "N. stem text ? A) text B)..."
        q_pattern = re.compile(r'(\d+)\.\s*')
        parts = list(q_pattern.finditer(body))

        for k, match in enumerate(parts):
            num = int(match.group(1))
            start = match.end()
            end = parts[k + 1].start() if k + 1 < len(parts) else len(body)
            full_text = body[start:end].strip()

            options = _extract_options(full_text)
            stem = full_text
            if options:
                # 找第一个选项标记位置
                first_opt_pos = None
                for marker in [f"{options[0]['label']})", f"{options[0]['label']}."]:
                    pos = full_text.find(marker)
                    if pos > 0:
                        first_opt_pos = pos
                        break
                if first_opt_pos:
                    stem = full_text[:first_opt_pos]
                elif '?' in full_text:
                    qm = full_text.rfind('?')
                    if qm > 0:
                        stem = full_text[:qm + 1]

            stem = _clean(stem)
            if options:
                questions.append({"number": num, "stem": stem, "options": options})

    else:
        # 回退: 直接提取所有选项
        all_options = _extract_options(body)
        if all_options:
            questions.append({"number": 1, "stem": "", "options": all_options})

    return questions


def _extract_options(text):
    """提取选项，支持 A) / B) / C) / D) 或 A. / B. / C. / D. 两种格式"""
    # 检测使用哪种格式
    if re.search(r'[A-D]\)', text):
        sep = r'\s*([A-D])\)\s*'
    else:
        sep = r'\s*([A-D])\.\s*'

    parts = re.split(sep, text)

    options = []
    for j in range(1, len(parts), 2):
        label = parts[j]
        opt_text = parts[j + 1] if j + 1 < len(parts) else ""
        # 截断到下一个问题起始
        end = re.search(r'\d+\.\s*[A-Z]', opt_text)
        if end:
            opt_text = opt_text[:end.start()]
        opt_text = _clean(opt_text)
        if opt_text:
            options.append({"label": label, "text": opt_text})

    return options if len(options) >= 2 else []


def _clean_noise(text):
    """清除格式噪声"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'\(\d+\s*minutes?\)', '', text, flags=re.I)
    text = re.sub(r'Part\s+(I|II|III|IV|V|VI+)', '', text, flags=re.I)
    text = re.sub(r'Section\s+[A-C]', '', text, flags=re.I)
    text = re.sub(r'by\s*:.*?$', '', text, flags=re.M)
    text = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _clean(text):
    """清理空白"""
    return re.sub(r'\s+', ' ', text).strip()


def format_structured_for_prompt(structured):
    """将结构化数据格式化为 AI Prompt 可读的文本"""
    lines = []

    if structured.get("passage"):
        passage = structured["passage"]
        # 截断过长的原文到 3000 字符
        if len(passage) > 3000:
            passage = passage[:3000] + "\n...[原文已截断]"
        lines.append("【原文段落】")
        lines.append(passage)
        lines.append("")

    if structured.get("question_groups"):
        for g in structured["question_groups"]:
            lines.append(f"[{g['header']}]")
            for q in g["questions"]:
                lines.append(f"  第{q['number']}题: {q['stem']}")
                opt_text = " | ".join(f"{o['label']}) {o['text'][:120]}" for o in q['options'])
                lines.append(f"    选项: {opt_text}")
            lines.append("")

    return "\n".join(lines)
