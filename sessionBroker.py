# One public port. Each new browser gets its own ttyd and code directory.

import asyncio
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path

from tracker import RecordSessionStarted


# =========== {1} Keep Per-Visitor Sessions ===========

REPO_ROOT = Path(__file__).resolve().parent
SESSION_ROOT = REPO_ROOT / "sessions"
TTYD_THEME = 'theme={"background":"#1a1614","foreground":"#f3eadf"}'

sessions = {}


def ResolveTtydBin():
    configuredBin = os.environ.get("FALEN_TTYD_BIN", "")
    if configuredBin:
        return configuredBin
    return "ttyd"


def ResolvePythonBin():
    configuredBin = os.environ.get("FALEN_PYTHON_BIN", "")
    if configuredBin:
        return configuredBin
    return sys.executable


def HeaderMap(headText):
    headers = {}
    lines = headText.split("\r\n")
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if separator:
            headers[name.lower()] = value.strip()
    return headers


def ReapSessions():
    deadIds = []
    for sessionId, session in sessions.items():
        if session["process"].poll() is not None:
            deadIds.append(sessionId)

    for sessionId in deadIds:
        sessions.pop(sessionId, None)


def StopProcess(process):
    if process.poll() is not None:
        return

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
            return
        except OSError:
            pass

    process.terminate()


def StopSessions():
    processes = []
    for session in sessions.values():
        processes.append(session["process"])
    sessions.clear()

    for process in processes:
        StopProcess(process)

    for process in processes:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()


def FreePort():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def SessionIdFromPath(path):
    if not path.startswith("/s/"):
        return ""

    remainder = path[3:]
    sessionId, separator, tail = remainder.partition("/")
    return sessionId


def SessionIdFromCookie(headText):
    headers = HeaderMap(headText)
    cookieHeader = headers.get("cookie", "")
    cookieParts = cookieHeader.split(";")

    for cookiePart in cookieParts:
        cookieName, separator, cookieValue = cookiePart.strip().partition("=")
        if cookieName == "falen_session":
            return cookieValue.strip()

    return ""


def LiveSession(sessionId):
    session = sessions.get(sessionId)
    if session is None:
        return None

    if session["process"].poll() is not None:
        sessions.pop(sessionId, None)
        return None

    return session


# =========== {2} Start One ttyd ===========

def ClientIpFromRequest(headText, writer):
    headers = HeaderMap(headText)
    # Render (and similar) put the real client first in X-Forwarded-For.
    forwarded = headers.get("x-forwarded-for", "")
    if forwarded:
        firstIp = forwarded.split(",")[0].strip()
        if firstIp:
            return firstIp

    peerName = writer.get_extra_info("peername")
    if peerName and len(peerName) >= 1:
        return str(peerName[0])

    return ""


def IsLocalOrPrivateIp(ipText):
    if not ipText:
        return True

    try:
        ipObj = ipaddress.ip_address(ipText)
    except ValueError:
        return True

    return (
        ipObj.is_private
        or ipObj.is_loopback
        or ipObj.is_link_local
        or ipObj.is_reserved
    )


def ResolveCountry(ipText):
    # Country only — never persist the IP. Soft-fail keeps session start alive.
    if IsLocalOrPrivateIp(ipText):
        return "local"

    lookupUrl = (
        f"http://ip-api.com/json/{ipText}"
        "?fields=status,country,countryCode"
    )
    try:
        with urllib.request.urlopen(lookupUrl, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") != "success":
            return ""

        countryCode = payload.get("countryCode") or ""
        if countryCode:
            return countryCode

        return payload.get("country") or ""
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return ""
    except Exception:
        return ""


def StartSession(country=""):
    sessionId = str(uuid.uuid4())
    sessionDir = SESSION_ROOT / sessionId
    sessionDir.mkdir(parents=True, exist_ok=False)

    childPort = FreePort()
    childEnv = os.environ.copy()
    childEnv["FALEN_CODE_DIR"] = str(sessionDir)
    childEnv["FALEN_SESSION_ID"] = sessionId

    ttydCommand = [
        ResolveTtydBin(),
        "--port",
        str(childPort),
        "--interface",
        "127.0.0.1",
        "--once",
        "-W",
        "-t",
        "fontSize=16",
        "-t",
        TTYD_THEME,
        "--base-path",
        f"/s/{sessionId}",
        ResolvePythonBin(),
        "interface.py",
    ]

    try:
        childProcess = subprocess.Popen(
            ttydCommand,
            cwd=str(REPO_ROOT),
            env=childEnv,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as spawnError:
        print(f"could not start ttyd: {spawnError}", flush=True)
        return ""

    sessions[sessionId] = {
        "process": childProcess,
        "port": childPort,
        "directory": str(sessionDir),
    }
    RecordSessionStarted(sessionId, country)
    print(
        f"session {sessionId} ttyd 127.0.0.1:{childPort}",
        flush=True,
    )
    return sessionId


async def WaitUntilListening(sessionId):
    session = sessions.get(sessionId)
    if session is None:
        return False

    attempts = 0
    while attempts < 50:
        if session["process"].poll() is not None:
            return False

        try:
            reader, writer = await asyncio.open_connection(
                "127.0.0.1",
                session["port"],
            )
            writer.close()
            await writer.wait_closed()
            return True
        except OSError:
            await asyncio.sleep(0.1)

        attempts += 1

    return False


async def WriteRedirect(writer, sessionId):
    message = (
        "HTTP/1.1 302 Found\r\n"
        f"Location: /s/{sessionId}/\r\n"
        f"Set-Cookie: falen_session={sessionId}; HttpOnly; Path=/; SameSite=Lax\r\n"
        "Content-Length: 0\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(message.encode("ascii"))
    await writer.drain()


async def WritePlain(writer, statusCode, statusText, body):
    bodyBytes = body.encode("utf-8")
    message = (
        f"HTTP/1.1 {statusCode} {statusText}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(bodyBytes)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(message.encode("ascii") + bodyBytes)
    await writer.drain()


# =========== {3} Proxy HTTP And WebSocket ===========

async def ReadHead(reader):
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        chunk = await reader.read(4096)
        if not chunk:
            break
        buffer += chunk
        if len(buffer) > 65536:
            break

    separator = buffer.find(b"\r\n\r\n")
    if separator == -1:
        return buffer, b""

    head = buffer[:separator]
    rest = buffer[separator + 4:]
    return head, rest


async def ReadBody(reader, headText, alreadyRead):
    headers = HeaderMap(headText)
    lengthText = headers.get("content-length", "")
    if not lengthText:
        return b""

    length = int(lengthText)
    body = alreadyRead[:length]
    while len(body) < length:
        chunk = await reader.read(length - len(body))
        if not chunk:
            break
        body += chunk

    return body


def IsWebSocket(responseHead):
    text = responseHead.decode("latin-1", errors="replace")
    statusLine = text.split("\r\n", 1)[0]
    return " 101 " in statusLine


async def Pipe(source, dest):
    try:
        while True:
            chunk = await source.read(65536)
            if not chunk:
                break
            dest.write(chunk)
            await dest.drain()
    except OSError:
        pass

    try:
        dest.close()
        await dest.wait_closed()
    except OSError:
        pass


async def ForwardBody(remoteReader, clientWriter, responseHead, alreadyRead):
    headText = responseHead.decode("latin-1", errors="replace")
    headers = HeaderMap(headText)
    lengthText = headers.get("content-length", "")

    if lengthText:
        length = int(lengthText)
        body = alreadyRead[:length]
        clientWriter.write(body)
        remaining = length - len(body)
        while remaining > 0:
            chunk = await remoteReader.read(min(65536, remaining))
            if not chunk:
                break
            clientWriter.write(chunk)
            remaining -= len(chunk)
        await clientWriter.drain()
        return

    if alreadyRead:
        clientWriter.write(alreadyRead)
        await clientWriter.drain()

    while True:
        try:
            chunk = await asyncio.wait_for(remoteReader.read(65536), timeout=2)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        clientWriter.write(chunk)
        await clientWriter.drain()


async def ProxyToTtyd(clientReader, clientWriter, childPort, requestHead, requestRest):
    try:
        remoteReader, remoteWriter = await asyncio.open_connection(
            "127.0.0.1",
            childPort,
        )
    except OSError:
        await WritePlain(clientWriter, 502, "Bad Gateway", "ttyd is not reachable")
        return

    requestText = requestHead.decode("latin-1", errors="replace")
    requestHeaders = HeaderMap(requestText)
    upgrade = requestHeaders.get("upgrade", "")
    if upgrade.lower() == "websocket":
        # Bytes after the handshake were already read and must reach ttyd.
        remoteWriter.write(requestHead + b"\r\n\r\n" + requestRest)
    else:
        requestBody = await ReadBody(clientReader, requestText, requestRest)
        remoteWriter.write(requestHead + b"\r\n\r\n" + requestBody)
    await remoteWriter.drain()

    responseHead, responseRest = await ReadHead(remoteReader)
    if not responseHead:
        remoteWriter.close()
        await WritePlain(clientWriter, 502, "Bad Gateway", "ttyd closed the connection")
        return

    clientWriter.write(responseHead + b"\r\n\r\n")
    await clientWriter.drain()

    if IsWebSocket(responseHead):
        if responseRest:
            clientWriter.write(responseRest)
            await clientWriter.drain()
        await asyncio.gather(
            Pipe(clientReader, remoteWriter),
            Pipe(remoteReader, clientWriter),
        )
        return

    await ForwardBody(remoteReader, clientWriter, responseHead, responseRest)
    remoteWriter.close()


# =========== {4} Open Or Reuse A Session ===========

async def RouteClient(reader, writer):
    ReapSessions()
    requestHead, requestRest = await ReadHead(reader)
    if not requestHead:
        return

    requestText = requestHead.decode("latin-1", errors="replace")
    requestLines = requestText.split("\r\n")
    requestParts = requestLines[0].split(" ")
    if len(requestParts) < 2:
        return

    target = requestParts[1]
    path = target.split("?", 1)[0]

    pathSessionId = SessionIdFromPath(path)
    pathSession = LiveSession(pathSessionId)
    if pathSession is not None:
        await ProxyToTtyd(
            reader,
            writer,
            pathSession["port"],
            requestHead,
            requestRest,
        )
        return

    cookieSessionId = SessionIdFromCookie(requestText)
    cookieSession = LiveSession(cookieSessionId)
    if cookieSession is not None:
        await WriteRedirect(writer, cookieSessionId)
        return

    clientIp = ClientIpFromRequest(requestText, writer)
    country = ResolveCountry(clientIp)
    sessionId = StartSession(country)
    if not sessionId:
        await WritePlain(writer, 502, "Bad Gateway", "ttyd did not start")
        return

    listening = await WaitUntilListening(sessionId)
    if not listening:
        failedSession = sessions.pop(sessionId, None)
        if failedSession is not None:
            StopProcess(failedSession["process"])
        await WritePlain(writer, 502, "Bad Gateway", "ttyd did not start")
        return

    await WriteRedirect(writer, sessionId)


async def HandleClient(reader, writer):
    try:
        await RouteClient(reader, writer)
    except OSError:
        pass
    except Exception as routeError:
        print(f"session request failed: {routeError}", flush=True)
        try:
            await WritePlain(writer, 500, "Internal Server Error", "session broker error")
        except OSError:
            pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass


async def ReapLoop():
    while True:
        ReapSessions()
        await asyncio.sleep(2)


async def Serve():
    portText = os.environ.get("PORT", "7681")
    port = int(portText)
    reapTask = asyncio.create_task(ReapLoop())
    server = await asyncio.start_server(HandleClient, "0.0.0.0", port)
    if os.name == "posix":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, server.close)
        loop.add_signal_handler(signal.SIGINT, server.close)
    print(f"Falen session broker listening on 0.0.0.0:{port}", flush=True)

    try:
        async with server:
            await server.serve_forever()
    finally:
        reapTask.cancel()
        StopSessions()


def Main():
    try:
        asyncio.run(Serve())
    except KeyboardInterrupt:
        StopSessions()


if __name__ == "__main__":
    Main()
