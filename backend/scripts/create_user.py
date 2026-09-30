"""Add a sign-in account. There is no public sign-up.

    docker compose exec -e SF_NEW_PASSWORD='...' app \
        python -m scripts.create_user <username> "<Full Name>" [role]

The password is NOT passed as an argument — that would land in shell history
and in `ps`. It is read from SF_NEW_PASSWORD for one command, hashed, and
discarded. The plain value is never stored, never logged, never echoed.

Roles: 'user' sees only their own bookings, 'admin' sees all.
Re-running for an existing username updates that user's password.

Rollback:  DELETE FROM users WHERE username = '<username>';
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.services.security import hash_password  # noqa: E402

USAGE = (
    "Usage: SF_NEW_PASSWORD=... python -m scripts.create_user "
    '<username> "<Full Name>" [user|admin]'
)


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(USAGE, file=sys.stderr)
        return 1

    username, name = args[0].strip().lower(), args[1].strip()
    role = (args[2].strip() if len(args) > 2 else "user").lower()

    if role not in {"user", "admin"}:
        print("Role must be 'user' or 'admin'.", file=sys.stderr)
        return 1

    password = os.environ.get("SF_NEW_PASSWORD", "")
    if not password:
        print(
            "SF_NEW_PASSWORD is not set. Pass it as an environment variable, "
            "not as an argument.",
            file=sys.stderr,
        )
        return 1

    try:
        hashed = hash_password(password)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    db.open_pool()
    try:
        db.execute(
            """
            INSERT INTO users (username, password_hash, name, role)
                 VALUES (%s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash,
                        name          = EXCLUDED.name,
                        role          = EXCLUDED.role
            """,
            (username, hashed, name, role),
        )
    finally:
        db.close_pool()

    print(f'User "{username}" saved (role: {role}).')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
