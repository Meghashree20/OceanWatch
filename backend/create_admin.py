
import asyncio
from datetime import datetime, timezone
from getpass import getpass
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.db.mongodb import close_mongo_connection, connect_to_mongo, db_client
from app.models.user import User
from app.schemas.auth import SignupRequest


DEFAULT_EMAIL = "admin@oceanwatch.com"
DEFAULT_FULL_NAME = "OceanWatch Admin"


async def create_admin(email: str, password: str) -> None:
    request = SignupRequest(
        full_name=DEFAULT_FULL_NAME,
        email=email,
        password=password,
        password_confirmation=password,
    )
    normalized_email = str(request.email)

    await connect_to_mongo()
    try:
        db = db_client.db

        existing = await db.users.find_one({"email": normalized_email})

        if existing:
            print("Admin account already exists!")
            return

        now = datetime.now(timezone.utc)
        user = User(
            user_id=str(uuid4()),
            full_name=DEFAULT_FULL_NAME,
            email=normalized_email,
            password_hash=hash_password(password),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        try:
            await db.users.insert_one(user.model_dump())
        except DuplicateKeyError:
            print("Admin account already exists!")
            return

        print("Admin account created successfully!")
        print("Email:", normalized_email)
    finally:
        await close_mongo_connection()


def main() -> None:
    email = input(f"Admin email [{DEFAULT_EMAIL}]: ").strip() or DEFAULT_EMAIL
    password = getpass("Admin password: ")
    password_confirmation = getpass("Confirm admin password: ")
    if password != password_confirmation:
        raise ValueError("Passwords do not match")
    asyncio.run(create_admin(email, password))


if __name__ == "__main__":
    main()
