"""Inyecta una sesion de prueba para E2E testing."""
import hashlib, sqlite3, secrets
from datetime import datetime, timezone, timedelta

token = "e15247d4c4a94f36a1d3b0c8f5e6d7a8"
token_hash = hashlib.sha256(token.encode()).hexdigest()
session_id = secrets.token_urlsafe(32)
csrf = secrets.token_urlsafe(32)

conn = sqlite3.connect("admin_sessions.db")
conn.execute("DELETE FROM admin_sessions")
conn.execute(
    "INSERT INTO admin_sessions (session_id, token_hash, csrf_token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
    (session_id, token_hash, csrf, datetime.now(timezone.utc).isoformat(),
     (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
)
conn.commit()
conn.close()

print(f"SESSION_ID={session_id}")
print(f"CSRF={csrf}")
