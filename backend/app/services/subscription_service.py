"""Subscription window arithmetic — one rule, in one place.

Every grant of subscription time (Kashier renewal, Instapay/manual approval,
admin extension, legacy promo, birthday gift) goes through
`extend_subscription`. The rule never changes: time is ADDED to whatever the
member still has, it is never used to overwrite it. A member with 5 days left
who buys a month ends on day 35, not day 30.

This lived as a copy-pasted two-liner before, and three of the five copies had
dropped the "extend" half and were assigning `now + days` outright — silently
confiscating the remainder from anyone who renewed early. Adding time is a
money-handling operation; it gets exactly one implementation.
"""
from datetime import datetime, timedelta
from typing import Optional


def extend_subscription(user, days: int, now: Optional[datetime] = None) -> datetime:
    """Add `days` to a member's subscription and return the new end date.

    Extends from the current `end_at` while it is still in the future, and from
    `now` once the subscription has lapsed (or never existed) — so an early
    renewal keeps the unused remainder, while a late one doesn't retroactively
    credit the gap the member wasn't paying for.

    Also flips `is_active` on, since every caller granting time wants the
    member usable afterwards.
    """
    now = now or datetime.utcnow()
    base = user.end_at if (user.end_at and user.end_at > now) else now
    user.end_at = base + timedelta(days=days)
    user.is_active = True
    return user.end_at
