"""baseline

Revision ID: e25f2c152474
Revises: 
Create Date: 2026-10-16 12:50:01.770308

"""
from typing import Sequence, Union


from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector


# revision identifiers, used by Alembic.
revision: str = 'e25f2c152474'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
