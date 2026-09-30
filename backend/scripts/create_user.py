"""Add or update a sign-in account. There is no public sign-up — this script is
the only way an account comes into existence.

    python -m scripts.create_user <username> "<Full Name>" [user|admin]

It prompts for the password, twice, without echoing it. To run it
non-interactively (a setup script, or `docker compose exec` without a TTY), set
SF_NEW_PASSWORD instead:

    docker compose exec -e SF_NEW_PASSWORD='...' app \
        python -m scripts.create_user alok "Alok" admin

The password is never accepted as a command-line argument: arguments land in
shell history and are visible in `ps` to every user on the box. Whichever way it
arrives it is hashed immediately and the plain value is never stored, logged, or
printed.

Roles: 'user' sees only their own bookings, 'admin' sees all.

Re-running for an existing username updates that person's name, role and
password, and signs them out everywhere — a password change should not leave an
old session alive.

Rollback:
    -- back up first
    CREATE TABLE bk_users_YYYYMMDD AS SELECT * FROM users;
    -- then
    DELETE FROM users WHERE username = '<username>';
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.services import security  # noqa: E402

USAGE = 'Usage: python -m scripts.create_user <username> "<Full Name>" [user|admin]'
ROLES = ("user", "admin")


def _read_password() -> str:
    """From the environment if set, otherwise prompt twice. Never echoed."""
    from_env = os.environ.get("SF_NEW_PASSWORD", "")
    if from_env:
        return from_env

    if not sys.stdin.isatty():
        raise ValueError(
            "No TTY to prompt on. Set SF_NEW_PASSWORD for a non-interactive run."
        )

    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise ValueError("The two passwords do not match.")
    return first


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(USAGE, file=sys.stderr)
        return 1

    username = args[0].strip().lower()
    name = args[1].strip()
    role = (args[2].strip().lower() if len(args) > 2 else "user")

    if not username or not name:
        print(USAGE, file=sys.stderr)
        return 1
    if role not in ROLES:
        print(f"Role must be one of: {', '.join(ROLES)}.", file=sys.stderr)
        return 1

    try:
        password = _read_password()
        hashed = security.hash_password(password)
    except ValueError as exc:
        # The message describes the rule, never the value.
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        password = ""  # noqa: F841 - drop the plain value as early as possible

    db.open_pool()
    try:
        row = db.fetch_one(
            """
            INSERT INTO users (username, password_hash, name, role)
                 VALUES (%s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash,
                        name          = EXCLUDED.name,
                        role          = EXCLUDED.role,
                        is_active     = TRUE
              RETURNING id, (xmax = 0) AS was_inserted
            """,
            (username, hashed, name, role),
        )

        if not row["was_inserted"]:
            # Password changed: kill any session still running under it.
            killed = security.delete_sessions_for_user(row["id"])
            print(f'Updated "{username}" (role: {role}); signed out {killed} session(s).')
        else:
            print(f'Created "{username}" (role: {role}).')
    finally:
        db.close_pool()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
