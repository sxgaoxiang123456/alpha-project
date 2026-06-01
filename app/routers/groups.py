from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.group import DEFAULT_GROUP_ID, Group
from app.schemas.group import GroupCreate, GroupResponse, GroupUpdate
from app.services.group_service import CannotDeleteDefaultGroupError, delete_group

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
) -> Group:
    existing = db.query(Group).filter_by(name=data.name).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"分组名 '{data.name}' 已存在",
        )

    group = Group(name=data.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=list[GroupResponse])
def list_groups(
    db: Session = Depends(get_db),
) -> list[Group]:
    return db.query(Group).order_by(Group.is_default.desc(), Group.created_at.asc()).all()


@router.put("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Session = Depends(get_db),
) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分组 {group_id} 不存在",
        )

    existing = db.query(Group).filter_by(name=data.name).first()
    if existing is not None and existing.id != group_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"分组名 '{data.name}' 已存在",
        )

    group.name = data.name
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}")
def remove_group(
    group_id: int,
    strategy: str = Query(default="move_to_default"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = delete_group(db, group_id, strategy=strategy)
    except CannotDeleteDefaultGroupError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分组 {group_id} 不存在",
        )

    return result
