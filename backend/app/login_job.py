"""Xiaomi account login from the web UI, by mifit's QR flow.

``start()`` asks Xiaomi for a login session and returns its URL right away; a
background thread then waits (long poll, ~2 min) for the user to approve it on that
page, and saves the session where the sync reads it. The UI polls ``state()``.

Xiaomi sometimes resolves the account region wrongly (a French account saved as
``cn``, which then reads empty data): ``MIFIT_REGION`` forces it.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

import requests
from mifit.auth.lifetime import record_event
from mifit.auth.qr import SID, exchange_sts, new_device_id, poll_qr_login, request_qr_login
from mifit.auth.session import Session, load_session, save_session
from mifit.errors import NotificationRequiredError

# A Xiaomi login link lives about as long as one long poll (~2 min): too short
# when the user first has to sign in to their Xiaomi account on that page. The
# login keeps asking for a fresh link until this window closes.
LOGIN_WINDOW_S = 10 * 60


@dataclass
class LoginState:
    status: str  # waiting | done | error
    login_url: str | None = None
    link_count: int = 0  # 1 = first link; more = renewed after expiry
    notification_url: str | None = None  # security confirmation asked by Xiaomi
    error: str | None = None
    started_at: float = 0.0
    finished_at: float | None = None


def forced_region() -> str | None:
    return (os.environ.get("MIFIT_REGION") or "").strip().lower() or None


def session_info() -> dict:
    """Whether a usable session is stored, and its metadata. Never the secrets."""
    try:
        s = load_session()
    except Exception:  # unreadable / corrupt file: report it as missing
        s = None
    if s is None or not s.is_valid():
        return {"connected": False}
    return {
        "connected": True,
        "region": s.region,
        "logged_in_at": s.created_at,
        "renewed_at": s.renewed_at,
        "can_renew": s.can_renew(),
    }


def login_with_renewal(on_qr: Callable[[str, str], None], window_s: float = LOGIN_WINDOW_S) -> Session:
    """mifit's QR login, with a fresh link each time one expires unapproved.

    Same steps as ``mifit.auth.qr.login_qr`` (one HTTP session, one device id),
    looped until approval or ``window_s``. A security confirmation request is
    raised at once: it needs the user, not a new link.
    """
    http = requests.Session()
    device_id = new_device_id()
    deadline = time.time() + window_s
    last: Exception | None = None
    while time.time() < deadline:
        challenge = request_qr_login(http, SID, device_id=device_id)
        on_qr(challenge.login_url, challenge.qr_payload)
        try:
            result = poll_qr_login(challenge, http, device_id=device_id)
        except NotificationRequiredError:
            raise
        except Exception as exc:  # link expired (long-poll timeout / refusal): renew
            last = exc
            continue
        return exchange_sts(result, SID, http, device_id=device_id)
    raise TimeoutError(f"no approval within {int(window_s // 60)} minutes") from last


class LoginManager:
    def __init__(
        self,
        login: Callable[..., Session] = login_with_renewal,
        save: Callable[[Session], object] = save_session,
    ) -> None:
        self._login = login
        self._save = save
        self._lock = threading.Lock()
        self._url_ready = threading.Event()
        self.state_: LoginState | None = None

    def state(self) -> dict | None:
        with self._lock:
            return asdict(self.state_) if self.state_ else None

    def start(self, wait_url_s: float = 15.0) -> tuple[dict, bool]:
        """Start a login, or join the one waiting. Returns ``(state, started)``;
        the state holds ``login_url`` once Xiaomi answered (within ``wait_url_s``)."""
        with self._lock:
            if self.state_ and self.state_.status == "waiting":
                return asdict(self.state_), False
            self.state_ = LoginState(status="waiting", started_at=time.time())
            self._url_ready.clear()
        threading.Thread(target=self._run, daemon=True).start()
        self._url_ready.wait(wait_url_s)
        return self.state() or {}, True

    def _set(self, **changes) -> None:
        with self._lock:
            assert self.state_ is not None
            for k, v in changes.items():
                setattr(self.state_, k, v)

    def _run(self) -> None:
        def on_qr(login_url: str, _qr_payload: str) -> None:
            with self._lock:
                assert self.state_ is not None
                self.state_.login_url = login_url
                self.state_.link_count += 1
            self._url_ready.set()

        try:
            session = self._login(on_qr=on_qr)
            if region := forced_region():
                session = replace(session, region=region)
            self._save(session)
            record_event("login", session)  # best effort, never raises
            self._set(status="done", finished_at=time.time())
        except NotificationRequiredError as exc:
            self._set(
                status="error",
                notification_url=exc.notification_url,
                error="Xiaomi demande une confirmation de sécurité : ouvre le lien, valide, puis reconnecte-toi.",
                finished_at=time.time(),
            )
        except Exception as exc:  # timeout of the long poll, network, refused login...
            text = str(exc) or type(exc).__name__
            if "timed out" in text.lower() or "timeout" in type(exc).__name__.lower():
                text = "La connexion n'a pas été validée à temps (10 minutes). Relance-la."
            self._set(status="error", error=text, finished_at=time.time())
        finally:
            self._url_ready.set()
