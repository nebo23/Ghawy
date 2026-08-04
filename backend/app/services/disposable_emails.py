"""Disposable / temporary email blocking — by domain and by local-part pattern.

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
    # additional throwaway providers seen in the wild
    "temp-mail.net", "tempmail.net", "tempmail.dev", "tempmailer.com",
    "tmpmail.org", "tmpmail.net", "tmail.com", "tmails.net", "minuteinbox.com",
    "mailtemp.net", "mail-temporaire.fr", "mailexpire.com", "spambox.us",
    "spambog.com", "spamfree24.org", "spam.la", "deadaddress.com",
    "discard.email", "discardmail.com", "incognitomail.com", "anonbox.net",
    "anonymbox.com", "kurzepost.de", "objectmail.com", "proxymail.eu",
    "rcpt.at", "trash-mail.at", "trashinbox.com", "wegwerfemail.de",
    "mailde.de", "mailde.info", "nospam.ze.tc", "nomail.xl.cx",
    "fakemail.net", "fakemailgenerator.net", "generator.email", "internetkeno.com",
    "vomoto.com", "gettempmail.com", "tempail.com", "tempsky.com",
    "throwawaymail.net", "throam.com", "trbvm.com", "byom.de",
    "mailforspam.com", "mvrht.com", "veryrealemail.com", "e4ward.com",
    "boximail.com", "clrmail.com", "crazymailing.com", "cust.in",
    "mailbox52.ga", "mail7.io", "mailtothis.com", "mailnull.com",
    "meltmail.com", "mytrashmail.com", "nowmymail.com", "oneoffmail.com",
    "put2.net", "quickinbox.com", "rppkn.com", "s0ny.net",
    "shitmail.me", "sofort-mail.de", "spamavert.com", "tafmail.com",
    "thankyou2010.com", "tilien.com", "tmail.ws", "trash2009.com",
    "wh4f.org", "willselfdestruct.com", "yepmail.net", "zoemail.net",
    "cachedot.net", "emailfake.com", "emailtemporanea.net", "mail.tm",
    "edu.pl.ua", "instantemailaddress.com", "mailhole.de", "mailisp.net",
    "spaml.com", "smashmail.de", "muellmail.com", "spoofmail.de",
}

# ─── Obviously-fake local parts ─────────────────────────────
# The other half of the daily fake-signup traffic isn't a throwaway provider at
# all — it's test@gmail.com, asdf@outlook.com, 123456@yahoo.com. These are the
# local parts (the bit before the @) we refuse outright.
#
# Matching is EXACT against this set (never a substring) so that a real short
# name is never caught: "sam@…" is fine even though "sample" is listed, and
# "testa@…" is fine even though "test" is. The numeric/repeated-character rules
# below are the only structural ones.
FAKE_LOCAL_PARTS = {
    "test", "tests", "testing", "testuser", "test1", "test2", "test123",
    "testtest", "testmail", "testemail", "testaccount",
    "demo", "demouser", "sample", "example", "examples",
    "asdf", "asd", "asdfg", "asdfgh", "asdasd", "qwe", "qwer", "qwerty",
    "qwertyui", "zxc", "zxcv", "zxcvbn", "abc", "abcd", "abcde", "aaa",
    "xxx", "xyz", "temp", "tempuser", "fake", "fakeuser", "dummy",
    "noreply", "no-reply", "donotreply", "do-not-reply", "nobody", "none",
    "null", "undefined", "unknown", "anonymous", "user", "username",
    "admin", "administrator", "root", "guest", "someone", "somebody",
    "trial", "check", "checking", "tester", "testerr", "mytest", "testtt",
}


def _normalize_local_part(email: str) -> str:
    """Local part, lowercased, with Gmail-style dots and +tags removed.

    test.user+1@gmail.com -> "testuser"; the +tag is stripped for every
    provider (it's a tagging convention everywhere), dots only matter for the
    Gmail-style aliasing this is meant to catch.
    """
    local = email.rsplit("@", 1)[0] if "@" in email else email
    local = local.strip().lower()
    local = local.split("+", 1)[0]
    return local.replace(".", "")


def is_fake_email_pattern(email: str) -> bool:
    """True if the local part is an obviously throwaway/placeholder identity."""
    local = _normalize_local_part(email)
    if not local:
        return False

    # Exact match against the curated list (case- and dot-insensitive).
    if local in FAKE_LOCAL_PARTS:
        return True

    # All digits: 123@, 111111@ — never a real person's mailbox name.
    if local.isdigit():
        return True

    # One or two characters: too short to be a genuine address here.
    if len(local) <= 2:
        return True

    # The same character repeated: aaaa@, zzzz@, 0000@.
    if len(set(local)) == 1:
        return True

    return False


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
