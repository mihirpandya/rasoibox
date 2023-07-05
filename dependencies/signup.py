from random import random


def generate_verification_code() -> str:
    return "{0:x}".format(int(random() * 1_000_000))
