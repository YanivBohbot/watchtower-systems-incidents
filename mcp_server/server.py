"""Real MCP stdio server. Only protocol messages go to stdout."""
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

server = FastMCP('WatchTower Tickets')
database = Path(os.environ.get('TICKET_DB_PATH', './data/tickets.db'))
database.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(database) as connection:
    connection.execute('CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL)')


def connect():
    db = sqlite3.connect(database, timeout=10)
    db.row_factory = sqlite3.Row
    return db


@server.tool()
def search_tickets(query: str) -> list[dict]:
    """Search up to ten tickets by a title substring."""
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT id, title FROM tickets WHERE title LIKE ? LIMIT 10', ('%' + query[:200] + '%',))]


@server.tool()
def get_ticket(ticket_id: str) -> dict:
    """Read a ticket by its exact ID."""
    with connect() as db:
        row = db.execute('SELECT id, title, body FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        return dict(row) if row else {'error': 'not_found'}


@server.tool()
def create_ticket(idempotency_key: str, title: str, body: str) -> dict:
    """Create a ticket once per approved investigation. Called by workflow, not agent."""
    if not idempotency_key or len(idempotency_key) > 200 or len(title) > 200 or len(body) > 100_000:
        raise ValueError('Invalid ticket payload')
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?)', (str(uuid4()), idempotency_key, title, body))
        row = db.execute('SELECT id, title FROM tickets WHERE idempotency_key = ?', (idempotency_key,)).fetchone()
        return dict(row)


if __name__ == '__main__':
    server.run(transport='stdio')
