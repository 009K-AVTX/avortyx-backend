"""Brings an existing database up to date with the models.

db.create_all() makes missing tables but never adds a column to a table that already exists, so
a server that ran the first version would fail on the new Telegram and email columns. This adds
any missing column with its default, at start-up. It only ever adds: nothing is renamed or
dropped. (Replace with Flask-Migrate if the models start changing in other ways.)
"""
import logging

from sqlalchemy import inspect, literal, text

log = logging.getLogger(__name__)


def _default_sql(column, dialect):
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return None
    return str(literal(default.arg, type_=column.type).compile(dialect=dialect, compile_kwargs={"literal_binds": True}))


def add_missing_columns(db):
    engine = db.engine
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    added = []
    with engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all makes it whole
            have = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(dialect=engine.dialect)}'
                default = _default_sql(column, engine.dialect)
                if default is not None:
                    ddl += f" DEFAULT {default}"
                    if not column.nullable:
                        ddl += " NOT NULL"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
    if added:
        log.warning("database: added columns %s", ", ".join(added))
    return added
