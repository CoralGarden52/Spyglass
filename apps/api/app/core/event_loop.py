import asyncio


def database_event_loop() -> asyncio.AbstractEventLoop:
    """Psycopg async requires a selector loop on Windows (also supported on Linux)."""
    return asyncio.SelectorEventLoop()
