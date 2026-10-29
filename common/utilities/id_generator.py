import secrets
import string
import uuid


class IdGenerator:
    # Workout IDs and join codes are bearer credentials, so they come from a CSPRNG.
    @classmethod
    def build_id(cls, length: int = 10) -> str:
        return ''.join(secrets.choice(string.ascii_lowercase) for _ in range(length))

    @classmethod
    def join_code(cls) -> str:
        return ''.join(str(secrets.randbelow(10)) for _ in range(0, 6))

    @classmethod
    def discriminator(cls) -> str:
        return f"{secrets.randbelow(10000):04d}"

    @classmethod
    def uuid(cls) -> str:
        return str(uuid.uuid4().hex)
