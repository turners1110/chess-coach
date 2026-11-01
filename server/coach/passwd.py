"""Prints an argon2id hash for COACH_PASSWORD_HASH: python -m coach.passwd"""

import getpass

from argon2 import PasswordHasher

if __name__ == "__main__":
    pw = getpass.getpass("New password: ")
    if pw != getpass.getpass("Repeat: ") or len(pw) < 8:
        raise SystemExit("Passwords differ or are shorter than 8 characters.")
    # Single quotes stop Docker Compose from expanding the $ signs in the hash
    print("Add this line to .env:\nCOACH_PASSWORD_HASH='" + PasswordHasher().hash(pw) + "'")
