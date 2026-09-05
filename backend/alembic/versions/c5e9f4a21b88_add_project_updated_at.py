"""add updated_at to courseware_projects

Revision ID: c5e9f4a21b88
Revises: a3f8c21d94e7
Create Date: 2026-09-03 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e9f4a21b88'
down_revision: Union[str, Sequence[str], None] = 'a3f8c21d94e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 卡死任务收敛需要区分「正在推进」与「worker 崩溃后的僵死状态」，
    # 仅 courseware_projects 需要 updated_at，其余表暂不加。
    # 分两步：先加可空列 → 回填现有行为 created_at → 再收紧为 NOT NULL，
    # 避免「从未 UPDATE 过的项目 updated_at 为 NULL 导致卡死收敛失效」。
    with op.batch_alter_table("courseware_projects") as batch_op:
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute(
        "UPDATE courseware_projects SET updated_at = created_at "
        "WHERE updated_at IS NULL"
    )

    with op.batch_alter_table("courseware_projects") as batch_op:
        batch_op.alter_column("updated_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("courseware_projects") as batch_op:
        batch_op.drop_column("updated_at")
