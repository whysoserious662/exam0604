"""
OCR 扫描模块：对扫描版 PDF 进行 OCR 文字识别
使用 EasyOCR + pypdfium2（PDF转图片）
"""
import os
import pypdfium2 as pdfium

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        import easyocr
        # ch_sim=简体中文, en=英文
        _ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
    return _ocr


def ocr_pdf(pdf_path, progress_callback=None):
    """对 PDF 逐页 OCR，返回拼接后的纯文本"""
    ocr = _get_ocr()
    full_text = ""
    success_pages = 0

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        n_pages = len(pdf)

        for i in range(n_pages):
            try:
                page = pdf[i]
                # 渲染为图片（200 DPI 平衡速度和质量）
                bitmap = page.render(scale=200 / 72)
                img = bitmap.to_pil()

                tmp_path = f"data/temp_ocr_page_{i}.png"
                os.makedirs("data", exist_ok=True)
                img.save(tmp_path)

                # EasyOCR 识别
                result = ocr.readtext(tmp_path, detail=0)  # detail=0 只返回文字
                page_text = '\n'.join(result)
                full_text += page_text + "\n"
                success_pages += 1

                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

                if progress_callback:
                    progress_callback(i + 1, n_pages)

            except Exception as e:
                full_text += f"\n[OCR PAGE {i+1} ERROR: {e}]\n"
                continue

        pdf.close()
    except Exception as e:
        return f"[OCR ERROR: {e}]", 0

    return full_text, success_pages


def is_scanned_pdf(pdf_path):
    """快速判断 PDF 是否为扫描版"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]:
                t = page.extract_text()
                if t and len(t.strip()) > 50:
                    return False
            return True
    except Exception:
        return False
