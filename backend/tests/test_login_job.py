from dataclasses import dataclass

from mifit.errors import NotificationRequiredError

from app import login_job
from app.login_job import LoginManager


@dataclass
class FakeSession:
    region: str = "cn"
    user_id: str = "1"


def test_login_returns_url_then_saves_with_forced_region(monkeypatch):
    monkeypatch.setenv("MIFIT_REGION", "de")
    monkeypatch.setattr(login_job, "record_event", lambda *a, **k: None)
    saved = []

    def fake_login(on_qr):
        on_qr("https://account.xiaomi.com/longPolling/login?ticket=x", "qr")
        return FakeSession()

    m = LoginManager(login=fake_login, save=saved.append)
    state, started = m.start()
    assert started and state["login_url"].startswith("https://account.xiaomi.com/")
    for _ in range(100):
        if m.state()["status"] != "waiting":
            break
        import time

        time.sleep(0.01)
    assert m.state()["status"] == "done"
    assert saved[0].region == "de"


def test_security_confirmation_is_surfaced(monkeypatch):
    def fake_login(on_qr):
        on_qr("https://account.xiaomi.com/x", "qr")
        raise NotificationRequiredError("https://account.xiaomi.com/confirm")

    m = LoginManager(login=fake_login, save=lambda s: None)
    m.start()
    import time

    for _ in range(100):
        if m.state()["status"] != "waiting":
            break
        time.sleep(0.01)
    s = m.state()
    assert s["status"] == "error" and s["notification_url"] == "https://account.xiaomi.com/confirm"


def test_session_info_never_exposes_secrets(monkeypatch):
    @dataclass
    class S:
        region: str = "de"
        created_at: str = "2026-11-13T10:00:00Z"
        renewed_at: str | None = None
        service_token: str = "SECRET"
        pass_token: str = "SECRET"

        def is_valid(self):
            return True

        def can_renew(self):
            return True

    monkeypatch.setattr(login_job, "load_session", lambda: S())
    info = login_job.session_info()
    assert info["connected"] and info["region"] == "de"
    assert "SECRET" not in str(info)


def test_expired_link_is_renewed_until_approved(monkeypatch):
    calls = {"request": 0, "poll": 0}

    class Challenge:
        def __init__(self, n):
            self.login_url = f"https://account.xiaomi.com/longPolling/login?ticket={n}"
            self.qr_payload = "qr"

    def fake_request(http, sid, device_id=None):
        calls["request"] += 1
        return Challenge(calls["request"])

    def fake_poll(challenge, http, device_id=None):
        calls["poll"] += 1
        if calls["poll"] < 3:  # the first two links expire
            raise TimeoutError("read timed out")
        return "result"

    monkeypatch.setattr(login_job, "request_qr_login", fake_request)
    monkeypatch.setattr(login_job, "poll_qr_login", fake_poll)
    monkeypatch.setattr(login_job, "exchange_sts", lambda result, sid, http, device_id="": FakeSession())
    urls = []
    session = login_job.login_with_renewal(lambda url, qr: urls.append(url), window_s=5)
    assert isinstance(session, FakeSession)
    assert urls == [f"https://account.xiaomi.com/longPolling/login?ticket={n}" for n in (1, 2, 3)]


def test_security_confirmation_is_not_retried(monkeypatch):
    class Challenge:
        login_url, qr_payload = "https://account.xiaomi.com/x", "qr"

    polls = []
    monkeypatch.setattr(login_job, "request_qr_login", lambda *a, **k: Challenge())

    def poll(*a, **k):
        polls.append(1)
        raise NotificationRequiredError("https://account.xiaomi.com/confirm")

    monkeypatch.setattr(login_job, "poll_qr_login", poll)
    try:
        login_job.login_with_renewal(lambda u, q: None, window_s=5)
    except NotificationRequiredError:
        pass
    assert len(polls) == 1
