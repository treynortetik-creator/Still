"""Database compatibility helpers for PostgreSQL and SQLite."""
from app.config import get_settings

settings = get_settings()


def sql(query: str) -> str:
    """Convert SQLite-style query to PostgreSQL if needed.

    Converts:
    - ? placeholders to $1, $2, $3... (PostgreSQL style)
    - INSERT OR REPLACE to INSERT ... ON CONFLICT
    - datetime('now') to NOW()
    """
    if not settings.use_postgres:
        return query

    # Convert ? placeholders to $1, $2, $3...
    result = []
    param_count = 0
    i = 0
    while i < len(query):
        if query[i] == '?':
            param_count += 1
            result.append(f'${param_count}')
        else:
            result.append(query[i])
        i += 1

    converted = ''.join(result)

    # Convert datetime('now') to NOW()
    converted = converted.replace("datetime('now')", "NOW()")

    return converted


async def execute_insert_returning_id(conn, query: str, params: tuple) -> int:
    """Execute an INSERT and return the new row's ID.

    Handles the difference between SQLite (lastrowid) and PostgreSQL (RETURNING).
    """
    if settings.use_postgres:
        # PostgreSQL: add RETURNING clause and use fetchval
        pg_query = sql(query)
        if 'RETURNING' not in pg_query.upper():
            pg_query = pg_query.rstrip().rstrip(';') + ' RETURNING id'
        result = await conn.fetchval(pg_query, *params)
        return result
    else:
        # SQLite: use cursor.lastrowid
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.lastrowid


async def execute(conn, query: str, params: tuple = ()):
    """Execute a query with automatic placeholder conversion."""
    converted_query = sql(query)

    if settings.use_postgres:
        return await conn.execute(converted_query, *params)
    else:
        return await conn.execute(query, params)


async def fetchone(conn, query: str, params: tuple = ()):
    """Fetch one row with automatic placeholder conversion."""
    converted_query = sql(query)

    if settings.use_postgres:
        row = await conn.fetchrow(converted_query, *params)
        return dict(row) if row else None
    else:
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def fetchall(conn, query: str, params: tuple = ()):
    """Fetch all rows with automatic placeholder conversion."""
    converted_query = sql(query)

    if settings.use_postgres:
        rows = await conn.fetch(converted_query, *params)
        return [dict(row) for row in rows]
    else:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetchval(conn, query: str, params: tuple = ()):
    """Fetch a single value with automatic placeholder conversion."""
    converted_query = sql(query)

    if settings.use_postgres:
        return await conn.fetchval(converted_query, *params)
    else:
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else None
