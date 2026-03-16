import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Policy
from api.schemas import PolicyResponse

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/evalforge/policies")


@router.post("", response_model=PolicyResponse, status_code=201)
async def upload_policy(
    name: str,
    description: str | None = None,
    file: UploadFile = ...,
    db: AsyncSession = Depends(get_db),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.py")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    policy = Policy(
        name=name,
        description=description,
        file_path=file_path,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("", response_model=list[PolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).order_by(Policy.created_at.desc()))
    return result.scalars().all()


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy
