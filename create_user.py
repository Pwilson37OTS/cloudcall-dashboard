"""Utility to add or update a user in users.json."""
import json
import sys
import bcrypt
from pathlib import Path

USERS_FILE = Path(__file__).parent / "users.json"


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {"users": {}}


def save_users(data):
    USERS_FILE.write_text(json.dumps(data, indent=2))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main():
    if len(sys.argv) < 3:
        print("Usage: python create_user.py <username> <password> [admin]")
        print("  Add 'admin' as third arg to grant admin role")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    role = "admin" if len(sys.argv) > 3 and sys.argv[3] == "admin" else "manager"

    data = load_users()
    data["users"][username] = {
        "password_hash": hash_password(password),
        "role": role,
    }
    save_users(data)
    print(f"User '{username}' saved with role '{role}'")


if __name__ == "__main__":
    main()
