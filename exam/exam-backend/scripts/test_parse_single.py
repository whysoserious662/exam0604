"""测试单个PDF的解析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_parser import load_questions_from_pdf

def test_parse():
    pdf_path = "pdf_upload/2022.06四级真题第1套【可复制可搜索，打印首选】.pdf"
    
    print(f"正在解析: {pdf_path}")
    questions = load_questions_from_pdf(pdf_path)
    print(f"解析到 {len(questions)} 道题目")
    print()
    
    for i, q in enumerate(questions[:5], 1):  # 只显示前5道
        print(f"题目 {i}:")
        print(f"  ID: {q.id}")
        print(f"  类型: {q.type}")
        print(f"  难度: {q.difficulty}")
        print(f"  内容: {q.content[:100]}...")
        print(f"  选项: {q.options}")
        print()

if __name__ == "__main__":
    test_parse()
