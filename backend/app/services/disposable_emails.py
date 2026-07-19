"""Disposable / temporary email domain blocklist.

The signup flow was hit by an automated swarm registering hundreds of accounts
through throwaway-mail providers (e.g. web-library.net). Genuine members sign
up with real mailboxes (Gmail, Outlook, Yahoo, university/company domains), so
rejecting known disposable providers at registration stops the flood at the
door without hurting real users.

This is a curated static list on purpose: no external API call is made in the
request path (we learned the hard way not to add blocking network I/O to
request handlers). Add new domains here as they show up in the abuse logs —
`SELECT split_part(email,'@',2) AS d, count(*) FROM users GROUP BY d ORDER BY 2 DESC`.
"""

# Kept lowercase, bare domains. Matched against the email domain and any parent
# domain, so a subdomain like foo.mailinator.com is also caught.
DISPOSABLE_DOMAINS = {
    # seen in the abuse swarm
    "web-library.net",
    # mailinator family
    "mailinator.com", "mailinator.net", "mailinator2.com", "reallymymail.com",
    # 10minutemail / guerrilla / temp-mail family
    "10minutemail.com", "10minutemail.net", "guerrillamail.com",
    "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamail.de", "sharklasers.com", "grr.la", "guerrillamailblock.com",
    "temp-mail.org", "temp-mail.io", "tempmail.com", "tempmailo.com",
    "tempr.email", "tempmail.plus", "tempmailaddress.com",
    # yopmail
    "yopmail.com", "yopmail.net", "yopmail.fr", "cool.fr.nf", "jetable.fr.nf",
    # trash / throwaway
    "trashmail.com", "trashmail.de", "trashmail.net", "wegwerfmail.de",
    "throwawaymail.com", "getnada.com", "nada.email", "dispostable.com",
    "fakeinbox.com", "spamgourmet.com", "mailnesia.com", "mytemp.email",
    "mohmal.com", "emailondeck.com", "moakt.com", "tempinbox.com",
    "burnermail.io", "maildrop.cc", "mailcatch.com", "inboxkitten.com",
    "33mail.com", "spam4.me", "mailsac.com", "harakirimail.com",
    "einrot.com", "fakemailgenerator.com", "maileater.com", "mintemail.com",
    "tempemail.co", "luxusmail.org", "linshiyou.com", "20minutemail.com",
    "mail-temp.com", "emltmp.com", "mailpoof.com", "1secmail.com",
    "1secmail.org", "1secmail.net", "dropmail.me", "10mail.org",
}


def _extract_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower().rstrip(".") if "@" in email else ""


def is_disposable_email(email: str) -> bool:
    """True if the email's domain (or any parent domain) is a known disposable
    provider."""
    domain = _extract_domain(email)
    if not domain:
        return False
    if domain in DISPOSABLE_DOMAINS:
        return True
    # catch subdomains: foo.bar.mailinator.com -> check bar.mailinator.com, mailinator.com
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        if ".".join(parts[i:]) in DISPOSABLE_DOMAINS:
            return True
    return False
