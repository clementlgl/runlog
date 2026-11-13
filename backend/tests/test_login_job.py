from dataclasses import dataclass

from app import login_job
from app.login_job import LoginManager
from mifit.errors import NotificationRequiredError


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
