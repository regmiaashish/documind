"""A successful standalone Alembic upgrade must survive closing its connection."""

import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text


def test_standalone_upgrade_commits_schema_and_seed(tmp_path, monkeypatch):
    # Use real local SQL transactions; only replace the async PostgreSQL transport.
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")

    @event.listens_for(engine, "connect")
    def schema_function(connection, record):
        connection.create_function("current_schema", 0, lambda: "main")

    class ConnectionAdapter:
        def __init__(self, connection):
            self.connection = connection

        async def run_sync(self, callback):
            callback(self.connection)

    class EngineAdapter:
        @asynccontextmanager
        async def connect(self):
            with engine.connect() as connection:
                yield ConnectionAdapter(connection)

        @asynccontextmanager
        async def begin(self):
            with engine.begin() as connection:
                yield ConnectionAdapter(connection)

        async def dispose(self):
            engine.dispose()

    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine", lambda *args, **kwargs: EngineAdapter()
    )
    migrations = tmp_path / "migrations"
    (migrations / "versions").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "migrations/env.py", migrations / "env.py")
    (migrations / "versions/0001_test.py").write_text(
        'from alembic import op\nrevision = "test_1"\ndown_revision = None\n'
        "def upgrade():\n"
        '    op.execute("CREATE TABLE demo_users (id integer PRIMARY KEY)")\n'
        '    op.execute("INSERT INTO demo_users VALUES (1)")\n',
        encoding="utf-8",
    )
    config = Config()
    config.set_main_option("script_location", str(migrations))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert inspect(connection).has_table("demo_users")
        assert connection.execute(text("SELECT count(*) FROM demo_users")).scalar_one() == 1
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "test_1"
        )
    engine.dispose()
