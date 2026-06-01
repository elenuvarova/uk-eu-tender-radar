"""Add buyer, buyer_category_stat, supplier_profile, saved_search tables

Revision ID: a1b2c3d4e5f6
Revises: 8f81000f2f85
Create Date: 2026-05-31 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8f81000f2f85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: earlier deploys created these tables via SQLModel.create_all()
    # at app startup, so on an existing prod DB they already exist while
    # alembic_version still points at the baseline. Only create what's missing,
    # so this runs cleanly both on a drifted prod DB and on a fresh one.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if 'buyer' not in existing:
        op.create_table(
            'buyer',
            sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('canonical_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('normalized_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('country', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('region', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('name_aliases', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    buyer_indexes = (
        {ix['name'] for ix in insp.get_indexes('buyer')}
        if 'buyer' in existing else set()
    )
    if 'ix_buyer_normalized_name' not in buyer_indexes:
        op.create_index('ix_buyer_normalized_name', 'buyer', ['normalized_name'], unique=False)

    if 'buyer_category_stat' not in existing:
        op.create_table(
            'buyer_category_stat',
            sa.Column('buyer_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('cpv_division', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('notice_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('awarded_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('avg_value_eur', sa.Float(), nullable=True),
            sa.Column('last_notice_date', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['buyer_id'], ['buyer.id']),
            sa.PrimaryKeyConstraint('buyer_id', 'cpv_division'),
        )

    if 'supplier_profile' not in existing:
        op.create_table(
            'supplier_profile',
            sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('target_cpv_codes', sa.JSON(), nullable=True),
            sa.Column('keywords', sa.JSON(), nullable=True),
            sa.Column('value_min', sa.Float(), nullable=True),
            sa.Column('value_max', sa.Float(), nullable=True),
            sa.Column('value_currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False,
                      server_default='EUR'),
            sa.Column('target_countries', sa.JSON(), nullable=True),
            sa.Column('min_days_to_bid', sa.Integer(), nullable=False, server_default='7'),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'saved_search' not in existing:
        op.create_table(
            'saved_search',
            sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('filters_json', sa.JSON(), nullable=True),
            sa.Column('alert_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())
    for table in ('saved_search', 'supplier_profile', 'buyer_category_stat'):
        if table in existing:
            op.drop_table(table)
    if 'buyer' in existing:
        op.drop_index('ix_buyer_normalized_name', table_name='buyer')
        op.drop_table('buyer')
