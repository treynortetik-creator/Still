"""Database helpers for PostgreSQL."""
import json


def sql(query: str) -> str:
    """Convert query placeholders to PostgreSQL format.

    Converts:
    - ? placeholders to $1, $2, $3... (PostgreSQL style)
    - datetime('now') to NOW()
    """
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
    """Execute an INSERT and return the new row's ID via RETURNING clause."""
    pg_query = sql(query)
    if 'RETURNING' not in pg_query.upper():
        pg_query = pg_query.rstrip().rstrip(';') + ' RETURNING id'
    result = await conn.fetchval(pg_query, *params)
    return result


async def execute(conn, query: str, params: tuple = ()):
    """Execute a query with automatic placeholder conversion.

    Returns:
        Command tag string (e.g., "DELETE 1", "UPDATE 0")
    """
    converted_query = sql(query)
    return await conn.execute(converted_query, *params)


async def fetchone(conn, query: str, params: tuple = ()):
    """Fetch one row with automatic placeholder conversion."""
    converted_query = sql(query)
    row = await conn.fetchrow(converted_query, *params)
    return dict(row) if row else None


async def fetchall(conn, query: str, params: tuple = ()):
    """Fetch all rows with automatic placeholder conversion."""
    converted_query = sql(query)
    rows = await conn.fetch(converted_query, *params)
    return [dict(row) for row in rows]


async def fetchval(conn, query: str, params: tuple = ()):
    """Fetch a single value with automatic placeholder conversion."""
    converted_query = sql(query)
    return await conn.fetchval(converted_query, *params)


def safe_json(value, default=None):
    """Safely parse a JSON value that may already be deserialized by asyncpg.

    Handles: None, str (parse it), dict/list (return as-is), other (return default).
    """
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default
    return default
