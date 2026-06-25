"""测试前端API接口"""
import requests

def test_frontend_api():
    print("=== 测试前端组卷接口 ===")
    payload = {
        "difficulty": 2,
        "write_count": 1,
        "listen_count": 0,
        "read_count": 3,
        "translate_count": 2
    }
    response = requests.post("http://localhost:8000/api/paper/generate", json=payload)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"消息: {result.get('msg')}")
        if "error" in result:
            print(f"错误详情: {result.get('error')}")
        print(f"试卷内容: {result.get('data', {})}")
        print(f"统计信息: {result.get('summary', {})}")
    else:
        print(f"错误: {response.text}")

if __name__ == "__main__":
    test_frontend_api()
