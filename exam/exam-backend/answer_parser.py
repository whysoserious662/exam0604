"""
解析 PDF 解析器 — 从 CET-4 解析 PDF 中提取答案和解析内容
支持2022新版格式 + 2015-2017旧版格式 + OCR文本
"""
import re
import pdfplumber


def extract_text_from_pdf(pdf_path):
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
    except Exception:
        return ""
    return full_text


def _clean(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()


PAREN = r'[\)）]'
LBRA = r'[\[【]'
RBRA = r'[\]】]'


def _extract_analysis(text, pos, end_pos, max_len=400):
    """提取pos到end_pos之间的文字作为解析"""
    raw = text[pos:end_pos]
    # 清理噪声
    raw = re.sub(r'【听前预测】.*?(?=【|$)', '', raw, flags=re.DOTALL)
    raw = re.sub(r'【做题提示】.*?(?=【|$)', '', raw, flags=re.DOTALL)
    raw = re.sub(r'定位[：:].*?(?=解析[：:]|【|$)', '', raw, flags=re.DOTALL)
    return _clean(raw)[:max_len]


# ═══════════════════════════════════════════════════════════════════
# 新版格式解析（2022+）
# ═══════════════════════════════════════════════════════════════════

def parse_listening_answers(text):
    lc = re.search(r'Part\s+\S*\s*Listening\s+Comprehension', text, re.IGNORECASE)
    if not lc: return []
    end = re.search(r'Part\s+\S*\s*Reading\s+Comprehension', text[lc.start():], re.IGNORECASE)
    lt = text[lc.start():lc.start() + end.start()] if end else text[lc.start():]
    blocks = re.split(r'答案详解', lt)
    all_answers = []; qnum = 1
    jx_pat = re.compile(r'([A-D])\s*' + PAREN + r'\s*' + LBRA + r'精析' + RBRA)
    da_pat = re.compile(r'(?:答案|因此)[，,]?\s*为\s*([A-D])\s*' + PAREN, re.DOTALL)

    for block in blocks[1:]:
        jx_matches = list(jx_pat.finditer(block))
        da_matches = list(da_pat.finditer(block))
        if not jx_matches: continue
        da_letters = [m.group(1) for m in da_matches]
        expected = len(jx_matches)
        if len(da_letters) == expected: final_letters = da_letters
        elif len(da_letters) > 0:
            final_letters = [m.group(1) for m in jx_matches]
            di = len(da_letters) - 1
            for i in range(len(final_letters) - 1, -1, -1):
                if di >= 0: final_letters[i] = da_letters[di]; di -= 1
        else: final_letters = [m.group(1) for m in jx_matches]

        for letter in final_letters:
            matched = None
            for m in jx_matches:
                if m.group(1) == letter: matched = m; break
            if not matched: matched = jx_matches[0]
            pos = matched.end()
            after = block[pos:]
            boundaries = []
            dm = re.search(r'(?:答案|因此)[，,]?\s*为\s*[A-D]\s*' + PAREN, after)
            if dm: boundaries.append(dm.end())
            nm = re.search(r'[A-D]\s*' + PAREN + r'\s*' + LBRA + r'精析' + RBRA, after)
            if nm: boundaries.append(nm.start())
            end_pos = min(boundaries) if boundaries else min(len(after), 300)
            analysis = _clean(after[:end_pos])[:400]
            all_answers.append({"question_number": qnum, "answer": letter, "analysis": analysis, "type": "听力"})
            qnum += 1
            if qnum > 25: break
        if qnum > 25: break
    return all_answers


def parse_reading_section_a_answers(text):
    answers = []
    rc = re.search(r'Part\s+\S*\s*Reading\s+Comprehension', text, re.IGNORECASE)
    if not rc: return answers
    sa = re.search(r'Section\s+A\b', text[rc.start():], re.IGNORECASE)
    if not sa: return answers
    sa_start = rc.start() + sa.start()
    sb = re.search(r'Section\s+B\b', text[sa_start:], re.IGNORECASE)
    section_text = text[sa_start:sa_start + sb.start()] if sb else text[sa_start:]
    q_pat = re.compile(r'(\d{2})\s*[\.、\s]+' + LBRA + r'考点' + RBRA)
    ans_pat = re.compile(r'由此确定答案为\s*([A-O])\s*' + PAREN)
    q_positions = [(int(m.group(1)), m.start()) for m in q_pat.finditer(section_text)]
    a_positions = [(m.group(1), m.start()) for m in ans_pat.finditer(section_text)]
    a_idx = 0
    for qnum, qpos in q_positions:
        while a_idx < len(a_positions) and a_positions[a_idx][1] < qpos: a_idx += 1
        if a_idx < len(a_positions):
            answer = a_positions[a_idx][0]
            sem = re.search(LBRA + r'语义判断' + RBRA + r'\s*(.*?)(?:由此确定答案为|$)', section_text[qpos:a_positions[a_idx][1]], re.DOTALL)
            analysis = _clean(sem.group(1))[:400] if sem else ""
            answers.append({"question_number": qnum, "answer": answer, "analysis": analysis, "type": "阅读"})
            a_idx += 1
    return answers


def parse_reading_section_b_answers(text):
    answers = []
    rc = re.search(r'Part\s+\S*\s*Reading\s+Comprehension', text, re.IGNORECASE)
    if not rc: return answers
    sb = re.search(r'Section\s+B\b', text[rc.start():], re.IGNORECASE)
    if not sb: return answers
    sb_start = rc.start() + sb.start()
    sc = re.search(r'Section\s+C\b', text[sb_start:], re.IGNORECASE)
    section_text = text[sb_start:sb_start + sc.start()] if sc else text[sb_start:]
    q_pat = re.compile(r'(\d{2})\s*[\.、\s]+' + LBRA + r'定位' + RBRA)
    jx_pat = re.compile(r'([A-L])\s*' + PAREN + r'\s*' + LBRA + r'精析' + RBRA)
    fb_pat = re.compile(r'故答案为\s*([A-L])\s*' + PAREN)
    q_positions = [(int(m.group(1)), m.start()) for m in q_pat.finditer(section_text)]
    a_positions = [(m.group(1), m.start()) for m in jx_pat.finditer(section_text)]
    fb_positions = [(m.group(1), m.start()) for m in fb_pat.finditer(section_text)]
    all_a = sorted(a_positions + fb_positions, key=lambda x: x[1])
    a_idx = 0
    for qnum, qpos in q_positions:
        while a_idx < len(all_a) and all_a[a_idx][1] < qpos: a_idx += 1
        if a_idx < len(all_a):
            answer = all_a[a_idx][0]; apos = all_a[a_idx][1]
            after = section_text[apos:apos + 800]
            jm = jx_pat.search(after)
            if jm:
                ana_after = after[jm.end():]
                bounds = [];
                for p in [r'\d{2}\s*[\.、\s]+'+LBRA+r'(?:定位|考点)'+RBRA, r'【文章来源】', r'参考译文', r'Section\s+C']:
                    m = re.search(p, ana_after);
                    if m: bounds.append(m.start())
                end_pos = min(bounds) if bounds else min(len(ana_after), 400)
                analysis = _clean(ana_after[:end_pos])[:400]
            else: analysis = ""
            answers.append({"question_number": qnum, "answer": answer, "analysis": analysis, "type": "阅读"})
            a_idx += 1
    return answers


def parse_reading_section_c_answers(text):
    answers = []
    rc = re.search(r'Part\s+\S*\s*Reading\s+Comprehension', text, re.IGNORECASE)
    if not rc: return answers
    sc = re.search(r'Section\s+C\b', text[rc.start():], re.IGNORECASE)
    if not sc: return answers
    sc_start = rc.start() + sc.start()
    trans = re.search(r'Part\s+\S*\s*Translation', text[sc_start:], re.IGNORECASE)
    section_text = text[sc_start:sc_start + trans.start()] if trans else text[sc_start:]
    q_pat = re.compile(r'(\d{2})\s*[\.、\s]+' + LBRA + r'定位' + RBRA)
    jx_pat = re.compile(r'([A-D])\s*' + PAREN + r'\s*' + LBRA + r'精析' + RBRA)
    fb_pat = re.compile(r'故正确答案为\s*([A-D])\s*' + PAREN)
    q_positions = [(int(m.group(1)), m.start()) for m in q_pat.finditer(section_text)]
    a_positions = [(m.group(1), m.start()) for m in jx_pat.finditer(section_text)]
    fb_positions = [(m.group(1), m.start()) for m in fb_pat.finditer(section_text)]
    all_a = sorted(a_positions + fb_positions, key=lambda x: x[1])
    a_idx = 0
    for qnum, qpos in q_positions:
        while a_idx < len(all_a) and all_a[a_idx][1] < qpos: a_idx += 1
        if a_idx < len(all_a):
            answer = all_a[a_idx][0]; apos = all_a[a_idx][1]
            after = section_text[apos:apos + 800]
            jm = jx_pat.search(after)
            if jm:
                ana_after = after[jm.end():]
                bounds = [];
                for p in [r'\d{2}\s*[\.、\s]+'+LBRA+r'定位'+RBRA, r'【避错】', r'参考译文', r'Passage', r'Part\s']:
                    m = re.search(p, ana_after);
                    if m: bounds.append(m.start())
                end_pos = min(bounds) if bounds else min(len(ana_after), 400)
                analysis = _clean(ana_after[:end_pos])[:400]
            else: analysis = ""
            answers.append({"question_number": qnum, "answer": answer, "analysis": analysis, "type": "阅读"})
            a_idx += 1
    return answers


# ═══════════════════════════════════════════════════════════════════
# 旧版格式解析（2015-2017）
# ═══════════════════════════════════════════════════════════════════

def parse_old_listening(text):
    answers = []
    lc = re.search(r'Part\s*I\s*\n?\s*Listening\s+Comprehension|Part\s*\S*\s*Listening\s+Comprehen', text, re.IGNORECASE)
    if not lc: return answers
    end = re.search(r'Part\s*\S*\s*Reading\s+Comprehen|Part\s*III', text[lc.start():], re.IGNORECASE)
    lt = text[lc.start():lc.start() + end.start()] if end else text[lc.start():]
    pat = re.compile(r'(?:^|\n)\s*(\d{1,2})\.\s*([A-D])\s*\n')
    matches = list(pat.finditer(lt))
    for i, m in enumerate(matches):
        qnum = int(m.group(1)); letter = m.group(2)
        if not (1 <= qnum <= 25 and letter in 'ABCD'): continue
        next_p = matches[i+1].start() if i+1 < len(matches) else len(lt)
        analysis = _extract_analysis(lt, m.end(), next_p)
        answers.append({"question_number": qnum, "answer": letter, "analysis": analysis, "type": "听力"})
    seen = set(); unique = []
    for a in answers:
        if a["question_number"] not in seen: seen.add(a["question_number"]); unique.append(a)
    return unique


def parse_old_reading_sa(text):
    answers = []
    rc = re.search(r'Part\s*\S*\s*Reading\s+Comprehen', text, re.IGNORECASE)
    if not rc: return answers
    sa = re.search(r'Section\s*A\b', text[rc.start():], re.IGNORECASE)
    if not sa: return answers
    sa_start = rc.start() + sa.start()
    sb = re.search(r'Section\s*B\b', text[sa_start:], re.IGNORECASE)
    st = text[sa_start:sa_start + sb.start()] if sb else text[sa_start:]
    pat = re.compile(r'(?:^|\n)\s*(\d{2})\.\s*([A-O])\s*\)')
    matches = list(pat.finditer(st))
    for i, m in enumerate(matches):
        qnum = int(m.group(1))
        if not (26 <= qnum <= 35): continue
        next_p = matches[i+1].start() if i+1 < len(matches) else len(st)
        analysis = _extract_analysis(st, m.end(), next_p)
        # prefer 语义判断 content
        sem = re.search(r'【语义判断】\s*(.*?)(?:【|$)', st[m.end():next_p], re.DOTALL)
        if sem: analysis = _clean(sem.group(1))[:400]
        answers.append({"question_number": qnum, "answer": m.group(2), "analysis": analysis, "type": "阅读"})
    return answers


def parse_old_reading_sb(text):
    answers = []
    rc = re.search(r'Part\s*\S*\s*Reading\s+Comprehen', text, re.IGNORECASE)
    if not rc: return answers
    sb = re.search(r'Section\s*B\b', text[rc.start():], re.IGNORECASE)
    if not sb: return answers
    sb_start = rc.start() + sb.start()
    sc = re.search(r'Section\s*C\b', text[sb_start:], re.IGNORECASE)
    st = text[sb_start:sb_start + sc.start()] if sc else text[sb_start:]
    pat = re.compile(r'(?:^|\n)\s*(\d{2})\s*[\.、]\s*([A-O])\s*\n')
    matches = list(pat.finditer(st))
    for i, m in enumerate(matches):
        qnum = int(m.group(1))
        if not (36 <= qnum <= 45): continue
        next_p = matches[i+1].start() if i+1 < len(matches) else len(st)
        raw = st[m.end():next_p]
        jx = re.search(r'解析[：:]\s*(.*)', raw, re.DOTALL)
        analysis = _clean(jx.group(1))[:400] if jx else _clean(raw)[:300]
        answers.append({"question_number": qnum, "answer": m.group(2), "analysis": analysis, "type": "阅读"})
    return answers


def parse_old_reading_sc(text):
    answers = []
    rc = re.search(r'Part\s*\S*\s*Reading\s+Comprehen', text, re.IGNORECASE)
    if not rc: return answers
    sc = re.search(r'Section\s*C\b', text[rc.start():], re.IGNORECASE)
    if not sc: return answers
    sc_start = rc.start() + sc.start()
    end = re.search(r'Part\s*IV|Part\s*\S*\s*Translation', text[sc_start:], re.IGNORECASE)
    st = text[sc_start:sc_start + end.start()] if end else text[sc_start:]
    pat = re.compile(r'(?:^|\n)\s*(\d{2})\s*[\.、]\s*([A-D])\s*\n')
    matches = list(pat.finditer(st))
    for i, m in enumerate(matches):
        qnum = int(m.group(1))
        if not (46 <= qnum <= 55): continue
        next_p = matches[i+1].start() if i+1 < len(matches) else len(st)
        raw = st[m.end():next_p]
        raw = re.sub(r'定位[：:].*?(?=解析[：:]|【|$)', '', raw, flags=re.DOTALL)
        jx = re.search(r'解析[：:]\s*(.*)', raw, re.DOTALL)
        analysis = _clean(jx.group(1))[:400] if jx else _clean(raw)[:300]
        answers.append({"question_number": qnum, "answer": m.group(2), "analysis": analysis, "type": "阅读"})
    return answers


def parse_old_format(text):
    all_answers = []
    all_answers.extend(parse_old_listening(text))
    all_answers.extend(parse_old_reading_sa(text))
    all_answers.extend(parse_old_reading_sb(text))
    all_answers.extend(parse_old_reading_sc(text))
    seen = set(); unique = []
    for a in all_answers:
        if a["question_number"] not in seen: seen.add(a["question_number"]); unique.append(a)
    return unique


# ═══════════════════════════════════════════════════════════════════
# OCR 专用解析
# ═══════════════════════════════════════════════════════════════════

OCR_DIGIT_MAP = {'0': 'D', '1': 'A', '8': 'B'}

def _ocr_correct(letter):
    if not letter: return letter
    return OCR_DIGIT_MAP.get(letter.upper(), letter.upper())


def parse_ocr_listening_answers(text):
    answers = []; qnum = 1
    blocks = re.split(r'答案\s*详\s*解', text)
    jx_pat = re.compile(r'([A-D])\s*' + PAREN + r'\s*' + LBRA + r'精析' + RBRA)
    da_pat = re.compile(r'(?:答案|因此)[，,]?\s*为\s*([A-D])\s*' + PAREN, re.DOTALL)
    for block in blocks[1:]:
        jx_matches = list(jx_pat.finditer(block))
        da_matches = list(da_pat.finditer(block))
        if not jx_matches: continue
        da_letters = [m.group(1) for m in da_matches]
        expected = len(jx_matches)
        if len(da_letters) == expected: final_letters = da_letters
        elif len(da_letters) > 0:
            final_letters = [m.group(1) for m in jx_matches]
            di = len(da_letters) - 1
            for i in range(len(final_letters) - 1, -1, -1):
                if di >= 0: final_letters[i] = da_letters[di]; di -= 1
        else: final_letters = [m.group(1) for m in jx_matches]
        for letter in final_letters:
            matched = None
            for m in jx_matches:
                if m.group(1) == letter: matched = m; break
            if not matched: matched = jx_matches[0]
            pos = matched.end(); after = block[pos:]
            boundaries = []
            dm = re.search(r'(?:答案|因此)[，,]?\s*为\s*[A-D]\s*' + PAREN, after)
            if dm: boundaries.append(dm.end())
            end_pos = min(boundaries) if boundaries else min(len(after), 200)
            analysis = _clean(after[:end_pos])[:300]
            answers.append({"question_number": qnum, "answer": letter, "analysis": analysis, "type": "听力"})
            qnum += 1
            if qnum > 25: break
        if qnum > 25: break
    return answers


def parse_ocr_reading_answers(text):
    answers = []
    da_simple = re.compile(r'故\s*答案\s*为\s*([A-O0-9])\s*[。.]')
    q_positions = [(int(m.group(1)), m.start()) for m in re.finditer(r'(?:^|\n)\s*(\d{2})\s*[\.、]', text)]
    a_positions = [(m.group(1), m.start()) for m in da_simple.finditer(text)]
    a_idx = 0
    for qnum, qpos in q_positions:
        if qnum < 36 or qnum > 55: continue
        while a_idx < len(a_positions) and a_positions[a_idx][1] < qpos: a_idx += 1
        if a_idx < len(a_positions):
            letter = _ocr_correct(a_positions[a_idx][0])
            if letter in 'ABCDEFGHIJKLMNO':
                answers.append({"question_number": qnum, "answer": letter, "analysis": "", "type": "阅读"})
                a_idx += 1
    seen = set(); unique = []
    for a in answers:
        if a["question_number"] not in seen: seen.add(a["question_number"]); unique.append(a)
    return unique


def parse_ocr_text(ocr_text):
    all_answers = []
    all_answers.extend(parse_ocr_listening_answers(ocr_text))
    all_answers.extend(parse_ocr_reading_answers(ocr_text))
    all_answers.extend(parse_reading_section_a_answers(ocr_text))
    all_answers.extend(parse_reading_section_b_answers(ocr_text))
    all_answers.extend(parse_reading_section_c_answers(ocr_text))
    seen = set(); unique = []
    for a in all_answers:
        if a["question_number"] not in seen: seen.add(a["question_number"]); unique.append(a)
    return unique


# ═══════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════

def parse_answer_pdf(pdf_path):
    full_text = extract_text_from_pdf(pdf_path)
    if not full_text or len(full_text.strip()) < 100:
        return [], "", False

    all_answers = []
    # 新版格式
    all_answers.extend(parse_listening_answers(full_text))
    all_answers.extend(parse_reading_section_a_answers(full_text))
    all_answers.extend(parse_reading_section_b_answers(full_text))
    all_answers.extend(parse_reading_section_c_answers(full_text))

    # 旧版格式（如果新版没找到足够答案）
    if len(all_answers) < 10:
        all_answers.extend(parse_old_format(full_text))

    seen = set()
    unique = []
    for a in all_answers:
        if a["question_number"] not in seen:
            seen.add(a["question_number"])
            unique.append(a)

    return unique, full_text, True
