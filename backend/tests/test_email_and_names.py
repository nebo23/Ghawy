"""Unit tests for the signup guards (fake-email filtering) and name splitting.

The repo has no test runner wired up, so this file works two ways:
  * `pytest backend/tests/test_email_and_names.py` if pytest is available
  * `python3 backend/tests/test_email_and_names.py` — runs the same assertions
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.disposable_emails import (  # noqa: E402
    is_disposable_email,
    is_fake_email_pattern,
)
from app.services.name_utils import compose_full_name, split_full_name  # noqa: E402


# ─── Blocked: disposable domains ────────────────────────────
BLOCKED_DOMAINS = [
    "someone@mailinator.com",
    "someone@foo.mailinator.com",       # subdomain
    "abc123@10minutemail.com",
    "mohamed@web-library.net",
    "user1234@guerrillamail.com",
    "hello@yopmail.com",
    "x9y8z7@temp-mail.org",
    "mohamed.salah@sharklasers.com",
    "realname@mail.tm",
    "someone@minuteinbox.com",
]

# ─── Blocked: obviously fake local parts ────────────────────
BLOCKED_PATTERNS = [
    "test@gmail.com",
    "TEST@gmail.com",                   # case-insensitive
    "test.user+1@gmail.com",            # dots + tag normalise to "testuser"
    "testing@outlook.com",
    "demo@yahoo.com",
    "asdf@gmail.com",
    "qwerty@hotmail.com",
    "123456@gmail.com",                 # all digits
    "aaaa@gmail.com",                   # one repeated character
    "zz@gmail.com",                     # two characters
    "a@gmail.com",                      # one character
    "admin@gmail.com",
    "dummy@gmail.com",
    "hr@somecompany.com.eg",     # 2-char local parts are rejected by design
]

# ─── Must pass: real, ordinary addresses ────────────────────
ALLOWED = [
    "mohamed.salah@gmail.com",
    "ahmed@outlook.com",
    "sam@gmail.com",                    # short real name, NOT "sample"
    "ali@yahoo.com",
    "testa@gmail.com",                  # starts with "test" but isn't it
    "protest@gmail.com",                # contains "test" as a substring
    "abcarpentry@gmail.com",            # contains "abc" as a substring
    "m.abdelrahman@student.cu.edu.eg",
    "nour99@gmail.com",
    "a7med.mahmoud@gmail.com",
    "kareem_2001@hotmail.com",
]


def test_disposable_domains_blocked():
    for email in BLOCKED_DOMAINS:
        assert is_disposable_email(email), email


def test_fake_local_parts_blocked():
    for email in BLOCKED_PATTERNS:
        assert is_fake_email_pattern(email), email


def test_real_emails_pass():
    for email in ALLOWED:
        assert not is_disposable_email(email), email
        assert not is_fake_email_pattern(email), email


def test_split_full_name():
    assert split_full_name("محمد أحمد") == ("محمد", "أحمد")
    assert split_full_name("محمد أحمد علي") == ("محمد", "أحمد علي")
    assert split_full_name("Mohamed") == ("Mohamed", "")
    assert split_full_name("  Mohamed   Salah  ") == ("Mohamed", "Salah")
    assert split_full_name("") == ("", "")
    assert split_full_name(None) == ("", "")


def test_compose_full_name():
    assert compose_full_name("محمد", "أحمد") == "محمد أحمد"
    assert compose_full_name("Mohamed", "") == "Mohamed"
    assert compose_full_name("", "Salah") == "Salah"
    assert compose_full_name("  Mohamed  ", "  Salah  ") == "Mohamed Salah"


def test_split_compose_roundtrip():
    for name in ["محمد أحمد علي", "Mohamed Salah", "Nour"]:
        assert compose_full_name(*split_full_name(name)) == name


if __name__ == "__main__":
    passed = 0
    for fn_name, fn in sorted(globals().items()):
        if fn_name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {fn_name}")
    print(f"\n{passed} test functions passed")
