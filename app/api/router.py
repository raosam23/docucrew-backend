from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.collections import router as collections_router
from app.api.routes.documents import router as documents_router
from app.api.routes.query import router as query_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(collections_router, prefix="/collections", tags=["Collections"])
router.include_router(documents_router, prefix="/collections", tags=["Documents"])
router.include_router(query_router, prefix="/collections", tags=["Query"])