from argon2 import PasswordHasher, exceptions


_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hash a plaintext password using argon2 and return the encoded hash."""
    return _ph.hash(plain)


def verify_password(plain: str, pass_hash: str) -> bool:
    """Verify `plain` against `pass_hash`.

    Returns True when the password matches, False when it does not match.
    If `pass_hash` is malformed (`InvalidHash`) the exception is re-raised
    so the caller can treat it as a real authentication error (not a simple
    "wrong password").
    """
    try:
        return _ph.verify(pass_hash, plain)
    except exceptions.VerifyMismatchError:
        # Wrong password
        return False
    except exceptions.InvalidHash:
        # Malformed hash in DB — do not mask
        raise

