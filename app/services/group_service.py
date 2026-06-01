from sqlalchemy.orm import Session

from app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group
from app.models.watchlist import WatchlistItem


class CannotDeleteDefaultGroupError(ValueError):
    """默认分组不可删除。"""


def delete_group(
    db: Session,
    group_id: int,
    strategy: str = "move_to_default",
) -> dict | None:
    """删除分组，按策略处理组内股票。

    :param strategy: ``move_to_default`` 将股票移入默认分组，
                     ``delete_all`` 一并删除组内股票。
    :returns: 操作结果字典，分组不存在时返回 ``None``。
    """
    if group_id == DEFAULT_GROUP_ID:
        raise CannotDeleteDefaultGroupError("默认分组不可删除")

    group = db.get(Group, group_id)
    if group is None:
        return None

    items = db.query(WatchlistItem).filter_by(group_id=group_id).all()

    if strategy == "move_to_default":
        for item in items:
            item.group_id = DEFAULT_GROUP_ID
        moved_count = len(items)
        deleted_count = 0
    else:  # delete_all
        for item in items:
            db.delete(item)
        moved_count = 0
        deleted_count = len(items)

    db.delete(group)
    db.commit()

    return {
        "moved_count": moved_count,
        "deleted_count": deleted_count,
    }


def find_or_create_group(db: Session, name: str) -> dict:
    """按名称查找分组，不存在则创建。

    返回 ``{"id": group_id, "name": group_name}``。
    """
    if name == DEFAULT_GROUP_NAME:
        return {"id": DEFAULT_GROUP_ID, "name": name}

    group = db.query(Group).filter_by(name=name).first()
    if group is None:
        group = Group(name=name)
        db.add(group)
        db.commit()
        db.refresh(group)

    return {"id": group.id, "name": group.name}
