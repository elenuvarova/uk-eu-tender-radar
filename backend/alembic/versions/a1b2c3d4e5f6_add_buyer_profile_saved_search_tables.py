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
    with op.batch_alter_table('buyer', schema=None) as batch_op:
        batch_op.create_index('ix_buyer_normalized_name', ['normalized_name'], unique=False)

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

    op.create_table(
        'saved_search',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('filters_json', sa.JSON(), nullable=True),
        sa.Column('alert_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('saved_search')
    op.drop_table('supplier_profile')
    op.drop_table('buyer_category_stat')
    with op.batch_alter_table('buyer', schema=None) as batch_op:
        batch_op.drop_index('ix_buyer_normalized_name')
    op.drop_table('buyer')
