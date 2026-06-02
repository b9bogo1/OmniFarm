"""add FK and query indexes for N+1 elimination

Revision ID: a4f9b2c1d8e7
Revises: ebe903c50c31
Create Date: 2026-05-29

"""
from alembic import op
import sqlalchemy as sa

revision = 'a4f9b2c1d8e7'
down_revision = 'ebe903c50c31'
branch_labels = None
depends_on = None


def upgrade():
    # FK indexes — missing from initial migration, critical for aggregation queries
    with op.batch_alter_table('aquaculture_records', schema=None) as batch_op:
        batch_op.create_index('ix_aquaculture_records_pond_id', ['pond_id'], unique=False)
        batch_op.create_index('ix_aquaculture_records_record_date', ['record_date'], unique=False)

    with op.batch_alter_table('poultry_records', schema=None) as batch_op:
        batch_op.create_index('ix_poultry_records_flock_id', ['flock_id'], unique=False)
        batch_op.create_index('ix_poultry_records_record_date', ['record_date'], unique=False)

    with op.batch_alter_table('cuniculture_records', schema=None) as batch_op:
        batch_op.create_index('ix_cuniculture_records_batch_id', ['batch_id'], unique=False)
        batch_op.create_index('ix_cuniculture_records_record_date', ['record_date'], unique=False)

    # Finance — entry_date is used in every monthly chart query; entry_type in all totals
    with op.batch_alter_table('finance_entries', schema=None) as batch_op:
        batch_op.create_index('ix_finance_entries_entry_date', ['entry_date'], unique=False)
        batch_op.create_index('ix_finance_entries_entry_type', ['entry_type'], unique=False)

    # Health — event_date and production_unit are filtered/sorted on every list load
    with op.batch_alter_table('health_events', schema=None) as batch_op:
        batch_op.create_index('ix_health_events_event_date', ['event_date'], unique=False)
        batch_op.create_index('ix_health_events_production_unit', ['production_unit'], unique=False)
        batch_op.create_index('ix_health_events_next_due_date', ['next_due_date'], unique=False)


def downgrade():
    with op.batch_alter_table('health_events', schema=None) as batch_op:
        batch_op.drop_index('ix_health_events_next_due_date')
        batch_op.drop_index('ix_health_events_production_unit')
        batch_op.drop_index('ix_health_events_event_date')

    with op.batch_alter_table('finance_entries', schema=None) as batch_op:
        batch_op.drop_index('ix_finance_entries_entry_type')
        batch_op.drop_index('ix_finance_entries_entry_date')

    with op.batch_alter_table('cuniculture_records', schema=None) as batch_op:
        batch_op.drop_index('ix_cuniculture_records_record_date')
        batch_op.drop_index('ix_cuniculture_records_batch_id')

    with op.batch_alter_table('poultry_records', schema=None) as batch_op:
        batch_op.drop_index('ix_poultry_records_record_date')
        batch_op.drop_index('ix_poultry_records_flock_id')

    with op.batch_alter_table('aquaculture_records', schema=None) as batch_op:
        batch_op.drop_index('ix_aquaculture_records_record_date')
        batch_op.drop_index('ix_aquaculture_records_pond_id')
