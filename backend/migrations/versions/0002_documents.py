"""Add owner-scoped documents, chunks, and two local demo identities."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            api_key_hash text NOT NULL UNIQUE
        )
    """)
    op.execute("""
        CREATE TABLE documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id uuid NOT NULL REFERENCES users(id),
            filename text NOT NULL,
            content_type text NOT NULL,
            size_bytes integer NOT NULL CHECK (size_bytes > 0),
            content_hash text NOT NULL,
            page_count integer,
            chunk_count integer NOT NULL CHECK (chunk_count > 0),
            chunk_size integer NOT NULL CHECK (chunk_size > 0),
            chunk_overlap integer NOT NULL CHECK (chunk_overlap >= 0 AND chunk_overlap < chunk_size),
            embedding_model text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (owner_id, content_hash, chunk_size, chunk_overlap, embedding_model)
        )
    """)
    op.execute("""
        CREATE TABLE chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index integer NOT NULL CHECK (chunk_index >= 0),
            page integer CHECK (page > 0),
            content text NOT NULL,
            token_count integer NOT NULL CHECK (token_count > 0),
            embedding vector(768) NOT NULL,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
            UNIQUE (document_id, chunk_index)
        )
    """)
    op.execute("""
        CREATE INDEX documents_owner_created_idx ON documents (owner_id, created_at DESC)
    """)
    # Owner checks join documents; ownership has one source of truth.
    op.execute("""
        CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)
    """)
    op.execute("""
        INSERT INTO users (id, name, api_key_hash) VALUES
            ('00000000-0000-0000-0000-000000000001', 'Alice', '724c3a14d3ea8b29272df65af1388d5d2f8db3bb8838f97832ee174011b5bd02'),
            ('00000000-0000-0000-0000-000000000002', 'Bob', '928d0e301fa5359204a65b60c4bd40dc36db8f25a0246e6d0d452b4d676e420a')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE chunks")
    op.execute("DROP TABLE documents")
    op.execute("DROP TABLE users")
