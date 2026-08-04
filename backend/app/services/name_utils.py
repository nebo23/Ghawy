"""First/last name helpers.

`full_name` stays the single source of truth for display: it is used in 20+
places across the codebase (emails, chat, DMs, the team dashboard, admin), so
splitting the signup form into two inputs must NOT remove it. Instead the two
new columns feed it — full_name is always recomposed from first + last.
"""


def split_full_name(full_name: str | None) -> tuple[str, str]:
    """Split a display name on the FIRST space.

    "محمد أحمد علي" -> ("محمد", "أحمد علي")
    "Mohamed"        -> ("Mohamed", "")
    """
    clean = " ".join((full_name or "").split())
    if not clean:
        return "", ""
    first, _, last = clean.partition(" ")
    return first, last


def compose_full_name(first_name: str | None, last_name: str | None) -> str:
    """Build the display name the rest of the app reads."""
    return f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
