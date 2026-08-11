from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select

from aisearcharab_api.config import get_settings
from aisearcharab_api.database import get_session_factory
from aisearcharab_api.models import User
from aisearcharab_api.security import PasswordPolicyError, hash_password, normalize_email


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the first AISearcharab owner account after migrations are applied.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    password = getpass.getpass("Owner password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("password confirmation does not match", file=sys.stderr)
        return 2
    try:
        encoded = hash_password(password, minimum_length=settings.password_min_length)
    except PasswordPolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    with get_session_factory()() as session:
        active_owners = session.scalar(select(func.count()).select_from(User).where(User.role == "owner", User.is_active.is_(True))) or 0
        if active_owners:
            print("an active owner already exists; use the admin console for additional users", file=sys.stderr)
            return 3
        if session.scalar(select(User).where(User.email == email)) is not None:
            print("email already exists", file=sys.stderr)
            return 3
        session.add(User(email=email, display_name=args.name.strip(), role="owner", password_hash=encoded))
        session.commit()
    print("owner account created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
