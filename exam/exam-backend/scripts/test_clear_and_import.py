"""清空题库并重新导入"""
import requests

def clear_and_reimport():
    try:
        print("=== 清空题库 ===")
        response = requests.delete("http://localhost:8000/exam/bank/clear")
        print(f"清空结果: {response.json()}")
        print()
        
        print("=== 检查清空后的统计 ===")
        response = requests.get("http://localhost:8000/exam/bank/stats")
        print(f"统计结果: {response.json()}")
        
    except Exception as e:
        print(f"操作失败: {e}")

if __name__ == "__main__":
    clear_and_reimport()
