"""add wallet balance snapshots

Revision ID: 6b2e1d9c4a7f
Revises: 3081f243ff8b
Create Date: 2026-07-24 09:02:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = "6b2e1d9c4a7f"
down_revision = "3081f243ff8b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wallet_transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sender_balance_after", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("receiver_balance_after", sa.Integer(), nullable=True))
    _backfill_balance_snapshots()


def downgrade():
    with op.batch_alter_table("wallet_transactions", schema=None) as batch_op:
        batch_op.drop_column("receiver_balance_after")
        batch_op.drop_column("sender_balance_after")


def _backfill_balance_snapshots():
    bind = op.get_bind()
    balances = {
        row.user_id: row.balance
        for row in bind.execute(sa.text("select user_id, balance from wallets")).mappings()
    }
    transactions = bind.execute(
        sa.text(
            """
            select id, sender_id, receiver_id, amount, transaction_type
            from wallet_transactions
            order by created_at desc, id desc
            """
        )
    ).mappings()

    for tx in transactions:
        sender_id = tx["sender_id"]
        receiver_id = tx["receiver_id"]
        amount = tx["amount"]
        sender_after = balances.get(sender_id) if sender_id is not None else None
        receiver_after = balances.get(receiver_id)

        bind.execute(
            sa.text(
                """
                update wallet_transactions
                set sender_balance_after = :sender_after,
                    receiver_balance_after = :receiver_after
                where id = :tx_id
                """
            ),
            {
                "sender_after": sender_after,
                "receiver_after": receiver_after,
                "tx_id": tx["id"],
            },
        )

        if tx["transaction_type"] == "TRANSFER":
            if sender_id is not None and sender_after is not None:
                balances[sender_id] = sender_after + amount
            if receiver_after is not None:
                balances[receiver_id] = receiver_after - amount
        elif tx["transaction_type"] == "ADMIN_GRANT" and receiver_after is not None:
            balances[receiver_id] = receiver_after - amount
