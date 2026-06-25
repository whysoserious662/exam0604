"""
FastAPI 主入口 — 按业务模块挂载路由 + 托管前端静态文件
"""
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from question_bank import router as question_router
from exam_records import router as exam_record_router
from paper import router as paper_router
from analysis.routes import router as analysis_router
from difficulty import router as difficulty_router
from auth import router as auth_router
from answer_sheet import router as answer_sheet_router

app = FastAPI()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])

# API 路由
app.include_router(question_router)
app.include_router(exam_record_router)
app.include_router(paper_router)
app.include_router(analysis_router)
app.include_router(difficulty_router)
app.include_router(auth_router)
app.include_router(answer_sheet_router)

# 托管前端静态文件（生产模式）
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exam-frontend", "dist")

# SPA catch-all（在API路由之后注册，优先级低于API路由）
@app.get("/{full_path:path}")
async def serve_spa(full_path: str = ""):
    """API未匹配时返回前端页面"""
    if not os.path.exists(frontend_dist):
        return {"msg": "前端未构建，请运行 npm run build"}

    # 尝试返回具体文件
    file_path = os.path.join(frontend_dist, full_path)
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path)

    # SPA fallback
    return FileResponse(os.path.join(frontend_dist, "index.html"))
