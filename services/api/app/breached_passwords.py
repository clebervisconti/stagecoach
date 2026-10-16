"""Offline common / breached-password denylist.

Have I Been Pwned's range API is free but needs the network, so it is not
used here. This list is a local stand-in (no paid service, no egress).
"""

from __future__ import annotations

COMMON_PASSWORDS = frozenset(
    {
        "000000",
        "111111",
        "123123",
        "123456",
        "1234567",
        "12345678",
        "123456789",
        "1234567890",
        "123qwe",
        "1q2w3e4r",
        "abc123",
        "admin",
        "admin123",
        "letmein",
        "monkey",
        "passw0rd",
        "password",
        "password1",
        "password12",
        "password123",
        "qwerty",
        "qwerty123",
        "qwertyuiop",
        "welcome",
        "welcome1",
        "iloveyou",
        "dragon",
        "baseball",
        "football",
        "master",
        "sunshine",
        "princess",
        "starwars",
        "login",
        "adminadmin",
        "root",
        "toor",
        "pass",
        "pass1234",
        "changeme",
        "secret",
        "secret123",
        "stagecoach",
        "stagecoach1",
    }
)


def is_breached_password(password: str) -> bool:
    compact = "".join(password.lower().split())
    return compact in COMMON_PASSWORDS
