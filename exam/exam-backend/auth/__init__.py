from utils.auth import require_teacher
from fastapi import Depends
"""
认证模块 — 注册、登录、用户管理
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from db.database import SessionLocal
from models.user import User
from utils.auth import (hash_password, verify_password, create_access_token,
                        get_current_user, require_teacher)

router = APIRouter(tags=["认证"], prefix="/api/auth")


# ── Schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "student"
    email: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    username: str = None
    email: str = None
    role: str = None
    is_active: bool = None
    password: str = None


# ── Register ──────────────────────────────────────────────────────────

@router.post("/register")
def register(data: RegisterRequest):
    if data.role not in ("student", "teacher"):
        return {"code": 400, "msg": "角色只能是 student 或 teacher"}
    if len(data.username) < 2 or len(data.username) > 20:
        return {"code": 400, "msg": "用户名长度需要2-20位"}
    if len(data.password) < 6:
        return {"code": 400, "msg": "密码长度至少6位"}

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == data.username).first():
            return {"code": 400, "msg": "用户名已存在"}
        if db.query(User).filter(User.email == data.email).first():
            return {"code": 400, "msg": "邮箱已被注册"}

        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role,
            email=data.email,
        )
        db.add(user)
        db.commit()
        return {"code": 200, "msg": "注册成功"}
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "注册失败", "error": str(e)}
    finally:
        db.close()


# ── Login ─────────────────────────────────────────────────────────────

@router.post("/login")
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if not user or not verify_password(data.password, user.password_hash):
            return {"code": 400, "msg": "用户名或密码错误"}
        if not user.is_active:
            return {"code": 400, "msg": "账户已被禁用"}

        token = create_access_token({"user_id": user.id})
        return {
            "code": 200,
            "msg": "登录成功",
            "data": {
                "token": token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "email": user.email,
                }
            }
        }
    except Exception as e:
        return {"code": 500, "msg": "登录失败", "error": str(e)}
    finally:
        db.close()


# ── Get current user ──────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "email": current_user.email,
        }
    }


# ── List users (teacher) ──────────────────────────────────────────────

@router.get("/users")
def list_users(teacher = Depends(require_teacher),page: int = 1, size: int = 10,
               current_user: User = Depends(require_teacher)):
    db = SessionLocal()
    try:
        q = db.query(User)
        total = q.count()
        items = q.order_by(User.id.desc()).offset((page - 1) * size).limit(size).all()
        return {
            "code": 200, "total": total, "page": page, "size": size,
            "pages": (total + size - 1) // size,
            "data": [{
                "id": u.id, "username": u.username, "role": u.role,
                "email": u.email, "is_active": u.is_active,
                "created_at": str(u.created_at) if u.created_at else None,
            } for u in items]
        }
    except Exception as e:
        return {"code": 500, "error": str(e)}
    finally:
        db.close()


# ── Update user (teacher) ─────────────────────────────────────────────

@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateRequest,
                teacher = Depends(require_teacher)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"code": 404, "msg": "用户不存在"}
        if data.username is not None:
            user.username = data.username
        if data.email is not None:
            user.email = data.email
        if data.role is not None:
            if data.role not in ("student", "teacher"):
                return {"code": 400, "msg": "角色只能是 student 或 teacher"}
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.password is not None and data.password.strip():
            user.password_hash = hash_password(data.password)
        db.commit()
        return {"code": 200, "msg": "修改成功"}
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "修改失败", "error": str(e)}
    finally:
        db.close()


# ── Delete user (teacher) ─────────────────────────────────────────────

@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_teacher)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"code": 404, "msg": "用户不存在"}
        if user.id == current_user.id:
            return {"code": 400, "msg": "不能删除自己"}
        db.delete(user)
        db.commit()
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "删除失败", "error": str(e)}
    finally:
        db.close()
