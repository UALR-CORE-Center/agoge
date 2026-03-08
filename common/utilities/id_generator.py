import random
import string
import uuid


class IdGenerator:
    @classmethod
    def build_id(cls, length: int = 10) -> str:
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

    @classmethod
    def join_code(cls) -> str:
        return ''.join(str(random.randint(0, 9)) for _ in range(0, 6))

    @classmethod
    def discriminator(cls) -> str:
        return f"{random.randint(0, 9999):04d}"

    @classmethod
    def uuid(cls) -> str:
        return str(uuid.uuid4().hex)
