"""Exact conflict and boundary browser confirmation operations."""

from alembic import op

revision = "20261001_0018"
down_revision = "20261001_0017"
branch_labels = None
depends_on = None

OLD_ACTIONS = "action IN ('FACT_REVIEW', 'WORDING_REVIEW', 'PROFILE_EXPORT', 'RESUME_EXPORT')"
NEW_ACTIONS = "action IN ('FACT_REVIEW', 'WORDING_REVIEW', 'PROFILE_EXPORT', 'RESUME_EXPORT', 'CONFLICT_REVIEW', 'BOUNDARY_REVIEW')"


def _replace(expression):
    with op.batch_alter_table("browser_operations") as batch:
        batch.drop_constraint("ck_browser_operation_action", type_="check")
        batch.create_check_constraint("ck_browser_operation_action", expression)


def upgrade() -> None:
    _replace(NEW_ACTIONS)


def downgrade() -> None:
    # A populated database with these newer actions must be handled explicitly;
    # never discard pending or completed operations to make downgrade succeed.
    _replace(OLD_ACTIONS)
