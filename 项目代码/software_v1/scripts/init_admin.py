"""Create the first administrator from environment variables."""

import os

from sqlalchemy import select

from app.db.session import dispose_database, initialize_database
from app.models import SysUser
from app.security import hash_password


def main() -> None:
    username = os.getenv("INITIAL_ADMIN_USERNAME")
    password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not username or not password:
        raise RuntimeError("INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD are required")
    factory = initialize_database()
    try:
        with factory() as db:
            if db.scalar(select(SysUser.id).where(SysUser.username == username)) is not None:
                raise RuntimeError("administrator username already exists")
            db.add(SysUser(
                username=username,
                display_name="System Administrator",
                password_hash=hash_password(password),
                role="admin",
                status="active",
            ))
            db.commit()
    finally:
        dispose_database()


if __name__ == "__main__":
    main()
