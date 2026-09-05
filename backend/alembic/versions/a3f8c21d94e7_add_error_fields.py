"""add error_code/error_message to courseware slides and projects

Revision ID: a3f8c21d94e7
Revises: b6c1b042f0aa
Create Date: 2026-09-03 16:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8c21d94e7'
down_revision: Union[str, Sequence[str], None] = 'b6c1b042f0aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table：SQLite 不支持原生 ALTER TABLE DROP/ADD 组合操作，
    # batch 模式通过"建临时表→拷数据→换名"实现，兼容 PG 与 SQLite 两套环境。
    with op.batch_alter_table("courseware_slides") as batch_op:
        batch_op.add_column(sa.Column("error_code", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))

    with op.batch_alter_table("courseware_projects") as batch_op:
        batch_op.add_column(sa.Column("error_code", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("courseware_projects") as batch_op:
        batch_op.drop_column("error_code")

    with op.batch_alter_table("courseware_slides") as batch_op:
        batch_op.drop_column("error_message")
        batch_op.drop_column("error_code")
