"""
批量 OCR + DeepSeek 导入扫描版解析PDF
用法: python batch_ocr_import.py
"""
import sys, io, os, json, time, re, warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
import pypdfium2 as pdfium
import easyocr
import requests

API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/v1/chat/completions'
DB_CONFIG = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'exam_system'),
    charset='utf8mb4'
)

# ============================================================
# 待处理列表（所有扫描版解析PDF）
# ============================================================
BASE = r'd:\桌面\专业综合设计\第九周\测试题目\四级真题及答案（2015.6-2025(1).12）'
JOBS = [
    # (pdf_path, year_month, suite_number, matched_exam_source)
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2023年12月CET4真题+解析+听力/02、答案解析/2023.12英语四级真题第1套解析.pdf', '2023.12', 1, '2023.12四级真题第1套【可复制可检索】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2023年12月CET4真题+解析+听力/02、答案解析/2023.12英语四级真题第2套解析.pdf', '2023.12', 2, '2023.12四级真题第2套【可复制可检索】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2023年12月CET4真题+解析+听力/02、答案解析/2023.12英语四级真题第3套解析.pdf', '2023.12', 3, '2023.12四级真题第3套【可复制可检索】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年06月CET4真题+解析+听力/2024年06月CET4/2024年6月四级真题-答案解析/2024年6月四级真题解析【第一套】.pdf', '2024.06', 1, '大学英语四级考试2024年6月真题【第一套】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年06月CET4真题+解析+听力/2024年06月CET4/2024年6月四级真题-答案解析/2024年6月四级真题解析【第二套】.pdf', '2024.06', 2, '大学英语四级考试2024年6月真题【第二套】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年06月CET4真题+解析+听力/2024年06月CET4/2024年6月四级真题-答案解析/2024年6月四级真题解析【第三套】.pdf', '2024.06', 3, '大学英语四级考试2024年6月真题【第三套】.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年12月四级真题+听力+答案/2024.12英语四级解析第1套.pdf', '2024.12', 1, '2024.12四级真题第1套.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年12月四级真题+听力+答案/2024.12英语四级解析第2套.pdf', '2024.12', 2, '2024.12四级真题第2套.pdf'),
    (f'{BASE}/【1】2015-2024年12月四级真题+听力+答案合集/2024年12月四级真题+听力+答案/2024.12英语四级解析第3套.pdf', '2024.12', 3, '2024.12四级真题第3套.pdf'),
    (f'{BASE}/【2】2025年6月四级真题+听力+答案/2025.06英语四级解析第1套.pdf', '2025.06', 1, '2025.06四级真题第1套.pdf'),
    (f'{BASE}/【2】2025年6月四级真题+听力+答案/2025.06英语四级解析第2套.pdf', '2025.06', 2, '2025.06四级真题第2套.pdf'),
    (f'{BASE}/【2】2025年6月四级真题+听力+答案/2025.06英语四级解析第3套.pdf', '2025.06', 3, '2025.06四级真题第3套.pdf'),
    (f'{BASE}/【3】2025年12月四级真题+听力+答案（最新）/2025.12英语四级解析第2套.pdf', '2025.12', 2, '2025.12四级真题第2套.pdf'),
    (f'{BASE}/【3】2025年12月四级真题+听力+答案（最新）/2025.12英语四级解析第3套.pdf', '2025.12', 3, '2025.12四级真题第3套.pdf'),
]


def ocr_pdf_fast(pdf_path, ocr):
    """快速OCR：150 DPI"""
    pdf = pdfium.PdfDocument(pdf_path)
    n_pages = len(pdf)
    full_text = ''
    for i in range(n_pages):
        page = pdf[i]
        bitmap = page.render(scale=150 / 72)
        img = bitmap.to_pil()
        tmp = f'data/batch_ocr_{os.getpid()}_{i}.png'
        os.makedirs('data', exist_ok=True)
        img.save(tmp)
        result = ocr.readtext(tmp, detail=0)
        full_text += '\n'.join(result) + '\n'
        os.remove(tmp)
    pdf.close()
    return full_text, n_pages


def deepseek_extract(ocr_text):
    """调用 DeepSeek 从OCR文字中提取答案"""
    # 分块：每块最多15000字符
    chunks = []
    pos = 0
    while pos < len(ocr_text):
        chunks.append(ocr_text[pos:pos + 15000])
        pos += 14000  # overlap 1000 chars

    all_answers = []
    for ci, chunk in enumerate(chunks[:6]):  # 最多6块
        prompt = f'''从以下四级真题答案解析OCR文字中提取每道题的正确答案。
返回JSON数组：[{{"question_number": 题号, "answer": "答案字母", "type": "听力或阅读"}}]
听力题号1-25，阅读题号26-55。答案只保留字母。没有把握的不要返回。只返回JSON数组。

OCR文字：
{chunk}'''

        try:
            resp = requests.post(API_URL,
                headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}],
                      'max_tokens': 4000, 'temperature': 0},
                timeout=120)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                # 解析 JSON
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    try:
                        chunk_answers = json.loads(json_match.group())
                        all_answers.extend(chunk_answers)
                    except:
                        pass
        except Exception as e:
            print(f'    DeepSeek chunk {ci} error: {e}')

        # 请求间隔
        if ci < len(chunks) - 1:
            time.sleep(1)

    # 去重
    seen = set()
    unique = []
    for a in all_answers:
        key = (a.get('question_number'), a.get('type'))
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def save_to_db(fname, pdf_path, ym, suite, src, ocr_text, answers):
    """保存OCR结果和答案到数据库"""
    db = pymysql.connect(**DB_CONFIG)
    cur = db.cursor()

    # Truncate OCR text to fit (MEDIUMTEXT can hold ~16MB, but keep reasonable)
    safe_text = ocr_text[:100000] if ocr_text else ''
    ans_json = json.dumps(answers, ensure_ascii=False)

    # 更新或插入 answer_sheet（先删后插）
    cur.execute('DELETE FROM answer_sheet WHERE filename=%s', (fname,))
    # 使用无列名 INSERT（列的 VALUES 格式兼容性更好）
    cur.execute('INSERT INTO answer_sheet VALUES (NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())',
        (fname, pdf_path, ym, suite, 1, safe_text, ans_json, src, len(answers)))

    # 清除该来源的旧答案
    cur.execute("UPDATE question SET answer='', analysis='' WHERE source=%s", (src,))

    # 应用新答案（加题型过滤）
    type_map = {'听力': '听力', '阅读': '阅读'}
    count = 0
    for ans in answers:
        qnum = ans.get('question_number')
        answ = ans.get('answer', '')
        ans_type = ans.get('type', '')
        mapped = type_map.get(ans_type)
        if not qnum or not answ or not mapped:
            continue
        cur.execute('UPDATE question SET answer=%s WHERE source=%s AND question_number=%s AND type=%s',
            (answ, src, qnum, mapped))
        count += cur.rowcount

    db.commit()
    db.close()
    return count


# ============================================================
# 主流程
# ============================================================
def main():
    print('=' * 60)
    print('批量 OCR + DeepSeek 答案提取')
    print(f'共 {len(JOBS)} 本PDF待处理')
    print('=' * 60)

    # 初始化 EasyOCR（只加载一次模型）
    print('加载 EasyOCR 模型...')
    ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
    print('模型就绪！\n')

    total_answers = 0
    for idx, (pdf_path, ym, suite, src) in enumerate(JOBS):
        fname = os.path.basename(pdf_path)
        print(f'[{idx+1}/{len(JOBS)}] {fname}')

        # 检查是否已处理
        db = pymysql.connect(**DB_CONFIG)
        cur = db.cursor()
        cur.execute('SELECT match_count FROM answer_sheet WHERE filename=%s AND match_count > 0', (fname,))
        done = cur.fetchone()
        db.close()
        if done:
            print(f'  已处理过 ({done[0]}条答案)，跳过')
            total_answers += done[0]
            continue

        # 1. OCR
        t0 = time.time()
        print(f'  OCR中...', end='', flush=True)
        ocr_text, pages = ocr_pdf_fast(pdf_path, ocr)
        t_ocr = time.time() - t0
        print(f' {pages}页, {len(ocr_text)}字, 耗时{t_ocr:.0f}s')

        # 2. DeepSeek提取
        print(f'  DeepSeek提取...', end='', flush=True)
        t0 = time.time()
        answers = deepseek_extract(ocr_text)
        t_ds = time.time() - t0
        print(f' {len(answers)}条答案, 耗时{t_ds:.0f}s')

        # 3. 保存
        applied = save_to_db(fname, pdf_path, ym, suite, src, ocr_text, answers)
        print(f'  保存: {applied}条已应用到题目')
        total_answers += len(answers)

        # 进度
        print(f'  累计: {total_answers}条答案 | 已耗时: {(idx+1) * (t_ocr + t_ds) / 60:.0f}分钟(估算)')
        print()

    print('=' * 60)
    print(f'全部完成！共提取 {total_answers} 条答案')
    print('=' * 60)


if __name__ == '__main__':
    main()
