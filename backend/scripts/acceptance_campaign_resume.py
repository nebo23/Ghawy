"""Acceptance: an email campaign survives its SMTP connection dying mid-send.

A campaign to the full roster is ~2,000 messages with a 4-9s pause between
each — three and a half hours on ONE held-open SMTP connection. No provider
keeps a connection alive that long, so the interesting question was never
"does it send", it is "what happens at message 400 when the socket goes away".

Before this pass the answer was: the per-recipient `except` swallowed the
disconnect, marked that address failed, and carried on writing into a dead
socket — so every remaining member got a `failed:` row. Then `load_sent_log`
returned failures *as well as* successes, so re-running the campaign skipped
them. The recovery path is what made the loss permanent.

The four cases below are driven against a real SMTP server on localhost that
this file starts and kills on purpose — not a mock of smtplib:

  T1  the connection is dropped after 10 messages while the server keeps
      listening (an idle timeout / connection cap — the common case). The
      remaining 20 must still arrive: the sender reconnects and continues.
  T2  the server is killed outright after 10 messages and never comes back.
      The run must END, with the 20 unsent members logged `failed:`.
  T3  re-running T2's campaign against a healthy server must attempt exactly
      those 20 and skip the 10 that already succeeded.
  T4  one address that gets a hard 550 fails ALONE — the other 29 still go.

T2+T3 together are the whole point: a campaign that stopped halfway is now
finished by running it again.

Non-destructive: a throwaway SQLite file holds the sent-log, and nothing
touches the real database or sends real mail. Run it inside the image:

    docker exec ghawy_backend python scripts/acceptance_campaign_resume.py
"""
import os
import ssl
import socket
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force, never setdefault: this runs inside the image, where the real Gmail
# credentials are already in the environment. A `setdefault` here would leave
# them in place and point the test at the live mail server.
os.environ["SMTP_HOST"] = "127.0.0.1"
os.environ["SMTP_USER"] = "campaign@test.local"
os.environ["SMTP_PASSWORD"] = "test-password"
os.environ["SMTP_FROM_EMAIL"] = "campaign@test.local"

from sqlalchemy import create_engine                              # noqa: E402
from sqlalchemy.orm import sessionmaker                           # noqa: E402

from app.models import EmailCampaignSend                          # noqa: E402
import app.services.email_campaign_service as ecs                 # noqa: E402


# ══════════════════════════════════════════════════════════════
#  A real SMTP server we can drop connections on
# ══════════════════════════════════════════════════════════════

class FakeSMTP(threading.Thread):
    """Enough SMTP to satisfy smtplib: EHLO, STARTTLS, AUTH PLAIN, MAIL, RCPT,
    DATA, QUIT.

    `drop_after`  — close the CONNECTION after N accepted messages but keep
                    listening. This is the idle-timeout / connection-cap shape.
    `die_after`   — close the connection AND stop listening. A full outage.
    `refuse`      — addresses that get a hard 550 at RCPT TO.
    """

    def __init__(self, certfile, keyfile, drop_after=None, die_after=None, refuse=()):
        super().__init__(daemon=True)
        self.certfile, self.keyfile = certfile, keyfile
        self.drop_after, self.die_after = drop_after, die_after
        self.refuse = {a.lower() for a in refuse}
        self.accepted = []          # recipients that got a 250 after DATA
        self.connections = 0        # how many times the sender had to connect
        self._stop = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.3)
        self.port = self.sock.getsockname()[1]

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.connections += 1
            try:
                self._serve(conn)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        try:
            self.sock.close()
        except Exception:
            pass

    def _serve(self, conn):
        conn.settimeout(10)
        rf = conn.makefile("rb")

        def reply(text):
            conn.sendall((text + "\r\n").encode())

        reply("220 fake.local ESMTP")
        while True:
            line = rf.readline()
            if not line:
                return
            cmd = line.decode("utf-8", "replace").strip()
            up = cmd.upper()

            if up.startswith(("EHLO", "HELO")):
                reply("250-fake.local\r\n250-STARTTLS\r\n250-AUTH PLAIN\r\n250 OK")
            elif up.startswith("STARTTLS"):
                reply("220 Ready to start TLS")
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(self.certfile, self.keyfile)
                conn = ctx.wrap_socket(conn, server_side=True)
                rf = conn.makefile("rb")
            elif up.startswith("AUTH"):
                reply("235 2.7.0 Authentication successful")
            elif up.startswith("MAIL FROM"):
                reply("250 OK")
            elif up.startswith("RCPT TO"):
                addr = cmd.split("<", 1)[-1].split(">", 1)[0].lower()
                self._pending = addr
                if addr in self.refuse:
                    reply("550 5.1.1 No such user here")
                else:
                    reply("250 OK")
            elif up.startswith("DATA"):
                reply("354 End data with <CR><LF>.<CR><LF>")
                while True:
                    d = rf.readline()
                    if not d or d.strip() == b".":
                        break
                self.accepted.append(self._pending)
                reply("250 2.0.0 Ok: queued")
                n = len(self.accepted)
                if self.die_after and n >= self.die_after:
                    self.stop()          # full outage: stop listening too
                    return
                if self.drop_after and n % self.drop_after == 0:
                    return               # drop just this connection
            elif up.startswith("RSET"):
                reply("250 OK")
            elif up.startswith("QUIT"):
                reply("221 Bye")
                return
            else:
                reply("250 OK")


def make_cert(tmpdir):
    cert = os.path.join(tmpdir, "c.pem")
    key = os.path.join(tmpdir, "k.pem")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", key, "-out", cert, "-days", "1", "-subj", "/CN=127.0.0.1"],
        check=True, capture_output=True,
    )
    return cert, key


# ══════════════════════════════════════════════════════════════
#  Harness
# ══════════════════════════════════════════════════════════════

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def recipients(n, bad=None):
    out = [{"Name": f"عضو {i}", "Email": f"m{i}@test.local",
            "Governorate": "Cairo", "Country": "Egypt"} for i in range(1, n + 1)]
    if bad:
        out[bad - 1]["Email"] = "nosuchuser@test.local"
    return out


def content():
    return ecs.EmailContent(
        subject_template="اختبار {first_name}",
        body_html="<p>مرحبا {first_name}</p>",
    )


def session_factory(tmpdir, tag):
    engine = create_engine(f"sqlite:///{os.path.join(tmpdir, tag + '.db')}")
    EmailCampaignSend.__table__.create(engine, checkfirst=True)
    return sessionmaker(bind=engine)


def log_rows(SF, campaign):
    db = SF()
    try:
        return [(r.email, r.status) for r in
                db.query(EmailCampaignSend)
                  .filter(EmailCampaignSend.campaign_id == campaign).all()]
    finally:
        db.close()


def main():
    tmpdir = tempfile.mkdtemp(prefix="campaign-resume-")
    cert, key = make_cert(tmpdir)

    # Fast: the 4-9s human-rate pause and the reconnect backoff are what make a
    # real campaign take hours; neither is under test here.
    ecs.MIN_DELAY_SECONDS = 0.1
    ecs.MAX_DELAY_SECONDS = 0.1
    ecs.RECONNECT_BACKOFF_SECONDS = 0.1

    # ── T1: connection dropped every 10 messages, server stays up ──────────
    print("\nT1  connection dropped after 10 messages (server keeps listening)")
    srv = FakeSMTP(cert, key, drop_after=10)
    srv.start()
    os.environ["SMTP_PORT"] = str(srv.port)
    SF = session_factory(tmpdir, "t1")
    r1 = ecs.send_campaign(recipients(30), content(), "t1", test_mode=False,
                           session_factory=SF)
    srv.stop()
    check("all 30 delivered despite the drops",
          r1.success_count == 30 and r1.fail_count == 0,
          f"sent={r1.success_count} failed={r1.fail_count}")
    check("the server saw more than one connection",
          srv.connections >= 3, f"connections={srv.connections}")
    check("30 recipients actually reached the server",
          len(srv.accepted) == 30, f"accepted={len(srv.accepted)}")

    # ── T2: server killed at message 10 and never returns ─────────────────
    print("\nT2  server killed after 10 messages, never comes back")
    srv2 = FakeSMTP(cert, key, die_after=10)
    srv2.start()
    os.environ["SMTP_PORT"] = str(srv2.port)
    SF2 = session_factory(tmpdir, "t2")
    r2 = ecs.send_campaign(recipients(30), content(), "t2", test_mode=False,
                           session_factory=SF2)
    srv2.stop()
    rows2 = log_rows(SF2, "t2")
    sent_rows = [e for e, s in rows2 if s == "sent"]
    failed_rows = [e for e, s in rows2 if s.startswith("failed:")]
    check("the run ended instead of hanging", True, f"sent={r2.success_count} failed={r2.fail_count}")
    check("10 sent rows written", len(sent_rows) == 10, f"sent rows={len(sent_rows)}")
    check("20 failed rows written", len(failed_rows) == 20, f"failed rows={len(failed_rows)}")
    # getattr, so this same file can be pointed at the pre-fix service to
    # measure what it used to do (that build has no such field).
    check("the downed transport is reported",
          getattr(r2, "transport_failed", False),
          f"transport_error={getattr(r2, 'transport_error', '')[:60]!r}")

    # ── T3: re-run the SAME campaign against a healthy server ─────────────
    print("\nT3  re-running the stalled campaign against a healthy server")
    srv3 = FakeSMTP(cert, key)
    srv3.start()
    os.environ["SMTP_PORT"] = str(srv3.port)
    r3 = ecs.send_campaign(recipients(30), content(), "t2", test_mode=False,
                           session_factory=SF2)
    srv3.stop()
    check("exactly the 20 unsent members were attempted",
          r3.success_count == 20, f"sent={r3.success_count}")
    check("the 10 already delivered were skipped",
          r3.skipped_already_sent == 10, f"skipped={r3.skipped_already_sent}")
    check("nobody was mailed twice",
          sorted(srv3.accepted) == sorted(set(srv3.accepted)) and len(srv3.accepted) == 20,
          f"accepted={len(srv3.accepted)}")
    all_sent = {e for e, s in log_rows(SF2, "t2") if s == "sent"}
    check("all 30 members now hold a sent row", len(all_sent) == 30, f"sent={len(all_sent)}")

    # ── T4: one hard 550 must not take the campaign with it ───────────────
    print("\nT4  one address gets a hard 550")
    srv4 = FakeSMTP(cert, key, refuse=["nosuchuser@test.local"])
    srv4.start()
    os.environ["SMTP_PORT"] = str(srv4.port)
    SF4 = session_factory(tmpdir, "t4")
    r4 = ecs.send_campaign(recipients(30, bad=7), content(), "t4", test_mode=False,
                           session_factory=SF4)
    srv4.stop()
    check("the other 29 still went", r4.success_count == 29, f"sent={r4.success_count}")
    check("the bad address failed alone", r4.fail_count == 1, f"failed={r4.fail_count}")
    check("one connection was enough — no needless reconnects",
          srv4.connections == 1, f"connections={srv4.connections}")

    print("\n" + "=" * 60)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        for n in failed:
            print(f"  FAILED: {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
