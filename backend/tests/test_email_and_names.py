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
from app.services.name_utils import (  # noqa: E402
    _AR_FIRST_NAMES,
    _COMPOUND_FIRST_NAMES,
    arabic_first_name,
    compose_full_name,
    first_name_token,
    split_full_name,
)


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


def test_compound_first_names_are_not_split():
    """`عبد الرحمن علي` is greeted أهلاً عبد الرحمن, not أهلاً عبد.

    Two words, one first name. Every door that names a member goes through the
    same tokenizer, so this holds for the greeting and for the stored columns.
    """
    assert first_name_token("عبد الرحمن علي") == "عبد الرحمن"
    assert split_full_name("عبد الله محمد") == ("عبد الله", "محمد")
    assert split_full_name("عبد الرحمن علي حسن") == ("عبد الرحمن", "علي حسن")
    assert arabic_first_name("عبد الرحمن علي") == "عبد الرحمن"
    assert arabic_first_name("نور الدين حسن") == "نور الدين"
    # Latin spellings, both as one token and as two
    assert arabic_first_name("Abdelrahman Ali") == "عبد الرحمن"
    assert arabic_first_name("Abdel Salam Ahmed") == "عبد السلام"
    assert split_full_name("Abdel Rahman Ali") == ("Abdel Rahman", "Ali")


def test_a_prefix_never_merges_two_tokens():
    """`Abd El Hameed` is عبد الحميد, and must never become عبد الرحمن.

    `abdel` on its own is a prefix, not a name; the map guesses the commonest
    reading for a bare token, which is fine for a bare token and wrong the
    moment it is allowed to swallow the word after it. Longest join first, and
    a prefix key is skipped outright — a confidently wrong name is worse than
    the truncated one this whole change exists to fix.
    """
    assert arabic_first_name("Abd El Hameed Mohsen") == "عبد الحميد"
    assert arabic_first_name("Abd El Kader Sayed") == "عبد القادر"
    assert arabic_first_name("Seif El Din Tarek") == "سيف الدين"
    assert split_full_name("Abd El Hameed Mohsen") == ("Abd El Hameed", "Mohsen")
    # a bare `Abdel` keeps the map's guess — one token, nothing to swallow
    assert arabic_first_name("Abdel") == "عبد الرحمن"


def test_two_tokens_merge_only_into_a_compound():
    """`Nour Hany` is two people's worth of name, not نورهان."""
    assert split_full_name("Nour Hany") == ("Nour", "Hany")
    assert split_full_name("Salah Ahmed") == ("Salah", "Ahmed")
    assert split_full_name("محمد أحمد علي") == ("محمد", "أحمد علي")


def test_compound_set_is_derived_from_the_map():
    """One source of truth: a compound is a map value with a space in it.

    A second hand-written list is what drifted — the one in
    `email_campaign_service` was missing three names the map produces.
    """
    assert _COMPOUND_FIRST_NAMES == frozenset(
        v for v in _AR_FIRST_NAMES.values() if " " in v
    )
    for name in ("عبد الرؤوف", "عبد المحسن", "عبد المنعم", "عبد السلام", "صلاح الدين"):
        assert name in _COMPOUND_FIRST_NAMES, name
        assert arabic_first_name(f"{name} محمد") == name


def test_one_fallback_word_everywhere():
    """`صديقي` used to be the email-campaign fallback and `صديقنا` everyone
    else's — the same member addressed two ways depending on the sender."""
    from app.services.name_utils import FALLBACK_FIRST_NAME

    assert FALLBACK_FIRST_NAME == "صديقنا"
    try:
        from app.services.email_campaign_service import get_first_name
    except ModuleNotFoundError:      # host run: the email stack needs dotenv/jinja
        return
    assert get_first_name("") == FALLBACK_FIRST_NAME
    assert get_first_name(None) == FALLBACK_FIRST_NAME
    assert get_first_name("عبد الرحمن علي") == "عبد الرحمن"


def test_compose_full_name():
    assert compose_full_name("محمد", "أحمد") == "محمد أحمد"
    assert compose_full_name("Mohamed", "") == "Mohamed"
    assert compose_full_name("", "Salah") == "Salah"
    assert compose_full_name("  Mohamed  ", "  Salah  ") == "Mohamed Salah"


def test_split_compose_roundtrip():
    for name in ["محمد أحمد علي", "Mohamed Salah", "Nour",
                 "عبد الرحمن علي", "Abdel Rahman Ali", "نور الدين حسن"]:
        assert compose_full_name(*split_full_name(name)) == name


if __name__ == "__main__":
    passed = 0
    for fn_name, fn in sorted(globals().items()):
        if fn_name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {fn_name}")
    print(f"\n{passed} test functions passed")
