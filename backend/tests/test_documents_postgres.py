"""Opt-in real pgvector tests, isolated in a temporary schema."""

import hashlib
import os
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from documind.core.config import settings
from documind.repositories.documents import (
    find_duplicate,
    get_document,
    list_documents,
    save_document,
)
from documind.schemas.documents import Chunk

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Set RUN_DATABASE_TESTS=1 with a local pgvector database.",
)
ALICE = UUID(int=1)


async def test_ticket_confirmation_is_owner_scoped_atomic_and_idempotent(pool):
    import asyncio

    from documind.exceptions import AppError
    from documind.repositories.actions import confirm_ticket, draft_ticket
    from documind.schemas.tools import CreateTicket

    draft = await draft_ticket(
        pool, ALICE, CreateTicket(tool="create_ticket", subject="Damage", body="Damaged package")
    )
    assert await pool.fetchval("SELECT count(*) FROM tickets") == 0
    with pytest.raises(AppError) as failure:
        await confirm_ticket(pool, UUID(int=2), draft.id)
    assert failure.value.status == 404
    first, second = await asyncio.gather(
        confirm_ticket(pool, ALICE, draft.id), confirm_ticket(pool, ALICE, draft.id)
    )
    assert first.id == second.id
    assert await pool.fetchval("SELECT count(*) FROM tickets") == 1


async def test_expired_ticket_draft_does_not_create_ticket(pool):
    from documind.exceptions import AppError
    from documind.repositories.actions import confirm_ticket, draft_ticket
    from documind.schemas.tools import CreateTicket

    draft = await draft_ticket(
        pool, ALICE, CreateTicket(tool="create_ticket", subject="Damage", body="Damaged package")
    )
    await pool.execute(
        "UPDATE pending_actions SET expires_at=now()-interval '1 minute' WHERE id=$1", draft.id
    )
    with pytest.raises(AppError) as failure:
        await confirm_ticket(pool, ALICE, draft.id)
    assert failure.value.status == 409
    assert await pool.fetchval("SELECT count(*) FROM tickets") == 0


@pytest.fixture
async def pool():
    schema = f"test_{uuid4().hex}"
    admin = await asyncpg.connect(str(settings.database_url))
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    engine = create_async_engine(
        str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://", 1),
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )

    def upgrade(connection):
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")

    database_pool = None
    try:
        async with engine.begin() as connection:
            await connection.run_sync(upgrade)
        database_pool = await asyncpg.create_pool(
            str(settings.database_url),
            min_size=1,
            max_size=3,
            server_settings={"search_path": f"{schema},public"},
        )
        yield database_pool
    finally:
        if database_pool is not None:
            await database_pool.close()
        await engine.dispose()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


async def save(pool, owner=ALICE, vectors=None):
    return await save_document(
        pool,
        owner,
        "policy.txt",
        "text/plain",
        20,
        hashlib.sha256(b"policy").hexdigest(),
        None,
        300,
        [Chunk("20 days annual leave", 4, None)],
        vectors if vectors is not None else [[1.0] + [0.0] * 767],
    )


async def test_duplicate_upload_is_atomic_and_owner_scoped(pool):
    from documind.repositories.chunks import summary_chunks
    from documind.schemas.chat import ChatRequest

    first, duplicate = await save(pool)
    second, duplicate_again = await save(pool)
    assert not duplicate and duplicate_again and first.document_id == second.document_id
    assert await pool.fetchval("SELECT count(*) FROM chunks") == 1
    assert await get_document(pool, UUID(int=2), first.document_id) is None
    assert await list_documents(pool, UUID(int=2), 20, 0) == []
    summary = ChatRequest(question="Summarize this pdf", document_ids=[first.document_id])
    assert await summary_chunks(pool, UUID(int=2), summary) == []
    assert (await summary_chunks(pool, ALICE, summary))[0].content == "20 days annual leave"
    assert (
        await find_duplicate(pool, UUID(int=2), hashlib.sha256(b"policy").hexdigest(), 300) is None
    )
    other, _ = await save(pool, owner=UUID(int=2))
    assert other.document_id != first.document_id


async def test_delete_cascades_chunks_and_preserves_other_owner(pool):
    from documind.repositories.documents import delete_document

    alice, _ = await save(pool)
    bob, _ = await save(pool, owner=UUID(int=2))
    assert not await delete_document(pool, UUID(int=2), alice.document_id)
    assert await get_document(pool, ALICE, alice.document_id) is not None
    assert await delete_document(pool, ALICE, alice.document_id)
    assert (
        await pool.fetchval("SELECT count(*) FROM chunks WHERE document_id=$1", alice.document_id)
        == 0
    )
    assert await get_document(pool, UUID(int=2), bob.document_id) is not None
    replacement, duplicate = await save(pool)
    assert not duplicate and replacement.document_id != alice.document_id


async def test_concurrent_uploads_create_one_document(pool):
    import asyncio

    results = await asyncio.gather(save(pool), save(pool))
    assert results[0][0].document_id == results[1][0].document_id
    assert sorted(duplicate for _, duplicate in results) == [False, True]
    assert await pool.fetchval("SELECT count(*) FROM chunks") == 1


async def test_chunk_failure_rolls_back_document(pool):
    with pytest.raises(asyncpg.PostgresError):
        await save(pool, vectors=[[1.0]])
    assert await pool.fetchval("SELECT count(*) FROM documents") == 0
    assert await pool.fetchval("SELECT count(*) FROM chunks") == 0


async def test_vector_and_keyword_search_enforce_owner_and_document_filters(pool):
    from documind.repositories.chunks import get_chunk, search_chunks
    from documind.schemas.chat import ChatRequest

    alice, _ = await save(pool)
    bob, _ = await save(pool, owner=UUID(int=2))
    vector = [1.0] + [0.0] * 767
    for keyword in (False, True):
        hits = await search_chunks(
            pool, ALICE, ChatRequest(question="annual leave"), vector, keyword
        )
        assert len(hits) == 1 and hits[0].document_id == alice.document_id
        assert (
            await search_chunks(
                pool,
                ALICE,
                ChatRequest(question="annual leave", document_ids=[bob.document_id]),
                vector,
                keyword,
            )
            == []
        )
        assert (
            await search_chunks(
                pool, ALICE, ChatRequest(question="annual leave", document_ids=[]), vector, keyword
            )
            == []
        )
        assert (
            await search_chunks(
                pool, ALICE, ChatRequest(question="annual leave", chunk_size=800), vector, keyword
            )
            == []
        )
        assert (
            await search_chunks(
                pool,
                ALICE,
                ChatRequest(question="annual leave", created_before="2000-01-01T00:00:00Z"),
                vector,
                keyword,
            )
            == []
        )
    assert await get_chunk(pool, UUID(int=2), alice.document_id, 0) is None
    assert (await get_chunk(pool, ALICE, alice.document_id, 0))["content"] == "20 days annual leave"
