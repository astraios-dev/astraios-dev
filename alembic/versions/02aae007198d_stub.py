"""stub for missing revision

Revision ID: 02aae007198d
Revises: cdffb41d4526
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = '02aae007198d'
down_revision: Union[str, None] = 'cdffb41d4526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
