"""Generate secrets locally; never read, request or print an API key."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env already exists; left unchanged')
password = secrets.token_hex(24)
text = (root / '.env.example').read_text()
text = text.replace('JWT_SECRET=\n', f'JWT_SECRET={secrets.token_urlsafe(48)}\n')
text = text.replace('POSTGRES_PASSWORD=\n', f'POSTGRES_PASSWORD={password}\n')
text = text.replace('DATABASE_URL=\n', f'DATABASE_URL=postgresql+psycopg://watchtower:{password}@postgres:5432/watchtower\n')
with target.open('x', encoding='utf-8') as stream:
    stream.write(text)
target.chmod(0o600)
print('Created .env with local generated secrets. Add your existing OpenAI key using your editor.')
