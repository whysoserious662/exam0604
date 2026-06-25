"""
CET-4 真题精准解析器
将 PDF 试卷按 Part → Section → QuestionGroup → Individual Question 四级拆分
每道题独立存储，保留选项、题号、原文段落、所属大题等完整信息
"""
import re
import json
import pdfplumber
from dataclasses import dataclass, field


@dataclass
class ParsedQuestion:
    """解析后的单道题目"""
    question_number: int
    content: str                        # 题干
    type: str                           # writing/listening/reading/translation
    section: str                        # 所属大题 e.g. "Listening Section A"
    options: list = field(default_factory=list)   # [{"label":"A","text":"..."}]
    answer: str = ""
    analysis: str = ""
    difficulty: int = 2
    knowledge_id: int = 1
    score: float = 1.0
    passage_text: str = ""              # 阅读题原文段落
    source: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def _clean(text):
    """归一化空白"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def _norm(text):
    """轻度清理：保留换行，只去掉行首尾空白"""
    if not text:
        return ""
    return '\n'.join(line.strip() for line in text.split('\n') if line.strip())


def _clean_artifacts(text):
    """移除PDF页眉页脚、水印、URL等非题目内容"""
    if not text:
        return text
    # 淘宝店铺水印
    text = re.sub(r'淘宝店铺.*?(?:温馨提示|预祝)', '', text)
    text = re.sub(r'光速考研工作室', '', text)
    # OCR乱码日期行（如 "22001166年 年 四 四 六六级级"）
    text = re.sub(r'[\d\s]{5,}年\s*年\s*.{10,}级级', '', text)
    # 页码标记 "第X页 共X页"
    text = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', text)
    # URL
    text = re.sub(r'https?://\S+', '', text)
    # 水印 "by:新一文化" "by:xxx"
    text = re.sub(r'by\s*:\s*\S+', '', text, flags=re.IGNORECASE)
    # 试卷标题行（含年月+真题+第X套）
    text = re.sub(r'\d{4}\s*年\s*\d{1,2}\s*月\s*(?:大学\s*)?英语\s*四级\s*(?:考试\s*)?真题\s*(?:第\s*\d+\s*套)?', '', text)
    text = re.sub(r'\d{4}\s*年\s*\d{1,2}\s*月\s*(?:大学\s*)?英语\s*四级\s*(?:考试\s*)?真题\s*\(?\s*第\s*\d+\s*套\s*\)?', '', text)
    text = re.sub(r'大学英语四级考试\s*\d{4}\s*年\s*\d{1,2}\s*月\s*真题\s*\(?\s*第\s*\d+\s*套\s*\)?', '', text)
    # 微信公众号/推广信息
    text = re.sub(r'微\s*信\s*公\s*众\s*号\s*[:：]\s*\S+', '', text)
    text = re.sub(r'关\s*注\s*微\s*信\s*公\s*众\s*号\s*\S*', '', text)
    # 多出来的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _extract_options(text):
    """从文本中提取 A) B) C) D) 或 A. B. C. D. 格式的选项
    返回 ([{"label":"A","text":"..."}], remaining_stem_text)"""
    options = []
    stem = text

    # 检测格式
    has_paren = bool(re.search(r'\b[A-D]\)', text))
    has_dot = bool(re.search(r'\b[A-D]\.\s', text))

    if has_paren:
        sep_re = r'\b([A-D])\)\s*'
    elif has_dot:
        sep_re = r'\b([A-D])\.\s*'
    else:
        return [], text

    # 找到第一个选项的位置
    first_opt = re.search(sep_re, text)
    if not first_opt:
        return [], text

    # 选项之前的是题干
    stem = _clean(text[:first_opt.start()])

    # 提取各个选项
    parts = re.split(sep_re, text[first_opt.start():])
    # parts[0] = '' (before first sep), parts[1]=label1, parts[2]=text1, parts[3]=label2, ...
    for i in range(1, len(parts), 2):
        label = parts[i]
        # 拿到选项文本，截断到下一个选项或末尾
        opt_text = parts[i + 1] if i + 1 < len(parts) else ""
        # 去杂质
        opt_text = _clean(opt_text)
        if opt_text and len(opt_text) > 1:
            options.append({"label": label, "text": opt_text})

    # 按label排序，修复双栏PDF导致的选项乱序（如A,C,B,D → A,B,C,D）
    options.sort(key=lambda o: o["label"])

    # 按label去重，修复双层PDF文字导致的选项重复（如A,A,B,B,C,C,D,D）
    seen_labels = set()
    unique_options = []
    for opt in options:
        if opt["label"] not in seen_labels:
            seen_labels.add(opt["label"])
            unique_options.append(opt)
    options = unique_options

    return (options if len(options) >= 2 else []), stem


# ═══════════════════════════════════════════════════════════════════════════════
# PDF 文本提取
# ═══════════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_path):
    """从 PDF 提取纯文本，处理重复行和OCR乱码"""
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    t = _clean_artifacts(t)
                    # 精确去重：PDF双层文字导致完全相同的行出现两次
                    lines = t.split('\n')
                    seen = set()
                    unique_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if stripped and stripped not in seen:
                            seen.add(stripped)
                            unique_lines.append(line)
                        elif not stripped:
                            unique_lines.append(line)
                    t = '\n'.join(unique_lines)
                    full_text += t + "\n\n"
    except Exception:
        return ""
    return full_text


# ═══════════════════════════════════════════════════════════════════════════════
# Part 级拆分
# ═══════════════════════════════════════════════════════════════════════════════

PART_PATTERNS = [
    # 灵活匹配：Part 后的空格和罗马数字可能粘连或OCR乱码
    # "Comprehension" 可能被OCR拆成 "Comprehensi ． on" 等，只匹配前缀
    ("写作", re.compile(r'Part\s*\S*\s*Writing', re.IGNORECASE)),
    ("听力", re.compile(r'Part\s*\S*\s*Listening\s*Comprehen', re.IGNORECASE)),
    ("阅读", re.compile(r'Part\s*\S*\s*Reading\s*Comprehen', re.IGNORECASE)),
    ("翻译", re.compile(r'Part\s*\S*\s*Translation', re.IGNORECASE)),
]


def split_by_parts(full_text):
    """按 Part I-IV 拆分全文，返回 {type: text}"""
    parts = {}
    positions = []
    for qtype, pattern in PART_PATTERNS:
        m = pattern.search(full_text)
        if m:
            positions.append((m.start(), qtype))

    positions.sort()
    for i, (pos, qtype) in enumerate(positions):
        start = pos
        end = positions[i + 1][0] if i + 1 < len(positions) else len(full_text)
        parts[qtype] = full_text[start:end]

    return parts


# ═══════════════════════════════════════════════════════════════════════════════
# Writing 解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_writing(part_text, source=""):
    content = _clean(part_text)
    dir_match = re.search(r'Directions:', content, re.IGNORECASE)
    if dir_match:
        content = content[dir_match.start():]

    return [ParsedQuestion(
        question_number=1,
        content=content,
        type="写作",
        section="Writing",
        difficulty=2,
        score=106.5,
        source=source,
    )]


# ═══════════════════════════════════════════════════════════════════════════════
# Listening 解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_listening(part_text, source=""):
    """
    听力格式特征：
    1. A) text B) text C) text D) text   （无独立题干，直接选项）
    2. A) text B) text C) text D) text
    ...
    题干在录音中，试卷上只印选项
    """
    questions = []
    # 保留换行进行解析
    text = _norm(part_text)

    sections = _split_by_sections(text)

    for sec_label, sec_text in sections:
        groups = _split_question_groups(sec_text)

        for group_header, group_body in groups:
            qs = _extract_listening_questions(
                group_body, f"Listening {sec_label}", source
            )
            questions.extend(qs)

    return questions


def _extract_listening_questions(text, section, source):
    """听力专用：题目格式为 'N. A) ... B) ... C) ... D) ...' 无独立题干"""
    questions = []

    # 保留换行
    text = _norm(text)

    # 匹配 "N. " 或 "N.A)" 开头的行（新老PDF格式兼容）
    q_pattern = re.compile(r'(?:^|\n)\s*(\d{1,3})\.\s*')
    matches = list(q_pattern.finditer(text))

    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _norm(text[start:end])

        options, _ = _extract_options(body)

        if not options or len(options) < 4:
            # 尝试更宽松的匹配
            body_clean = _clean(body)
            options, _ = _extract_options(body_clean)

        # 听力题标准为4个选项，不足则丢弃
        if options and len(options) == 4:
            opt_summary = " | ".join(f"{o['label']}) {o['text'][:60]}" for o in options)
            questions.append(ParsedQuestion(
                question_number=num,
                content=f"[听力第{num}题]\n{opt_summary}",
                type="听力",
                section=section,
                options=options,
                difficulty=2,
                score=_default_score("听力", section),
                source=source,
            ))
        # 选项不足4个的听力题直接丢弃不存

    return questions


# ═══════════════════════════════════════════════════════════════════════════════
# Reading 解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_reading(part_text, source=""):
    """阅读部分：Section A(选词填空) / B(段落匹配) / C(仔细阅读)"""
    questions = []
    text = _norm(part_text)

    sections = _split_by_sections(text)

    for sec_label, sec_text in sections:
        sec_upper = sec_label.upper().strip()

        if 'A' in sec_upper:
            qs = _parse_reading_section_a(sec_text, sec_label, source)
        elif 'B' in sec_upper:
            qs = _parse_reading_section_b(sec_text, sec_label, source)
        elif 'C' in sec_upper:
            qs = _parse_reading_section_c(sec_text, sec_label, source)
        else:
            qs = []

        questions.extend(qs)

    return questions


def _parse_reading_section_a(sec_text, sec_label, source):
    """选词填空：一篇短文10个空(26-35) + 词库(A-O共15个词)"""
    questions = []

    # 跳过 Directions 部分：找到第一个数字标记 26 的位置
    passage_start = None
    m26 = re.search(r'(?:^|\n|\s)26(?:\s|\n|$)', sec_text)
    # 也尝试在 Directions 结束后找短文开始
    dir_end = re.search(r'more\s+than\s+once\.', sec_text, re.IGNORECASE)
    if dir_end:
        passage_start = dir_end.end()
    elif m26:
        # 从 26 往前找句子开始
        passage_start = max(0, m26.start() - 200)

    if passage_start and passage_start < len(sec_text):
        body_text = sec_text[passage_start:]
    else:
        body_text = sec_text

    # 找到词库开始位置：词库位于Section A末尾，每行可能含双栏两个词
    # 特征：每行有多个 X) word 格式（如 "A) adult I) emotional"）
    lines = body_text.split('\n')
    wb_start_idx = None
    wb_entries_raw = []
    # 从后往前找词库起始行（有多条 X) word 的行）
    for i in range(len(lines) - 1, -1, -1):
        spots = list(re.finditer(r'\b([A-O0])[\)\.]\s*(\S+)', lines[i]))
        if len(spots) >= 2:
            wb_start_idx = i
            break

    if wb_start_idx is not None:
        # 向前扩展到词库第一行（连续有 X) word 的行）
        while wb_start_idx > 0:
            prev_spots = list(re.finditer(r'\b([A-O0])[\)\.]\s*(\S+)', lines[wb_start_idx - 1]))
            if len(prev_spots) >= 1:
                wb_start_idx -= 1
            else:
                break
        # 从词库开始行到末尾收集所有条目
        for i in range(wb_start_idx, len(lines)):
            for m in re.finditer(r'\b([A-O0])[\)\.]\s*(\S+)', lines[i]):
                letter = m.group(1)
                if letter == '0':
                    letter = 'O'
                if letter in 'ABCDEFGHIJKLMNO':
                    wb_entries_raw.append((letter, m.group(2)))
        # 去重（同一字母保留第一次）
        seen = set()
        wb_entries = []
        for l, w in wb_entries_raw:
            if l not in seen:
                seen.add(l)
                wb_entries.append((l, w))
        wb_start = body_text.find(lines[wb_start_idx])
        passage_text = _clean(body_text[:wb_start])
        word_bank_words = dict(wb_entries)
    else:
        passage_text = _clean(body_text)
        word_bank_words = {}

    # 去掉 passage 中残留的 "Questions X to Y are based on..." 头部
    passage_text = re.sub(
        r'Questions?\s*\d+\s*(?:to|and)\s*\d+\s*are\s*based\s*(?:on|upon)\s*(?:the\s*following\s*)?passage\.?\s*',
        '', passage_text, flags=re.IGNORECASE
    ).strip()

    # 在短文中找数字标记 26-35
    number_positions = []
    for num in range(26, 36):
        for m in re.finditer(r'(?:^|\s|[\(\[\.。，,;:!?—])' + str(num) + r'(?:\s|$|[\)\]\.。，,;:!?—])', passage_text):
            number_positions.append((num, m.start() + len(m.group(0)) - len(str(num))))
            break

    number_positions.sort(key=lambda x: x[1])

    # 构建选项（词库）
    word_bank_options = [{"label": k, "text": v} for k, v in sorted(word_bank_words.items())]

    # 选项不足14个则跳过整个Section A（识别不完整，不展示）
    if len(word_bank_options) < 14:
        return questions

    # 为每个空创建题目
    for i, (num, pos) in enumerate(number_positions):
        # 截取上下文：前后各200字符
        ctx_start = max(0, pos - 200)
        ctx_end = min(len(passage_text), pos + 200)
        context = passage_text[ctx_start:ctx_end].strip()
        # 标记空位
        context = context.replace(str(num), f"__({num})__", 1)

        questions.append(ParsedQuestion(
            question_number=num,
            content=f"[原文]\n{passage_text[:2000]}\n\n[选词填空 第{num}空]\n{context}",
            type="阅读",
            section=f"Reading {sec_label}",
            options=word_bank_options[:15],
            difficulty=2,
            score=3.55,
            passage_text=passage_text[:3000],
            source=source,
        ))

    return questions


def _parse_reading_section_b(sec_text, sec_label, source):
    """段落匹配：一篇长文(A-L段落) + 10条匹配语句(36-45)"""
    questions = []

    # 跳过 Directions 部分：尝试多种可能的结束标记
    dir_end_match = re.search(
        r'mark\s+the\s+corresponding\s+letter\s+on\s+Answer\s+Sheet',
        sec_text, re.IGNORECASE
    )
    if dir_end_match:
        body_start = dir_end_match.end()
        # 跳过直到第一个字母段落标记
        first_para = re.search(r'(?:^|\n)\s*([A-L])[\.、]\s+', sec_text[body_start:])
        if first_para:
            body_start = body_start + first_para.start()
    else:
        # 回退：找第一个字母段落标记 A.
        first_para = re.search(r'(?:^|\n)\s*([A-L])[\.、]\s+', sec_text)
        body_start = first_para.start() if first_para else 0
    body_text = sec_text[body_start:]

    # 找到匹配语句开始位置：第一个 "36."
    q_start = None
    m36 = re.search(r'(?:^|\n)\s*36[\.、]', body_text)
    if m36:
        q_start = m36.start()
        passage_raw = body_text[:q_start]
        statements_text = body_text[q_start:]
    else:
        # 回退：找字母段落标记
        para_marker = re.search(r'(?:^|\n)\s*([A-L])[\.、]\s+', body_text)
        if para_marker:
            passage_raw = body_text[para_marker.start():]
        else:
            passage_raw = body_text
        statements_text = ""

    # 保持段落换行：在每个字母标记前加换行
    passage_raw = re.sub(r'(?:^|\n)\s*([A-L])[\.、]\s+', r'\n\1. ', passage_raw)
    passage_text = _norm(passage_raw)
    # 去掉 Directions 说明文字（Section B / Directions: / Answer Sheet 等行）
    passage_text = re.sub(r'^Section\s+[A-C]\s*', '', passage_text, flags=re.IGNORECASE)
    passage_text = re.sub(r'Directions?:[\s\S]*?(?=Answer\s*Sheet)', '', passage_text, flags=re.IGNORECASE)
    passage_text = re.sub(r'Answer\s*Sheet\s*\d+[^.]*\.\s*', '', passage_text, flags=re.IGNORECASE)
    passage_text = _norm(passage_text)

    # 提取36-45题（匹配语句，无选项）
    stmt_nums = []
    for m in re.finditer(r'(?:^|\n)\s*(\d{2})[\.、]\s*', statements_text):
        num = int(m.group(1))
        if 36 <= num <= 45:
            stmt_nums.append((num, m.start(), m.end()))

    for i, (num, st, en) in enumerate(stmt_nums):
        next_st = stmt_nums[i + 1][1] if i + 1 < len(stmt_nums) else len(statements_text)
        stmt_text = _clean(statements_text[en:next_st])

        if stmt_text:
            questions.append(ParsedQuestion(
                question_number=num,
                content=stmt_text,
                type="阅读",
                section=f"Reading {sec_label}",
                options=[],
                difficulty=2,
                score=7.1,
                passage_text=passage_text[:4000],
                source=source,
            ))

    return questions


def _parse_reading_section_c(sec_text, sec_label, source):
    """仔细阅读：2篇短文，每篇5道选择题(46-55)"""
    questions = []

    # 按 Passage 标记拆分
    pass_pattern = re.compile(r'(Passage\s*(?:One|Two|1|2))', re.IGNORECASE)
    pass_matches = list(pass_pattern.finditer(sec_text))

    if not pass_matches:
        # 只有一个Passage，或没有标记
        passage_parts = [("Passage", sec_text)]
    else:
        passage_parts = []
        for i, pm in enumerate(pass_matches):
            label = pm.group(1).strip()
            start = pm.end()
            end = pass_matches[i + 1].start() if i + 1 < len(pass_matches) else len(sec_text)
            passage_parts.append((label, sec_text[start:end]))

    for passage_label, passage_content in passage_parts:
        # 分离原文和题目
        # 格式: "Questions 46 to 50 are based on the following passage.\n[原文]\n46. stem..."
        q_marker = re.search(
            r'Questions?\s*\d+\s*(?:to|and)\s*\d+\s*are\s*based\s*(?:on|upon)\s*(?:the\s*following\s*)?passage[^.]*\.?',
            passage_content, re.IGNORECASE
        )

        passage_text = ""
        questions_text = passage_content

        if q_marker:
            after_marker = passage_content[q_marker.end():]
            # 找到第一个题号（46-55），题号之前就是原文
            first_q = re.search(r'(?:^|\n)\s*(?:4[6-9]|5[0-5])[\.、]', after_marker)
            if first_q:
                passage_text = _clean(after_marker[:first_q.start()])
                questions_text = after_marker[first_q.start():]
            else:
                questions_text = after_marker
        else:
            # 没有 marker，尝试用第一个46-55题号分割
            first_q = re.search(r'(?:^|\n)\s*(?:4[6-9]|5[0-5])[\.、]', passage_content)
            if first_q:
                before_q = passage_content[:first_q.start()]
                # 跳过 Directions
                dir_end = re.search(r'Directions?:', before_q, re.IGNORECASE)
                if dir_end:
                    dir_text = before_q[dir_end.end():]
                    # 取 Directions 之后到第一个题目之间的内容作为原文
                    # 但要跳过 "mark the corresponding letter..." 等说明
                    passage_text = _clean(dir_text)
                else:
                    passage_text = _clean(before_q)
                questions_text = passage_content[first_q.start():]
            else:
                passage_text = _clean(passage_content)
                questions_text = ""

        full_section = f"Reading {sec_label} {passage_label}"

        # 提取题目（46-55，带选项），把 passage 也传进去
        qs = _extract_reading_questions(questions_text, full_section, source, passage_text)
        for q in qs:
            # Section C 标准为4个选项，不足则丢弃
            if len(q.options) < 4:
                continue
            if passage_text:
                q.passage_text = passage_text[:3000]
                # 将原文也加入题干内容
                q.content = f"[原文]\n{passage_text[:2000]}\n\n[题目]\n{q.content}"
            questions.append(q)

    return questions


def _extract_reading_questions(text, section, source, passage_text=""):
    """提取仔细阅读的题目（有题干 + 选项的格式）"""
    questions = []
    text = _norm(text)

    # 匹配 "46. stem text A) ... B) ... C) ... D) ..."
    q_pattern = re.compile(r'(?:^|\n)\s*(\d{1,3})[\.、]\s+')
    matches = list(q_pattern.finditer(text))

    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _norm(text[start:end])

        options, stem = _extract_options(body)

        if not stem and options:
            # 无题干但有选项（罕见）
            stem = f"[第{num}题]"

        if not stem or len(stem) < 3:
            # 尝试用选项的第1字母之前的全部内容作为题干
            first_opt = re.search(r'\bA[\.\)]', _clean(body))
            if first_opt:
                stem = _clean(body)[:first_opt.start()]
                options, _ = _extract_options(_clean(body))

        if not stem or len(stem) < 3:
            continue

        questions.append(ParsedQuestion(
            question_number=num,
            content=stem,
            type="阅读",
            section=section,
            options=options,
            difficulty=2,
            score=_default_score("阅读", section),
            source=source,
        ))

    return questions


# ═══════════════════════════════════════════════════════════════════════════════
# Translation 解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_translation(part_text, source=""):
    content = _clean_artifacts(_clean(part_text))

    # 去掉 Directions 之前的标题行 (Part IV Translation 等)
    dir_match = re.search(r'Directions:', content, re.IGNORECASE)
    if dir_match:
        # 保留 Directions: 之后的内容，但去掉 Directions: 本身
        content = content[dir_match.end():]

    return [ParsedQuestion(
        question_number=1,
        content=content,
        type="翻译",
        section="Translation",
        difficulty=2,
        score=106.5,
        source=source,
    )]


# ═══════════════════════════════════════════════════════════════════════════════
# 通用拆分工具
# ═══════════════════════════════════════════════════════════════════════════════

def _split_by_sections(text):
    """按 Section A/B/C 拆分文本"""
    pattern = re.compile(r'(Section\s+[A-C])\b', re.IGNORECASE)
    positions = list(pattern.finditer(text))

    if not positions:
        return []

    sections = []
    for i, m in enumerate(positions):
        label = m.group(1).strip()
        start = m.start()
        end = positions[i + 1].start() if i + 1 < len(positions) else len(text)
        sections.append((label, text[start:end]))

    return sections


def _split_question_groups(text):
    """按 'Questions X to Y are based on...' 拆分题组"""
    pattern = re.compile(
        r'(Questions?\s*\d+\s*(?:to|and)\s*\d+\s*are\s*based\s*(?:on|upon)[^.]*\.?)',
        re.IGNORECASE
    )
    positions = list(pattern.finditer(text))

    if not positions:
        return [("", text)]

    groups = []
    for i, m in enumerate(positions):
        header = m.group(1).strip()
        start = m.end()
        end = positions[i + 1].start() if i + 1 < len(positions) else len(text)
        groups.append((header, text[start:end]))

    return groups


def _default_score(qtype, section=""):
    """根据题型估算分值（CET-4 满分710分）"""
    if qtype == "写作":
        return 106.5
    if qtype == "翻译":
        return 106.5
    if qtype == "听力":
        # 听力25题共248.5分，7.1/题起但Section C每题14.2
        return 9.9
    if qtype == "阅读":
        if "Section A" in section:
            return 3.55
        if "Section B" in section:
            return 7.1
        if "Section C" in section:
            return 14.2
        return 7.1
    return 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════════

def parse_cet4_exam(pdf_path, source=""):
    """解析整张 CET-4 试卷 PDF，返回 ParsedQuestion 列表"""
    full_text = extract_text_from_pdf(pdf_path)
    if not full_text:
        return []

    if not source:
        import os
        source = os.path.basename(pdf_path)

    parts = split_by_parts(full_text)
    all_questions = []

    parsers = {
        "写作": parse_writing,
        "听力": parse_listening,
        "阅读": parse_reading,
        "翻译": parse_translation,
    }

    for qtype, part_text in parts.items():
        parser = parsers.get(qtype)
        if parser:
            qs = parser(part_text, source=source)
            all_questions.extend(qs)

    # 统一题号：写作=1，听力/阅读=原号+1，翻译=57
    for q in all_questions:
        if q.type == "写作":
            q.question_number = 1
        elif q.type == "翻译":
            q.question_number = 57
        else:
            # 听力和阅读：原题号 + 1
            q.question_number = q.question_number + 1

    return all_questions


def parse_cet4_pdf(pdf_path):
    """兼容旧接口：返回 (questions_dict_list, full_text)"""
    parsed = parse_cet4_exam(pdf_path)
    full_text = extract_text_from_pdf(pdf_path)

    questions = []
    for pq in parsed:
        questions.append({
            "content": pq.content,
            "type": pq.type,
            "difficulty": pq.difficulty,
            "answer": pq.answer,
            "analysis": pq.analysis,
            "knowledge_id": pq.knowledge_id,
            "score": int(pq.score),
            "options": json.dumps(pq.options, ensure_ascii=False) if pq.options else None,
            "question_number": pq.question_number,
            "section": pq.section,
            "source": pq.source,
            "passage_text": pq.passage_text or None,
        })

    return questions, full_text


if __name__ == "__main__":
    import os, sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # 默认取第一个PDF测试
        pdf_dir = "pdf_upload"
        files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        if not files:
            print("没有找到PDF文件")
            sys.exit(1)
        pdf_path = os.path.join(pdf_dir, files[0])

    result = parse_cet4_exam(pdf_path)
    print(f"解析完成，共 {len(result)} 道题目\n")

    # 按 section 分组输出
    sections = {}
    for q in result:
        sec = q.section or "未知"
        sections.setdefault(sec, []).append(q)

    for sec, qs in sections.items():
        print(f"{'='*60}")
        print(f"【{sec}】共 {len(qs)} 题")
        print(f"{'='*60}")
        for q in qs:
            print(f"\n  #{q.question_number} (score={q.score})")
            print(f"  Stem: {q.content[:150]}...")
            if q.options:
                opt_str = " | ".join(f"{o['label']}) {o['text'][:50]}" for o in q.options[:6])
                print(f"  Options: {opt_str}")
            if q.passage_text:
                print(f"  Passage: {q.passage_text[:100]}...")
