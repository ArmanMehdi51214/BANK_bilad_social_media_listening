from fastapi import APIRouter, Depends

from app.models.enums import UserRole
from app.models.user import User
from app.modules.auth.dependencies import (
    get_current_user,
    require_admin,
    require_admin_or_analyst,
)

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/info")
def system_info():
    return {
        "success": True,
        "message": "System information loaded successfully",
        "data": {
            "name": "Bank Albilad Executive Social Media Intelligence API",
            "version": "0.1.0",
            "phase": "Milestone 1 - Phase 2",
            "module": "Backend Core APIs",
        },
    }


@router.get("/protected")
def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "message": "Authenticated access granted",
        "data": {
            "user_email": current_user.email,
            "role": current_user.role,
        },
    }


@router.get("/admin-only")
def admin_only_endpoint(current_user: User = Depends(require_admin())):
    return {
        "success": True,
        "message": "Admin access granted",
        "data": {
            "user_email": current_user.email,
            "role": current_user.role,
            "access_level": "admin",
        },
    }


@router.get("/analyst-or-admin")
def analyst_or_admin_endpoint(current_user: User = Depends(require_admin_or_analyst())):
    return {
        "success": True,
        "message": "Analyst/Admin access granted",
        "data": {
            "user_email": current_user.email,
            "role": current_user.role,
            "access_level": "analyst_or_admin",
        },
    }


@router.get("/security-check")
def security_check(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "message": "Security context loaded successfully",
        "data": {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
            "permissions": {
                "can_view_dashboard": True,
                "can_manage_monitoring": current_user.role in [
                    UserRole.ADMIN.value,
                    UserRole.ANALYST.value,
                ],
                "can_manage_users": current_user.role == UserRole.ADMIN.value,
                "can_manage_system": current_user.role == UserRole.ADMIN.value,
            },
        },
    }
