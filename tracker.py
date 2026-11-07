# Ops logging for web sessions and submitted problems.
# Disclose this logging to users in the product UI later.
#
# Supabase (optional): set SUPABASE_URL plus one server-only key, in order:
#   1) SUPABASE_SECRET_KEY — preferred server secret (sb_secret_…); never browsers.
#   2) SUPABASE_ANON_KEY — legacy fallback only; needs careful RLS if used.
#   3) SUPABASE_SERVICE_ROLE_KEY — legacy elevated alias for older projects.
# Prefer SECRET on servers. Never expose any of these to the browser / NEXT_PUBLIC.
# Secret keys bypass RLS (like service_role); anon must not get broad SELECT in prod.
# If URL or key is missing, writes fall back to local SQLite (demo / no cloud).

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = REPO_ROOT / "sessions" / "tracker.sqlite"
MAX_PROMPT_CHARS = 10000
SUPABASE_TIMEOUT_SECONDS = 10

# Prefer server secret, then legacy anon, then legacy service_role.
SUPABASE_KEY_ENV_NAMES = (
    "SUPABASE_SECRET_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)


def SupabaseHeaders(supabaseKey, extraHeaders=None):
    # Always send apikey + Authorization. Legacy JWTs need Bearer; sb_secret_
    # keys are accepted the same way by PostgREST on current Supabase projects.
    headers = {
        "apikey": supabaseKey,
        "Authorization": f"Bearer {supabaseKey}",
        "Content-Type": "application/json",
    }
    if extraHeaders:
        for headerName, headerValue in extraHeaders.items():
            headers[headerName] = headerValue
    return headers

# ANSI orange-ish warning; keep product running if a write fails.
WARN_PREFIX = "\033[38;5;208m[tracker]\033[0m"

# Render / process env wins. Local .env fills gaps only (override=False).
load_dotenv(REPO_ROOT / ".env", override=False)

_backendAnnounced = False


def ResolveDbPath():
    configuredPath = os.environ.get("FALEN_TRACKER_DB", "")
    if configuredPath:
        return Path(configuredPath)
    return DEFAULT_DB_PATH


def ResolveSupabaseConfig():
    supabaseUrl = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    supabaseKey = ""
    keyEnvName = ""

    for envName in SUPABASE_KEY_ENV_NAMES:
        candidateKey = os.environ.get(envName, "").strip()
        if candidateKey:
            supabaseKey = candidateKey
            keyEnvName = envName
            break

    if supabaseUrl and supabaseKey:
        return supabaseUrl, supabaseKey, keyEnvName
    return "", "", ""


def WarnSoft(message):
    print(f"{WARN_PREFIX} {message}", flush=True)


def AnnounceBackendOnce():
    # One line at first use — no secrets, so Render logs show which path is live.
    global _backendAnnounced
    if _backendAnnounced:
        return
    _backendAnnounced = True

    supabaseUrl, supabaseKey, keyEnvName = ResolveSupabaseConfig()
    if supabaseUrl and supabaseKey:
        print(
            f"[tracker] supabase ok (key via {keyEnvName})",
            flush=True,
        )
        return

    missingParts = []
    if not supabaseUrl:
        missingParts.append("SUPABASE_URL")
    if not supabaseKey:
        missingParts.append(
            "SUPABASE_SECRET_KEY|SUPABASE_ANON_KEY|SUPABASE_SERVICE_ROLE_KEY"
        )
    missingText = ", ".join(missingParts)
    print(
        "[tracker] using sqlite fallback "
        f"(missing {missingText}; ephemeral on Render)",
        flush=True,
    )


def TruncatePrompt(userPrompt):
    promptText = userPrompt
    if len(promptText) > MAX_PROMPT_CHARS:
        promptText = promptText[:MAX_PROMPT_CHARS]
    return promptText


# =========== {1} Write Via Supabase PostgREST ===========

def InsertSupabase(
    tableName,
    row,
    preferHeader="return=minimal",
    onConflict="",
):
    AnnounceBackendOnce()
    supabaseUrl, supabaseKey, _keyEnvName = ResolveSupabaseConfig()
    if not supabaseUrl or not supabaseKey:
        return False

    endpoint = f"{supabaseUrl}/rest/v1/{tableName}"
    requestParams = {}
    if onConflict:
        requestParams["on_conflict"] = onConflict

    headers = SupabaseHeaders(
        supabaseKey,
        extraHeaders={"Prefer": preferHeader},
    )

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            params=requestParams,
            json=row,
            timeout=SUPABASE_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            detailText = (response.text or "").strip().replace("\n", " ")
            if len(detailText) > 180:
                detailText = detailText[:180] + "…"
            if detailText:
                WarnSoft(
                    f"supabase {tableName} write FAILED "
                    f"(NOT SAVED): HTTP {response.status_code} — {detailText}"
                )
            else:
                WarnSoft(
                    f"supabase {tableName} write FAILED "
                    f"(NOT SAVED): HTTP {response.status_code}"
                )
            return False
        return True
    except requests.exceptions.RequestException as requestError:
        WarnSoft(
            f"supabase {tableName} write FAILED (NOT SAVED): {requestError}"
        )
        return False
    except Exception as writeError:
        WarnSoft(
            f"supabase {tableName} write FAILED (NOT SAVED): {writeError}"
        )
        return False


# =========== {2} Write Via Local SQLite ===========

def ConnectDb():
    dbPath = ResolveDbPath()
    dbPath.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(dbPath))
    connection.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        "id TEXT PRIMARY KEY, "
        "started_at TEXT NOT NULL, "
        "country TEXT"
        ")"
    )
    # Old DBs created before country existed; ADD COLUMN is a no-op if present.
    try:
        connection.execute("ALTER TABLE sessions ADD COLUMN country TEXT")
    except sqlite3.OperationalError:
        pass

    connection.execute(
        "CREATE TABLE IF NOT EXISTS problems ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT NOT NULL, "
        "prompt_text TEXT NOT NULL, "
        "submitted_at TEXT NOT NULL"
        ")"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS results ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT NOT NULL, "
        "falen_res_json TEXT NOT NULL, "
        "recorded_at TEXT NOT NULL"
        ")"
    )
    connection.commit()
    return connection


def InsertSqliteSession(sessionId, startedAt, country):
    connection = ConnectDb()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, country) "
            "VALUES (?, ?, ?)",
            (sessionId, startedAt, country),
        )
        connection.commit()
    finally:
        connection.close()


def InsertSqliteProblem(sessionId, promptText, submittedAt):
    connection = ConnectDb()
    try:
        connection.execute(
            "INSERT INTO problems (session_id, prompt_text, submitted_at) "
            "VALUES (?, ?, ?)",
            (sessionId, promptText, submittedAt),
        )
        connection.commit()
    finally:
        connection.close()


def InsertSqliteFalenRes(sessionId, falenResJson, recordedAt):
    connection = ConnectDb()
    try:
        connection.execute(
            "INSERT INTO results (session_id, falen_res_json, recorded_at) "
            "VALUES (?, ?, ?)",
            (sessionId, falenResJson, recordedAt),
        )
        connection.commit()
    finally:
        connection.close()


# =========== {3} Public Record Hooks ===========

def RecordSessionStarted(sessionId, country=""):
    try:
        AnnounceBackendOnce()
        startedAt = datetime.now(timezone.utc).isoformat()
        supabaseUrl, supabaseKey, _keyEnvName = ResolveSupabaseConfig()

        if supabaseUrl and supabaseKey:
            wroteOk = InsertSupabase(
                "falen_sessions",
                {
                    "id": sessionId,
                    "started_at": startedAt,
                    "country": country or "",
                },
                preferHeader="resolution=ignore-duplicates,return=minimal",
                onConflict="id",
            )
            if not wroteOk:
                WarnSoft(
                    "session NOT persisted to supabase "
                    f"(id={sessionId[:8]}…)"
                )
            return

        InsertSqliteSession(sessionId, startedAt, country)
    except Exception as writeError:
        WarnSoft(f"session write failed: {writeError}")


def RecordProblemSubmitted(sessionId, userPrompt):
    try:
        AnnounceBackendOnce()
        # Cap huge prompts so storage stays small on disk / ephemeral hosts.
        promptText = TruncatePrompt(userPrompt)
        submittedAt = datetime.now(timezone.utc).isoformat()
        supabaseUrl, supabaseKey, _keyEnvName = ResolveSupabaseConfig()

        if supabaseUrl and supabaseKey:
            wroteOk = InsertSupabase(
                "falen_problems",
                {
                    "session_id": sessionId,
                    "prompt_text": promptText,
                    "submitted_at": submittedAt,
                },
            )
            if not wroteOk:
                WarnSoft(
                    "problem NOT persisted to supabase "
                    f"(session={sessionId[:8]}…)"
                )
            return

        InsertSqliteProblem(sessionId, promptText, submittedAt)
    except Exception as writeError:
        WarnSoft(f"problem write failed: {writeError}")


def RecordFalenRes(sessionId, falenRes):
    try:
        AnnounceBackendOnce()
        recordedAt = datetime.now(timezone.utc).isoformat()
        # default=str keeps non-JSON values (paths, etc.) from aborting the write.
        falenResJson = json.dumps(falenRes, default=str)
        supabaseUrl, supabaseKey, _keyEnvName = ResolveSupabaseConfig()

        if supabaseUrl and supabaseKey:
            wroteOk = InsertSupabase(
                "falen_results",
                {
                    "session_id": sessionId,
                    "falen_res_json": falenResJson,
                    "recorded_at": recordedAt,
                },
            )
            if not wroteOk:
                WarnSoft(
                    "falenRes NOT persisted to supabase "
                    f"(session={sessionId[:8]}…)"
                )
            return

        InsertSqliteFalenRes(sessionId, falenResJson, recordedAt)
    except Exception as writeError:
        WarnSoft(f"falenRes write failed: {writeError}")


# First import (broker / orchestrator boot) prints supabase vs sqlite once.
AnnounceBackendOnce()
