"""add_ai_vm_features

Revision ID: ac6f3bf8838f
Revises: 699113298584
Create Date: 2026-03-04 19:41:13.926824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ac6f3bf8838f'
down_revision: Union[str, Sequence[str], None] = '699113298584'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    suggestion_status = postgresql.ENUM('PENDING', 'ACCEPTED', 'DISMISSED', name='suggestionstatus')
    suggestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table('vm_description_log',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vm_id', sa.UUID(), nullable=True),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('suggested_config', sa.JSON(), nullable=True),
    sa.Column('chosen_config', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vm_description_log_tenant_id'), 'vm_description_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_vm_description_log_vm_id'), 'vm_description_log', ['vm_id'], unique=False)
    op.create_table('vm_metrics',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vm_id', sa.UUID(), nullable=False),
    sa.Column('cpu_pct', sa.Float(), nullable=False),
    sa.Column('ram_pct', sa.Float(), nullable=False),
    sa.Column('disk_pct', sa.Float(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vm_metrics_recorded_at'), 'vm_metrics', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_vm_metrics_vm_id'), 'vm_metrics', ['vm_id'], unique=False)
    op.create_index('ix_vm_metrics_vm_recorded', 'vm_metrics', ['vm_id', 'recorded_at'], unique=False)
    op.create_table('vm_suggestions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vm_id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('suggestion_text', sa.String(), nullable=False),
    sa.Column('suggested_config', sa.JSON(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', postgresql.ENUM('PENDING', 'ACCEPTED', 'DISMISSED', name='suggestionstatus', create_type=False), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vm_suggestions_tenant_id'), 'vm_suggestions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_vm_suggestions_vm_id'), 'vm_suggestions', ['vm_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_vm_suggestions_vm_id'), table_name='vm_suggestions')
    op.drop_index(op.f('ix_vm_suggestions_tenant_id'), table_name='vm_suggestions')
    op.drop_table('vm_suggestions')
    op.drop_index('ix_vm_metrics_vm_recorded', table_name='vm_metrics')
    op.drop_index(op.f('ix_vm_metrics_vm_id'), table_name='vm_metrics')
    op.drop_index(op.f('ix_vm_metrics_recorded_at'), table_name='vm_metrics')
    op.drop_table('vm_metrics')
    op.drop_index(op.f('ix_vm_description_log_vm_id'), table_name='vm_description_log')
    op.drop_index(op.f('ix_vm_description_log_tenant_id'), table_name='vm_description_log')
    op.drop_table('vm_description_log')
    postgresql.ENUM(name='suggestionstatus').drop(op.get_bind(), checkfirst=True)
