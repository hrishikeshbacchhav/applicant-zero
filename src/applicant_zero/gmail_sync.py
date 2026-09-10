"""Read-only Gmail connection for matching job-search messages to the tracker.

The module deliberately uses only Gmail's read-only OAuth scope.  It never
sends, changes labels, archives, deletes or stores email bodies.  The local
database keeps only the message id, sender, subject and matching outcome.
"""

import base64
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .storage import (
    get_match,
    initialise_database,
    list_matches,
    record_email_sync_run,
    save_email_event,
    update_workflow,
)


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CLIENT_SECRET_NAME = "gmail_client_secret.json"
TOKEN_NAME = "gmail_token.json"


class GmailSetupError(ValueError):
    """Raised when the optional local Gmail connection is not ready."""


@dataclass(frozen=True)
class MailMatch:
    category: str
    external_id: str | None
    confidence: str
    target_status: str | None


def gmail_paths(project_root: Path) -> tuple[Path, Path]:
    private = project_root / "private"
    return private / CLIENT_SECRET_NAME, private / TOKEN_NAME


def gmail_setup_status(project_root: Path) -> tuple[bool, str]:
    secret, token = gmail_paths(project_root)
    if token.exists():
        return True, "Connected locally with Gmail read-only access."
    if secret.exists():
        return False, "OAuth client file is ready. Run the one-time Gmail connection command."
    return False, "Not connected. Add the private Gmail OAuth client file first."


def _google_libraries():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as error:
        raise GmailSetupError("Install the optional Gmail package first: python -m pip install -e \".[gmail]\"") from error
    return Request, Credentials, InstalledAppFlow, build


def connect_gmail(project_root: Path) -> str:
    """Run Google's local OAuth window once and save only its private token."""
    secret, token = gmail_paths(project_root)
    if not secret.exists():
        raise GmailSetupError(f"Add the Google OAuth desktop-client file at private/{CLIENT_SECRET_NAME} before connecting.")
    _request, _credentials, flow_type, _build = _google_libraries()
    flow = flow_type.from_client_secrets_file(str(secret), [GMAIL_READONLY_SCOPE])
    credentials = flow.run_local_server(port=0)
    token.write_text(credentials.to_json(), encoding="utf-8")
    return "Gmail connected with read-only access. No mail was changed."


def _service(project_root: Path):
    secret, token = gmail_paths(project_root)
    if not token.exists():
        raise GmailSetupError("Gmail is not connected yet. Run python -m applicant_zero --gmail-connect first.")
    request_type, credentials_type, _flow_type, build = _google_libraries()
    credentials = credentials_type.from_authorized_user_file(str(token), [GMAIL_READONLY_SCOPE])
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(request_type())
            token.write_text(credentials.to_json(), encoding="utf-8")
        else:
            raise GmailSetupError("Gmail access needs reconnecting. Run python -m applicant_zero --gmail-connect again.")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _headers(message: dict) -> dict[str, str]:
    return {
        str(item.get("name", "")).lower(): str(item.get("value", ""))
        for item in message.get("payload", {}).get("headers", [])
    }


def _body_text(part: dict) -> str:
    chunks: list[str] = []
    if part.get("mimeType") == "text/plain":
        encoded = str(part.get("body", {}).get("data", ""))
        if encoded:
            try:
                chunks.append(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", errors="replace"))
            except (ValueError, UnicodeDecodeError):
                pass
    for child in part.get("parts", []):
        chunks.append(_body_text(child))
    return "\n".join(chunk for chunk in chunks if chunk)


def _category(text: str) -> tuple[str, str | None]:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("offer of employment", "pleased to offer", "employment offer")):
        return "offer", "Offer"
    if any(phrase in lowered for phrase in ("not moving forward", "unsuccessful", "regret to inform", "unfortunately")):
        return "rejected", "Rejected"
    if any(phrase in lowered for phrase in ("interview invitation", "invite you to interview", "schedule an interview", "interview with")):
        return "interview", "Interview"
    if any(phrase in lowered for phrase in ("application received", "application has been received", "thanks for applying", "thank you for applying", "application submitted")):
        return "application confirmation", "Applied"
    return "other", None


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def classify_job_message(subject: str, sender: str, body: str, jobs: list[dict]) -> MailMatch:
    """Classify a message and match it only when a company signal is clear."""
    category, status = _category(" ".join((subject, sender, body)))
    if status is None:
        return MailMatch(category, None, "unmatched", None)
    haystack = _compact(" ".join((subject, sender, body)))
    candidates = []
    for job in jobs:
        company = _compact(str(job.get("company", "")))
        title = _compact(str(job.get("title", "")))
        company_hit = len(company) >= 3 and company in haystack
        title_words = [word for word in title.split() if len(word) >= 4]
        title_hits = sum(word in haystack for word in title_words)
        if company_hit:
            score = 2 + min(title_hits, 2)
            candidates.append((score, job))
    if not candidates:
        return MailMatch(category, None, "unmatched", None)
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best = candidates[0]
    if len(candidates) > 1 and candidates[1][0] == best_score:
        return MailMatch(category, None, "ambiguous", None)
    confidence = "high" if best_score >= 3 else "company match"
    return MailMatch(category, str(best["external_id"]), confidence, status)


def sync_gmail(project_root: Path, database_path: Path, days: int = 2, max_messages: int = 200) -> dict[str, int | str]:
    """Read recent mail, record minimal metadata and update only clear matches."""
    service = _service(project_root)
    query = f"newer_than:{max(1, days)}d"
    listed = service.users().messages().list(userId="me", q=query, maxResults=max_messages).execute().get("messages", [])
    database = initialise_database(database_path)
    jobs = list_matches(database, include_duplicates=True)
    fetched = matched = updated = 0
    for item in listed:
        message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        headers = _headers(message)
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        body = _body_text(message.get("payload", {}))
        result = classify_job_message(subject, sender, body, jobs)
        tracker_updated = False
        # A company-only signal is useful to show in Email updates, but it is
        # not enough to mutate the tracker.  Automatic tracker changes need a
        # clear company and role-title signal from the message.
        if result.external_id and result.target_status and result.confidence == "high":
            current = get_match(database, result.external_id)
            if current and current["workflow_status"] not in {"Offer", "Rejected", "Closed"}:
                update_workflow(database, result.external_id, result.target_status, f"Tracker updated from read-only Gmail: {result.category}.")
                tracker_updated = True
                updated += 1
        inserted = save_email_event(
            database, str(message["id"]), str(message.get("internalDate", "")), sender, subject,
            result.category, result.external_id, result.confidence, tracker_updated,
        )
        if inserted:
            fetched += 1
            matched += int(result.external_id is not None)
    detail = f"Read-only Gmail query {query}; no messages were changed."
    record_email_sync_run(database, fetched, matched, updated, detail)
    return {"fetched": fetched, "matched": matched, "updated": updated, "detail": detail}
