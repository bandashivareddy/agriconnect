"""Allow mobile-only accounts without changing existing identities."""
from alembic import op
import sqlalchemy as sa

revision = '8b213a901def'
down_revision = '44d0107abf58'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('users', 'email', existing_type=sa.String(150), nullable=True)


def downgrade():
    # PostgreSQL refuses this if mobile-only accounts exist; never invent emails.
    op.alter_column('users', 'email', existing_type=sa.String(150), nullable=False)
