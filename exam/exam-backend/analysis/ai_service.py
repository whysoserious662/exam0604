"""
AI 评语生成服务
"""
import json, urllib.request, os, socket
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def build_prompt(r):
    qa = r.get("question_analysis", [])
    min_rate = min(q.get("score_rate", 0) for q in qa) if qa else 0
    max_rate = max(q.get("score_rate", 0) for q in qa) if qa else 0
    return f"""你是一位大学英语四级(CET4)教学专家。请根据以下考试数据，生成一份中文试卷评语：

## 考试概况
- 参考人数：{r['student_count']} 人
- 平均分：{r['avg_score']} / {r['total_possible']}
- 得分率：{r['avg_score_rate'] * 100:.1f}%

## 题目分析摘要
每题得分率从 {min_rate * 100:.0f}% 到 {max_rate * 100:.0f}% 不等

请从以下四个方面给出评语（每个方面2-3句话）：
1. 整体评价：本次考试的整体水平如何，成绩分布是否合理
2. 优势与不足：学生表现好的方面和薄弱的方面
3. 教学建议：针对薄弱环节的教学改进建议
4. 学习建议：给学生个人的备考建议"""


def local_fallback_comment(r):
    avg = r['avg_score_rate']
    dist = r.get("score_distribution", [])
    if avg >= 0.7: level, suggestion = "整体表现良好", "保持现有教学节奏，重点关注中等偏下学生"
    elif avg >= 0.45: level, suggestion = "整体处于中等水平", "建议加强基础知识训练，增加针对性练习"
    else: level, suggestion = "整体成绩偏低，需要重点关注", "建议从基础概念入手，调整教学策略，加强课后辅导"

    high_count = sum(d['count'] for d in dist[-2:]) if dist else 0
    low_count = sum(d['count'] for d in dist[:2]) if dist else 0
    qa = r.get("question_analysis", [])
    weak_types = []
    if qa:
        weak = [str(q['question_number']) for q in qa if q.get('score_rate', 1) < 0.4][:5]
        strong = [str(q['question_number']) for q in qa if q.get('score_rate', 1) > 0.8][:5]
        if weak: weak_types.append(f"薄弱题目集中在题号 {'、'.join(weak)}")
        if strong: weak_types.append(f"掌握较好的题目：{'、'.join(strong)}")

    return f"""## 试卷评语（本地生成）

1. 整体评价
本次四级模拟考试参考人数 {r['student_count']} 人，平均分 {r['avg_score']} 分，得分率 {avg*100:.1f}%。{level}。
高分段占比约 {high_count} 人，低分段约 {low_count} 人，{('成绩呈正态分布' if high_count > low_count else '成绩偏低端集中，需引起重视')}。

2. 优势与不足
{"；".join(weak_types) if weak_types else "各题型得分较为均衡"}。

3. 教学建议
{suggestion}。

4. 学习建议
建议学生针对薄弱题型进行专项训练，合理规划复习时间，注重真题练习和错题总结。"""


def generate_comment(analysis_result):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return local_fallback_comment(analysis_result), None
    prompt = build_prompt(analysis_result)
    req_body = json.dumps({"model": DEEPSEEK_MODEL,
                           "messages": [{"role": "user", "content": prompt}],
                           "max_tokens": 1000, "temperature": 0.7}).encode("utf-8")
    request = urllib.request.Request(DEEPSEEK_API_URL, data=req_body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"], None
    except urllib.error.HTTPError as e:
        return None, f"DeepSeek API 请求失败 ({e.code}): {e.read().decode()[:200]}"
    except (urllib.error.URLError, socket.timeout):
        return local_fallback_comment(analysis_result), None
    except Exception:
        return local_fallback_comment(analysis_result), None
