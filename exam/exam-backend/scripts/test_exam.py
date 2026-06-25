import requests

def test_exam_api():
    try:
        # 测试题库统计接口
        print("测试题库统计接口...")
        response = requests.get("http://localhost:8000/exam/bank/stats")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.json()}")
        print()
        
        # 测试智能组卷接口
        print("测试智能组卷接口...")
        payload = {
            "choice_count": 5,
            "fill_count": 3,
            "essay_count": 1,
            "easy_ratio": 0.3,
            "medium_ratio": 0.5,
            "hard_ratio": 0.2,
            "shuffle": True
        }
        response = requests.post("http://localhost:8000/exam/generate", json=payload)
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.json()}")
        
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_exam_api()
