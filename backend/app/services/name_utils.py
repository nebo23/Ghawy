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
    """Build the display name the rest of the app reads.

    Sanitizes as it composes: every path that sets a name goes through here, so
    this is the one place that has to be right.
    """
    joined = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
    return clean_display_name(joined)

# Characters a spreadsheet reads as the start of a formula. A name is exported
# to CSV by the admin payments report, so one beginning with any of these is
# code in the admin's spreadsheet rather than text. See also the escaping in
# routers/admin.py — this stops it being stored, that stops it being emitted.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Everything below U+0020 plus the C1 range and the bidi/zero-width tricks.
# None of these belong in a display name, and several of them exist purely to
# make one string look like another.
_CONTROL_CHARS = dict.fromkeys(
    list(range(0x00, 0x20)) + [0x7F]
    + list(range(0x80, 0xA0))
    + [0x200B, 0x200C, 0x200D, 0x200E, 0x200F,
       0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
       0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF]
)


def clean_display_name(value: str | None, limit: int = 80) -> str:
    """Make a client-supplied name safe to store and cheap to render.

    Display names reach innerHTML on pages all over the site (notification
    bodies, DM previews, member lists, the admin payments queue) and a CSV in
    the admin's spreadsheet. Registration used to store them raw — the only
    check was len >= 2 — while PUT /profile/me already stripped markup, so
    signing up was simply the unguarded door into the same field.

    The rendering side escapes now, which is the real fix; this means a single
    missed escape anywhere is no longer a working payload. Angle brackets go,
    because they are what turns text into markup and no name needs them.
    Apostrophes stay: "Mu'men" and "MOH'D" are real members' names.
    """
    cleaned = (value or "").translate(_CONTROL_CHARS).replace("<", "").replace(">", "")
    cleaned = " ".join(cleaned.split())
    while cleaned[:1] in FORMULA_PREFIXES:
        cleaned = cleaned[1:].lstrip()
    return cleaned[:limit]
