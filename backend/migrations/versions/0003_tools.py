"""Owner-scoped demo orders and explicitly confirmed support tickets."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE orders (
        id text PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
        status text NOT NULL, delivery_date date NOT NULL
    )""")
    op.execute("""INSERT INTO orders VALUES
        ('ORD-1001', '00000000-0000-0000-0000-000000000001', 'shipped', '2026-10-12'),
        ('ORD-2001', '00000000-0000-0000-0000-000000000002', 'processing', '2026-10-15')""")
    op.execute("""CREATE TABLE pending_actions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        owner_id uuid NOT NULL REFERENCES users(id),
        subject text NOT NULL, body text NOT NULL,
        expires_at timestamptz NOT NULL DEFAULT now() + interval '10 minutes'
    )""")
    op.execute("""CREATE TABLE tickets (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        action_id uuid NOT NULL UNIQUE REFERENCES pending_actions(id),
        owner_id uuid NOT NULL REFERENCES users(id),
        subject text NOT NULL, body text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE tickets")
    op.execute("DROP TABLE pending_actions")
    op.execute("DROP TABLE orders")
