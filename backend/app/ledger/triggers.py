"""The database's half of append-only: two triggers refusing the other verbs.

``app.storage.models`` already refuses an amendment from the service's side
(``D39``'s two mapper events).  This is the other half -- the refusal *in the
database*, so it also covers a statement that never passed through the ORM:
a raw ``UPDATE`` or ``DELETE``, a script, a second service, a future one.

**Only SQLite.**  ``RAISE`` is SQLite's own, so the DDL here is written for
that dialect and :func:`install_append_only_triggers` refuses any other
engine by name rather than sending a PostgreSQL server a syntax error.  The
table name is :data:`~app.storage.models.LEDGER_ENTRY_TABLE_NAME` rather than
a second spelling of it, and the trigger names are built from it.

**Installing is the only verb here.**  The module exports no way to drop the
guards, because nothing in the service may un-append an entry; a caller that
wants an empty log drops them by name and installs them again, which is
what this task's own tests do.

**The guards are ``BEFORE ... FOR EACH ROW`` and they ``ABORT``.**  Not
``AFTER`` -- an amendment that reached the row first would leave a window --
and not ``ROLLBACK``, which would throw away the transaction a refused
statement happened to travel in.  ``IF NOT EXISTS`` makes a second install a
no-op, so a caller may ask on every start; it also means a guard already
present under the name is *kept*, never replaced.

**A guard fires per row, so a statement that matches no row is not a
refusal.**  ``DELETE FROM ledger_entries`` against an empty log is allowed
and changes nothing, which is the one case where "the database said no" is
not what happened.
"""

from sqlalchemy import Engine

from app.storage.models import LEDGER_ENTRY_TABLE_NAME

__all__ = [
    "APPEND_ONLY_MESSAGE",
    "DELETE_TRIGGER_NAME",
    "UPDATE_TRIGGER_NAME",
    "install_append_only_triggers",
]


#: The trigger that refuses an amendment, named after the table it guards.
UPDATE_TRIGGER_NAME = f"{LEDGER_ENTRY_TABLE_NAME}_refuse_update"

#: The trigger that refuses a removal, named the same way.
DELETE_TRIGGER_NAME = f"{LEDGER_ENTRY_TABLE_NAME}_refuse_delete"

#: What an operator reads in the log when a write is refused.  One string for
#: both guards, because it is one claim: an entry is neither amended nor
#: removed.
APPEND_ONLY_MESSAGE = (
    f"{LEDGER_ENTRY_TABLE_NAME} is append-only: an entry is never amended "
    f"and never removed"
)


#: The two refusals, in the order :func:`install_append_only_triggers` issues
#: them: the trigger's name beside the statement it fires on.
_GUARDS: tuple[tuple[str, str], ...] = (
    (UPDATE_TRIGGER_NAME, "UPDATE"),
    (DELETE_TRIGGER_NAME, "DELETE"),
)


_CREATE_TRIGGER = """\
CREATE TRIGGER IF NOT EXISTS {name}
BEFORE {verb} ON {table}
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, '{message}');
END;
"""


def install_append_only_triggers(engine: Engine) -> None:
    """Put the two refusals on ``ledger_entries``, if they are not there.

    :param engine: the engine naming the database to guard.  A caller may
        pass its own, as :func:`app.storage.db.build_engine` answers, rather
        than the module-level one.
    :returns: nothing.  The DDL is committed before this returns, so a
        refusal on the next statement is the database's, not this call's.
    :raises ValueError: when ``engine`` is not SQLite, before any statement
        is sent -- the guards are written in a dialect only SQLite has.
    """
    dialect = engine.dialect.name
    if dialect != "sqlite":
        raise ValueError(
            f"append-only triggers are written for SQLite, and {dialect} has "
            f"no RAISE: {LEDGER_ENTRY_TABLE_NAME} is left unguarded"
        )
    with engine.begin() as connection:
        for name, verb in _GUARDS:
            connection.exec_driver_sql(
                _CREATE_TRIGGER.format(
                    name=name,
                    verb=verb,
                    table=LEDGER_ENTRY_TABLE_NAME,
                    message=APPEND_ONLY_MESSAGE,
                )
            )
