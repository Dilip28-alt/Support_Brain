"""
Auth routes — register, login, logout, me.
"""
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Business, User
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse
from app.utils.auth import hash_password, verify_password, create_access_token, get_current_active_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:50]


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check email not already registered
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create unique slug
    base_slug = _slugify(data.business_name)
    slug = base_slug
    counter = 1
    while True:
        slug_check = await db.execute(select(Business).where(Business.slug == slug))
        if not slug_check.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create business
    business = Business(
        name=data.business_name,
        slug=slug,
        description=data.business_description,
    )
    db.add(business)
    await db.flush()

    # Create owner user
    user = User(
        business_id=business.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_owner=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(business)

    token = create_access_token({"sub": str(user.id), "business_id": str(business.id)})
    return TokenResponse(
        access_token=token,
        business_id=business.id,
        business_slug=business.slug,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Load business
    biz_result = await db.execute(select(Business).where(Business.id == user.business_id))
    business = biz_result.scalar_one()

    token = create_access_token({"sub": str(user.id), "business_id": str(business.id)})
    return TokenResponse(
        access_token=token,
        business_id=business.id,
        business_slug=business.slug,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.post("/login/form", response_model=TokenResponse)
async def login_form(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 password form endpoint (used by FastAPI docs)."""
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    biz_result = await db.execute(select(Business).where(Business.id == user.business_id))
    business = biz_result.scalar_one()
    token = create_access_token({"sub": str(user.id), "business_id": str(business.id)})
    return TokenResponse(
        access_token=token,
        business_id=business.id,
        business_slug=business.slug,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_active_user)):
    return current_user
