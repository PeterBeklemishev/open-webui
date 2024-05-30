from peewee import InterfaceError as PeeWeeInterfaceError, _ConnectionState
from peewee_migrate import Router
from playhouse.shortcuts import ReconnectMixin
from playhouse.db_url import PooledPostgresqlDatabase, connect, register_database
from psycopg2 import OperationalError
from psycopg2.errors import InterfaceError
from config import SRC_LOG_LEVELS, DATA_DIR, DATABASE_URL
import os
import logging
from contextvars import ContextVar

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])

# Check if the file exists
if os.path.exists(f"{DATA_DIR}/ollama.db"):
    # Rename the file
    os.rename(f"{DATA_DIR}/ollama.db", f"{DATA_DIR}/webui.db")
    log.info("Database migrated from Ollama-WebUI successfully.")
else:
    pass


db_state_default = {"closed": None, "conn": None, "ctx": None, "transactions": None}
db_state = ContextVar("db_state", default=db_state_default.copy())


class PeeweeConnectionState(_ConnectionState):
    def __init__(self, **kwargs):
        super().__setattr__("_state", db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name, value):
        self._state.get()[name] = value

    def __getattr__(self, name):
        return self._state.get()[name]


class PGReconnectMixin(ReconnectMixin):
    reconnect_errors = (
        # Postgres error examples:
        (OperationalError, 'termin'),
        (InterfaceError, 'closed'),
        (PeeWeeInterfaceError, 'closed'),
    )


class ReconnectingPostgresqlDatabase(PGReconnectMixin, PooledPostgresqlDatabase):
    pass


register_database(ReconnectingPostgresqlDatabase, 'postgres+pool', 'postgresql+pool')

DB = connect(DATABASE_URL)
DB._state = PeeweeConnectionState()
log.info(f"Connected to a {DB.__class__.__name__} database.")
router = Router(DB, migrate_dir="apps/web/internal/migrations", logger=log)
router.run()
DB.connect(reuse_if_open=True)
