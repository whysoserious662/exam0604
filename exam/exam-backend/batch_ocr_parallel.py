"""并行OCR+DeepSeek批量导入扫描版解析PDF（3进程）"""
import sys, os, json, re, time, warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
import pypdfium2 as pdfium
import easyocr
import requests
from multiprocessing import Pool, Manager

API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'exam_system'),
    charset='utf8mb4'
)
BASE = r'd:\桌面\专业综合设计\第十三周\测试题目'


def collect_scanned_pdfs():
    """收集所有未处理的扫描版解析PDF"""
    db = pymysql.connect(**DB)
    cur = db.cursor()
    cur.execute('SELECT filename FROM answer_sheet')
    done = set(r[0] for r in cur.fetchall())
    db.close()

    jobs = []
    for root, dirs, files in os.walk(BASE):
        for f in files:
            if '解析' in f and f.endswith('.pdf') and f not in done:
                # Check if scanned
                try:
                    import pdfplumber
                    with pdfplumber.open(os.path.join(root, f)) as pdf:
                        txt = ''
                        for p in pdf.pages[:3]:
                            t = p.extract_text()
                            if t: txt += t
                    if len(txt.strip()) < 500:  # scanned if < 500 chars
                        jobs.append(os.path.join(root, f))
                except:
                    pass
    return jobs


def process_one(path):
    """处理单个PDF：OCR→DeepSeek→保存"""
    fname = os.path.basename(path)
    try:
        # 1. OCR
        ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        pdf = pdfium.PdfDocument(path)
        text = ''
        for i in range(len(pdf)):
            page = pdf[i]
            bmp = page.render(scale=150/72); img = bmp.to_pil()
            tmp = f'data/ocr_par_{os.getpid()}_{i}.png'
            os.makedirs('data', exist_ok=True); img.save(tmp)
            r = ocr.readtext(tmp, detail=0)
            text += '\n'.join(r) + '\n'
            os.remove(tmp)
        pdf.close()

        # 2. DeepSeek
        all_answers = []
        chunks = []
        pos = 0
        while pos < len(text):
            chunks.append(text[pos:pos+14000])
            pos += 13000
        for ci, chunk in enumerate(chunks[:4]):
            prompt = f'''从以下四级真题答案解析OCR文字中提取正确答案。
返回JSON数组：[{{\"question_number\":题号,\"answer\":\"答案字母\",\"type\":\"听力或阅读\"}}]
听力题号1-25，阅读题号26-55。答案一个字母。无把握不返回。仅返回JSON。
OCR文字({ci+1}/{len(chunks)}):{chunk}'''
            resp = requests.post('https://api.deepseek.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}],
                      'max_tokens': 4000, 'temperature': 0}, timeout=120)
            if resp.status_code == 200:
                jm = re.search(r'\[.*\]', resp.json()['choices'][0]['message']['content'], re.DOTALL)
                if jm: all_answers.extend(json.loads(jm.group()))

        seen = set(); answers = []
        for a in all_answers:
            k = (a.get('question_number'), a.get('type'))
            if k not in seen: seen.add(k); answers.append(a)

        # 3. Save to DB
        from answer_sheet import extract_match_key
        ym, suite = extract_match_key(fname)
        db = pymysql.connect(**DB); cur = db.cursor()
        cur.execute('SELECT DISTINCT source FROM question')
        sources = [r[0] for r in cur.fetchall()]
        matched = None
        for src in sources:
            if not src: continue
            s_ym, s_suite = extract_match_key(src)
            if s_ym == ym and s_suite == suite: matched = src; break

        cur.execute('INSERT INTO answer_sheet VALUES (NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())',
            (fname, path, ym, suite, 1, text[:100000], json.dumps(answers, ensure_ascii=False), matched or '', 0))
        cnt = 0
        if matched:
            tm = {'听力': '听力', '阅读': '阅读'}
            for a in answers:
                qn, aw, at = a.get('question_number'), a.get('answer', ''), a.get('type', '')
                mt = tm.get(at)
                if qn and aw and mt:
                    cur.execute('UPDATE question SET answer=%s WHERE source=%s AND question_number=%s AND type=%s',
                        (aw, matched, qn, mt))
                    cnt += cur.rowcount
            cur.execute('UPDATE answer_sheet SET match_count=%s WHERE filename=%s', (cnt, fname))
        db.commit(); db.close()
        return {'file': fname, 'answers': len(answers), 'applied': cnt}
    except Exception as e:
        return {'file': fname, 'answers': 0, 'applied': 0, 'error': str(e)}


def main():
    jobs = collect_scanned_pdfs()
    print(f'Scanned PDFs to process: {len(jobs)}')
    if not jobs:
        print('All done!')
        return

    t0 = time.time()
    with Pool(processes=3) as pool:
        results = pool.map(process_one, jobs)

    elapsed = (time.time() - t0) / 60
    total_ans = sum(r['answers'] for r in results)
    total_app = sum(r['applied'] for r in results)
    errors = [r for r in results if r.get('error')]

    print(f'\n=== DONE in {elapsed:.0f} min ===')
    print(f'PDFs: {len(results)}, Answers: {total_ans}, Applied: {total_app}')
    if errors:
        print(f'Errors: {len(errors)}')
        for e in errors[:5]:
            print(f'  {e["file"][:50]}: {e["error"][:80]}')


if __name__ == '__main__':
    main()
