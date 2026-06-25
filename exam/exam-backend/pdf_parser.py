"""
pdf_parser.py
解析四六级/标准考试 PDF，提取题目列表。
支持题型：选择题(choice)、填空题(fill)、大题/作文(essay)
"""

import re
import pdfplumber
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Question:
    id: int
    type: str           # "choice" | "fill" | "essay"
    part: str           # e.g. "Part I", "Part II"
    section: str        # e.g. "Writing", "Listening Comprehension"
    difficulty: str     # "easy" | "medium" | "hard"
    content: str
    options: list[str] = field(default_factory=list)   # A/B/C/D for choice
    score: float = 0.0

    def to_dict(self):
        return asdict(self)


# ── 难度推断规则（可根据实际题库调整）──────────────────────────────────────
DIFFICULTY_RULES = {
    "Writing": "hard",
    "Reading Comprehension": "hard",
    "Translation": "hard",
    "Listening Comprehension": "medium",
    "Section A": "easy",
    "Section B": "medium",
    "Section C": "hard",
}

def infer_difficulty(section: str, part: str) -> str:
    for key, diff in DIFFICULTY_RULES.items():
        if key.lower() in section.lower() or key.lower() in part.lower():
            return diff
    return "medium"


# ── 题型推断 ────────────────────────────────────────────────────────────────
def infer_type(section: str, has_options: bool) -> str:
    essay_keywords = ["writing", "translation", "essay", "作文", "翻译"]
    fill_keywords  = ["blank", "填空", "cloze", "完形"]
    if any(k in section.lower() for k in essay_keywords):
        return "essay"
    if any(k in section.lower() for k in fill_keywords):
        return "fill"
    if has_options:
        return "choice"
    return "fill"


# ── 核心解析器 ──────────────────────────────────────────────────────────────
class CETParser:
    """解析四六级风格试卷 PDF"""

    # 匹配 Part I / Part II / Part III ...
    RE_PART    = re.compile(r'^Part\s+(I{1,3}V?|[IVX]+)\b', re.IGNORECASE)
    # 匹配 Section A / B / C
    RE_SECTION = re.compile(r'^Section\s+([A-Z])\b', re.IGNORECASE)
    # 匹配题目编号：行首的数字+点/括号，如 "1." "12." "1）"
    RE_QNUM    = re.compile(r'^\s*(\d{1,3})[\.、）\)]\s+(.+)')
    # 匹配选项行：A. / B. / C. / D. 或 A) B) ...
    RE_OPTION  = re.compile(r'\b([A-D])[\.、）\)]\s*(.+)')
    # 匹配 Directions 行（跳过）
    RE_DIR     = re.compile(r'^Directions?:', re.IGNORECASE)

    def parse(self, pdf_path: str) -> list[Question]:
        questions: list[Question] = []
        current_part    = "Part I"
        current_section = ""
        pending_q: Optional[dict] = None   # 暂存尚未入库的题目

        with pdfplumber.open(pdf_path) as pdf:
            lines = []
            for page in pdf.pages:
                text = page.extract_text(layout=False) or ""
                lines.extend(text.split("\n"))

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            # ── Part 标题 ───────────────────────────────────────────────────
            if self.RE_PART.match(line):
                if pending_q:
                    questions.append(self._build(pending_q))
                    pending_q = None
                current_part = self._extract_part(line)
                current_section = self._extract_section_from_part_line(line)
                continue

            # ── Section 标题 ─────────────────────────────────────────────────
            if self.RE_SECTION.match(line):
                current_section = line
                continue

            # ── Directions（跳过）────────────────────────────────────────────
            if self.RE_DIR.match(line):
                continue

            # ── 题目编号行 ───────────────────────────────────────────────────
            m = self.RE_QNUM.match(line)
            if m:
                if pending_q:
                    questions.append(self._build(pending_q))
                num, content = int(m.group(1)), m.group(2).strip()
                # 检查当行是否已有内嵌选项（如 "1. A. xxx  B. xxx ..."）
                opts = self._extract_inline_options(content)
                pending_q = {
                    "id": num,
                    "content": content if not opts else self._strip_options(content),
                    "options": opts,
                    "part": current_part,
                    "section": current_section,
                }
                continue

            # ── 选项行（A. B. C. D.）────────────────────────────────────────
            if pending_q and self.RE_OPTION.search(line):
                # 一行可能有多个选项（两列排版）
                options_found = False
                # 尝试匹配多个选项
                for opt_m in re.finditer(r'\b([A-D])[\.）\)]\s*([^A-D]{3,}?)(?=\s+[A-D][\.）\)]|$)', line):
                    pending_q["options"].append(f"{opt_m.group(1)}. {opt_m.group(2).strip()}")
                    options_found = True
                # 若上面没匹配到，尝试匹配单个选项
                if not options_found:
                    single = self.RE_OPTION.search(line)
                    if single:
                        pending_q["options"].append(f"{single.group(1)}. {single.group(2).strip()}")
                continue

            # ── 其他正文行：追加到当前题目内容 ─────────────────────────────
            if pending_q:
                pending_q["content"] += " " + line

        # 别忘最后一题
        if pending_q:
            questions.append(self._build(pending_q))

        return questions

    # ── 辅助方法 ─────────────────────────────────────────────────────────────
    def _build(self, d: dict) -> Question:
        has_opts = bool(d["options"])
        qtype = infer_type(d["section"], has_opts)
        diff  = infer_difficulty(d["section"], d["part"])
        return Question(
            id       = d["id"],
            type     = qtype,
            part     = d["part"],
            section  = d["section"],
            difficulty = diff,
            content  = d["content"].strip(),
            options  = d["options"],
            score    = self._default_score(qtype),
        )

    @staticmethod
    def _default_score(qtype: str) -> float:
        return {"choice": 2.0, "fill": 5.0, "essay": 15.0}.get(qtype, 2.0)

    @staticmethod
    def _extract_part(line: str) -> str:
        m = re.match(r'^(Part\s+\S+)', line, re.IGNORECASE)
        return m.group(1) if m else line.split()[0]

    @staticmethod
    def _extract_section_from_part_line(line: str) -> str:
        # "Part I  Writing  (30 minutes)" → "Writing"
        tokens = line.split()
        if len(tokens) >= 3:
            return " ".join(t for t in tokens[2:] if not t.startswith("("))
        return ""

    @staticmethod
    def _extract_inline_options(text: str) -> list[str]:
        opts = []
        for m in re.finditer(r'\b([A-D])[\.）\)]\s*([^A-D]{3,}?)(?=\s+[A-D][\.）\)]|$)', text):
            opts.append(f"{m.group(1)}. {m.group(2).strip()}")
        return opts

    @staticmethod
    def _strip_options(text: str) -> str:
        return re.sub(r'\s+[A-D][\.）\)]\s+.+', '', text).strip()


def load_questions_from_pdf(pdf_path: str) -> list[Question]:
    """对外暴露的主入口"""
    parser = CETParser()
    return parser.parse(pdf_path)