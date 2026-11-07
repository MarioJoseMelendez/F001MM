import os
import sys
import click
import httpx
import asyncio
import subprocess
from ddgs import DDGS
from ddgs.exceptions import DDGSException, TimeoutException

ddgsSemaphore = asyncio.Semaphore(2)
asyncReq = httpx.AsyncClient()

async def webReq(*, search='', numSearch=3):
    # Transient transport failures get a few retries before giving up.
    maxAttempts = 3
    for webAttempt in range(1, maxAttempts + 1):
        try:
            async with ddgsSemaphore: # Limit the number of concurrent requests to DDGS
                res = await asyncio.to_thread(
                    DDGS(timeout=120).text, search, max_results=numSearch)
            return res
        except DDGSException as webError:
            errorText = str(webError).lower()
            # Empty DDGS searches soft-fail so Einstein continues instead of crashing.
            isEmptySearch = (
                "no results found" in errorText
                or "no results" in errorText
            )

            if isEmptySearch:
                click.echo(
                    click.style(
                        f"No results found for search: {search}. Skipping.",
                        fg=(255, 165, 0),
                    )
                )
                return []

            # Retry only transient transport failures; other errors re-raise.
            isTransportError = isinstance(webError, TimeoutException)

            if not isTransportError:
                if (
                    "timed out" in errorText
                    or "timeout" in errorText
                    or "connection" in errorText
                    or "error sending request" in errorText
                    or "connecterror" in errorText
                    or "dnserror" in errorText
                    or "requesterror" in errorText
                ):
                    isTransportError = True

            if not isTransportError:
                raise

            if webAttempt < maxAttempts:
                fallbackMessage = (
                    f"Could not search the web: {search}. "
                    f"Retrying ({webAttempt + 1}/{maxAttempts})..."
                )
            else:
                fallbackMessage = (
                    f"Could not search the web: {search}. "
                    f"No attempts left."
                )

            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )

    return []


async def paperReq(*, search='', numSearch=3):
    url = f'https://api.openalex.org/works'

    reqParams = {
        "search": search,
        "filter": "is_oa:true",
        "per_page": numSearch,
        "sort": "publication_year:desc,cited_by_count:desc",
        "select": "title,publication_year,publication_date,abstract_inverted_index,primary_location,cited_by_count",
    }
    reqHeaders = {
        "User-Agent": "Mozzilla/5.0 (Windows NT 10.0; Win64; x64) FalenEinstein/0.1 (mariomelendez099@gmail.com)",
    }
    # Transient transport failures get a few retries before giving up.
    maxAttempts = 3

    for paperAttempt in range(1, maxAttempts + 1):
        try:
            res = await asyncReq.get(
                url,
                params=reqParams,
                headers=reqHeaders,
                timeout=120,
            )
        except (
            httpx.exceptions.Timeout,
            httpx.exceptions.ConnectionError,
        ):
            if paperAttempt < maxAttempts:
                fallbackMessage = (
                    f"Could not search papers: {search}. "
                    f"Retrying ({paperAttempt + 1}/{maxAttempts})..."
                )
            else:
                fallbackMessage = (
                    f"Could not search papers: {search}. "
                    f"No attempts left."
                )

            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )
            continue

        data = res.json()
        papers = data.get("results", [])
        return papers

    return []


async def contentReq(*, url='', format='text_markdown'):
    # Soft-fail: no URL means nothing to extract; Einstein can continue.
    if not url:
        click.echo(
            click.style(
                "Skipping content extraction: no URL provided.",
                fg=(255, 165, 0),
            )
        )
        return ""

    # Transient transport failures get a few retries before giving up.
    maxAttempts = 3

    for contentAttempt in range(1, maxAttempts + 1):
        try:
            async with ddgsSemaphore:
                content = await asyncio.to_thread(DDGS(timeout=120).extract, url, fmt=format)
            return content['content']
        except DDGSException as contentError:
            errorText = str(contentError).lower()
            # Retry only transient transport failures; other extract errors soft-fail.
            isTransportError = isinstance(contentError, TimeoutException)

            if not isTransportError:
                if (
                    "timed out" in errorText
                    or "timeout" in errorText
                    or "connection" in errorText
                    or "error sending request" in errorText
                    or "connecterror" in errorText
                    or "dnserror" in errorText
                    or "requesterror" in errorText
                ):
                    isTransportError = True

            if not isTransportError:
                click.echo(
                    click.style(
                        f"Could not extract content from link: {url}",
                        fg=(255, 165, 0),
                    )
                )
                return ""

            if contentAttempt < maxAttempts:
                fallbackMessage = (
                    f"Could not extract content from link: {url}. "
                    f"Retrying ({contentAttempt + 1}/{maxAttempts})..."
                )
            else:
                fallbackMessage = (
                    f"Could not extract content from link: {url}. "
                    f"No attempts left."
                )

            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )

    return ""

def createCode(*, name='', code='', motherPath=''):
    if not os.path.exists(motherPath):
        os.makedirs(motherPath)
    try:
        # TODO: We need an async alternative to write files
        with open(f"{motherPath}/{name}.py", "x") as file:
            file.write(code)
    except FileExistsError:
        click.echo(
            click.style(
                f"File {name}.py already exists",
                fg=(255, 165, 0),
            )
        )

        with open(f"{motherPath}/{name}.py", "w") as file:
            file.write(code)

        click.echo(
            click.style(
                f"File {name}.py created",
                fg=(0, 255, 0),
            )
        )

def executeCode(*, name='', motherPath='', numExecutions=1):
    results = []
    for i in range(numExecutions):
        # TODO: We need an async alternative to run code
        codeRes = subprocess.run([sys.executable, f"{motherPath}/{name}.py"], capture_output=True, text=True)
        results.append(codeRes)

    return results
