import string
import random

def random_str(N: int) -> str:
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(N))
