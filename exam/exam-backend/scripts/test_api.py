"""测试组卷API"""
import requests

def test_api():
    try:
        print("=== 测试题库统计 ===")
        response = requests.get("http://localhost:8000/exam/bank/stats")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        print()
        
        print("=== 测试智能组卷 ===")
        payload = {
            "choice_count": 3,
            "fill_count": 2,
            "essay_count": 1,
            "easy_ratio": 0.3,
            "medium_ratio": 0.5,
            "hard_ratio": 0.2,
            "shuffle": True
        }
        response = requests.post("http://localhost:8000/exam/generate", json=payload)
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"响应: {result}")
        
        # 检查选项是否为空
        if "exam" in result:
            for q in result["exam"]:
                options = q.get("options", [])
                print(f"\n题目ID {q['id']}, 选项数量: {len(options)}")
                if options:
                    for opt in options:
                        print(f"  - {opt}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()
