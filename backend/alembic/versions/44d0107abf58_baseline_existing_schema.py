"""baseline existing schema

Revision ID: 44d0107abf58
Revises: 
Create Date: 2026-09-07 16:59:42.619334

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44d0107abf58'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the authoritative baseline schema on an empty PostgreSQL database."""
    schema_file = Path(__file__).resolve().parents[2] / "schema" / "baseline_schema.sql"
    schema_sql = schema_file.read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(schema_sql)


def downgrade() -> None:
    """Baseline downgrade is intentionally unsupported because it is destructive."""
    raise NotImplementedError(
        "Baseline downgrade would drop the AgriConnect schema; use a disposable database instead."
    )
