"""add discount coupons and redemptions

Two tables. `coupons` is the definition of a code; `coupon_redemptions` is one
row per member per coupon, and the number of live rows IS the usage counter —
there is deliberately no `times_used` column to drift away from the truth.

Two constraints in here do real work and are not decoration:

  uq_coupon_redemption_slot        (coupon_id, slot_no)
      The thirty-slot cap, enforced by the schema. coupon_service assigns
      slot_no under a row lock on the coupon; if that lock were ever bypassed,
      two transactions both claiming slot 30 collide here and one rolls back.
      NULLable because a slot that is handed back has to go into the pool for
      the next member, and NULLs do not collide in a unique index.

  uq_coupon_redemption_live        (coupon_id, user_id) WHERE status IN ('pending','active')
      One member cannot take the same coupon twice — as an index, not as an
      `if` somebody has to remember to write. Partial over the two statuses
      that actually hold a slot, so that a member whose manual request was
      rejected, or whose checkout hold lapsed, can use the code again while the
      old row stays for the record.

Also adds `expected_amount` and `coupon_code` to manual_payment_requests. The
existing `amount` there is typed by the payer and is a claim; `expected_amount`
is worked out server-side, and it is what the reviewer compares the receipt
against — otherwise a discounted transfer looks short and gets rejected by
mistake.

Seeds the two launch codes, Monzer and Os10: 10% off, thirty members each.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), nullable=False),
        # Lowercase, always — that is what makes monzer / MONZER / Monzer one
        # code rather than three. display_code keeps the pretty spelling for
        # anything shown to a human.
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_code", sa.String(length=64), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
    )
    op.create_index("ix_coupons_id", "coupons", ["id"])
    op.create_index("ix_coupons_code", "coupons", ["code"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("manual_request_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("slot_no", sa.Integer(), nullable=True),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EGP"),
        sa.Column("plan_key", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # SET NULL, not CASCADE: if a payment row is ever removed the redemption
        # must survive, or deleting a payment would silently give a coupon slot
        # back and the count would be wrong.
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["manual_request_id"], ["manual_payment_requests.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("coupon_id", "slot_no", name="uq_coupon_redemption_slot"),
    )
    op.create_index("ix_coupon_redemptions_id", "coupon_redemptions", ["id"])
    op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
    op.create_index("ix_coupon_redemptions_user_id", "coupon_redemptions", ["user_id"])
    op.create_index("ix_coupon_redemptions_status", "coupon_redemptions", ["status"])

    # One live claim per (coupon, member). Partial so that a row which is no
    # longer holding anything — released after a rejection, or expired after an
    # abandoned checkout — stops blocking the member it belonged to.
    op.create_index(
        "uq_coupon_redemption_live",
        "coupon_redemptions",
        ["coupon_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )

    # ── manual requests: what the member OWED, next to what they claim ──
    op.add_column("manual_payment_requests", sa.Column("expected_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("manual_payment_requests", sa.Column("coupon_code", sa.String(length=64), nullable=True))

    # ── Seed the two launch coupons ──
    # ON CONFLICT so this is safe to re-run and so it does not fight
    # seed_defaults(), which ensures the same two rows on every boot.
    op.execute(
        """
        INSERT INTO coupons (code, display_code, discount_percent, max_redemptions, is_active)
        VALUES ('monzer', 'Monzer', 10.00, 30, true),
               ('os10',   'Os10',   10.00, 30, true)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("manual_payment_requests", "coupon_code")
    op.drop_column("manual_payment_requests", "expected_amount")

    op.drop_index("uq_coupon_redemption_live", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_status", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_user_id", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_coupon_id", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_id", table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")

    op.drop_index("ix_coupons_code", table_name="coupons")
    op.drop_index("ix_coupons_id", table_name="coupons")
    op.drop_table("coupons")
