"""批量分析题库中所有题目，使用 AI+textstat 混合分析，更新难度分和维度明细"""
from datetime import datetime
from db.database import SessionLocal
from models.question import Question
from services.difficulty_analyzer import analyze_question_hybrid, analyze_question


def batch_analyze_all(use_ai=True):
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
        total = len(questions)
        mode = "AI+textstat混合" if use_ai else "textstat静态"
        print(f"共 {total} 道题待分析（{mode}）\n")

        updated = 0
        ai_success = 0
        ai_fail = 0

        for i, q in enumerate(questions, 1):
            if use_ai:
                result = analyze_question_hybrid(q.content, q.type)
            else:
                result = analyze_question(q.content, q.type)

            new_difficulty = result["difficulty"]
            if q.difficulty != new_difficulty:
                q.difficulty = new_difficulty
                updated += 1

            source = result.get("source", "static")
            if source == "ai":
                ai_success += 1
            elif source == "textstat_fallback":
                ai_fail += 1

            q.difficulty_detail = {
                "version": "2.0",
                "source": source,
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_detail": result.get("ai_detail"),
                "metrics": result.get("metrics"),
            }

            level = result["level"]
            reason = ""
            if result.get("ai_detail") and result["ai_detail"].get("reasoning"):
                reason = result["ai_detail"]["reasoning"][:60]
            print(f"[{i:3d}/{total}] ID={q.id:4d} | {q.type} | "
                  f"难度 {new_difficulty}({level}) | 来源 {source} | {reason}")

        db.commit()
        print(f"\n完成！更新 {updated}/{total} 题，AI成功 {ai_success}，降级 {ai_fail}")

        from sqlalchemy import func
        dist = db.query(Question.difficulty, func.count(Question.id)).group_by(Question.difficulty).all()
        print("\n难度分布：")
        for diff, cnt in sorted(dist, key=lambda x: x[0]):
            print(f"  难度 {diff}: {cnt} 题")

    except Exception as e:
        db.rollback()
        print(f"失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    use_ai = "--textstat-only" not in sys.argv
    batch_analyze_all(use_ai=use_ai)

