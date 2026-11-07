import os
import click
import requests
from dotenv import load_dotenv
from globalFuncs import contentReq, paperReq, webReq
import json
from pathlib import Path

load_dotenv()

# INFO for AI
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
urlOpenRouter = 'https://openrouter.ai/api/v1/chat/completions'

JEV_API_KEY = os.getenv('JEV_API_KEY')
urlJev = 'https://api.typesafe.ai/v1/systemone'
MAX_JEV_ATTEMPTS = 3
MAX_OPENROUTER_ATTEMPTS = 3

if not OPENROUTER_API_KEY:
    click.echo("There's not a OpenRouter API KEY")

# Prompts JSON
with open(Path(__file__).resolve().parent / "prompts.json", "r", encoding="utf-8") as file:
    prompts = json.load(file)

# Current Solution
def einstein(topic, limitations, baseline, thereBaseline=False):
    if thereBaseline:
        with open(baseline['code_path'], 'r', encoding='utf-8') as file:
            baselineCode = file.read()
    else:
        baselineCode = ""

    researchContext = {
        "topic": topic,
        "limitations": limitations,
        "baseline": {
            "description": baseline['description'],
            "results": baseline['results'],
            "implementation": baselineCode,
        },
    }
    # TODO: In the description we must have to add a function
    # where another agent take the current file and generate a desc of the baseline.

    # Context Prompt
    starterRaw = prompts[0]["prompt"]
    starterPrompt = '\n'.join(starterRaw)

    einsteinRes = []

    # One OpenRouter call proposes up to 5 searches; DDGS/OpenAlex gather locally.
    # Target ≥5 contentful unique URLs across all queries (no continue loop).
    MAX_SEARCH_PLANS = 5
    MIN_CONTENTFUL_RESULTS = 5
    MAX_LOCAL_FETCH_ATTEMPTS = 8
    DEFAULT_NUM_SEARCH = 5
    seenUrls = set()
    gatheredResults = []

    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================

    click.echo("")
    click.echo(click.style("  Einstein", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Deciding which searches to run...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")

    # ======================================================================

    researchPromptText = f"""RESEARCH CONTEXT:
{json.dumps(researchContext, indent=2)}"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }
    payload = {
        "model": "openrouter/free",
        "response_format": { "type": "json_object" },
        "messages": [
            {
                "role": "system",
                "content": starterPrompt
            },
            {
                "role": "user",
                "content": researchPromptText
            }
        ]
    }
    contentRes = None
    parsedRes = None

    for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
        try:
            aiRes = requests.post(
                urlOpenRouter,
                headers=headers,
                json=payload,
                timeout=120,
            )
            aiRes.raise_for_status()
            responseText = aiRes.text
            if responseText is None or not responseText.strip():
                raise ValueError("the server returned an empty body")
            aiResponse = aiRes.json()
            choices = aiResponse['choices']
            if not choices:
                raise ValueError("the answer was missing choices")
            contentRes = choices[0]['message']['content']
            if contentRes is None or not str(contentRes).strip():
                raise ValueError("the model returned an empty answer")
            parsedRes = json.loads(contentRes)
            if not isinstance(parsedRes, dict):
                raise TypeError("the answer was not a JSON object")
            break
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            IndexError,
            requests.exceptions.RequestException,
        ) as responseError:
            match responseError:
                case requests.exceptions.HTTPError():
                    statusCode = responseError.response.status_code
                    errorReason = f"the server answered with error {statusCode}"
                case json.JSONDecodeError():
                    errorReason = "the answer was not valid JSON"
                case requests.exceptions.RequestException():
                    errorReason = "the connection to the server failed"
                case KeyError():
                    errorReason = "the answer was missing expected fields"
                case _:
                    errorReason = str(responseError)
            if openRouterAttempt < MAX_OPENROUTER_ATTEMPTS:
                fallbackMessage = (
                    f"Could not plan Einstein searches: {errorReason}. "
                    f"Retrying ({openRouterAttempt + 1}/"
                    f"{MAX_OPENROUTER_ATTEMPTS})..."
                )
            else:
                fallbackMessage = (
                    f"Could not plan Einstein searches: {errorReason}. "
                    f"No attempts left."
                )
            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )
    else:
        raise RuntimeError(
            "Could not plan Einstein searches after all retry attempts."
        )

    print(contentRes)
    rawSearchPlans = parsedRes.get('searches')

    # Accept legacy single-search shape if the model still returns it.
    if rawSearchPlans is None:
        legacySearch = parsedRes.get('search')
        if legacySearch and legacySearch != 0:
            rawSearchPlans = [
                {
                    "method": parsedRes.get('method', 'web'),
                    "search": legacySearch,
                    "numSearch": parsedRes.get('numSearch', DEFAULT_NUM_SEARCH),
                }
            ]
        else:
            rawSearchPlans = []
    if not isinstance(rawSearchPlans, list):
        rawSearchPlans = []

    searchPlans = []
    for rawPlan in rawSearchPlans:
        if len(searchPlans) >= MAX_SEARCH_PLANS:
            break
        if not isinstance(rawPlan, dict):
            continue
        method = rawPlan.get('method', 'web')
        searchQuery = rawPlan.get('search', '')
        if not searchQuery or searchQuery == 0:
            continue
        numSearchRaw = rawPlan.get('numSearch', DEFAULT_NUM_SEARCH)
        try:
            numSearch = int(numSearchRaw)
        except (TypeError, ValueError):
            numSearch = DEFAULT_NUM_SEARCH
        if numSearch < 1:
            numSearch = 1
        if numSearch > 10:
            numSearch = 10
        searchPlans.append(
            {
                "method": method,
                "search": str(searchQuery),
                "numSearch": numSearch,
            }
        )

    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================

    click.echo("")
    click.echo(
        click.style("  Einstein plan", fg=(228, 180, 196), bold=True)
    )
    click.echo(
        click.style("  queries    ", fg=(154, 144, 136), bold=True)
        + click.style(str(len(searchPlans)), fg=(243, 234, 223))
    )
    click.echo(
        click.style("  target     ", fg=(154, 144, 136), bold=True)
        + click.style(
            f"≥{MIN_CONTENTFUL_RESULTS} contentful unique URLs",
            fg=(243, 234, 223),
        )
    )
    click.echo("")

    # ======================================================================

    for searchPlan in searchPlans:
        if len(gatheredResults) >= MIN_CONTENTFUL_RESULTS:
            break
        method = searchPlan['method']
        searchQuery = searchPlan['search']
        numSearch = searchPlan['numSearch']

        # ======================================================================
        # TODO: Embedded interface only. Remove this block later.
        # ======================================================================

        click.echo("")
        click.echo(
            click.style("  Einstein search", fg=(228, 180, 196), bold=True)
        )
        click.echo(
            click.style("  method     ", fg=(154, 144, 136), bold=True)
            + click.style(str(method), fg=(243, 234, 223))
        )
        click.echo(
            click.style("  query      ", fg=(154, 144, 136), bold=True)
            + click.style(str(searchQuery), fg=(243, 234, 223))
        )
        click.echo("")

        # ======================================================================

        localFetchAttempt = 0
        while (
            len(gatheredResults) < MIN_CONTENTFUL_RESULTS
            and localFetchAttempt < MAX_LOCAL_FETCH_ATTEMPTS
        ):
            localFetchAttempt += 1
            stillNeeded = MIN_CONTENTFUL_RESULTS - len(gatheredResults)
            batchSize = min(numSearch, stillNeeded)
            if batchSize < 1:
                break
            match method:
                case 'web':
                    batchRes = webReq(search=searchQuery, numSearch=batchSize)
                case 'paper':
                    batchRes = paperReq(search=searchQuery, numSearch=batchSize)
            for searchResult in batchRes:
                if len(gatheredResults) >= MIN_CONTENTFUL_RESULTS:
                    break
                if method == 'web':
                    resultUrl = searchResult.get('href') or searchResult.get('url')
                else:
                    primaryLocation = searchResult.get('primary_location') or {}
                    resultUrl = (
                        primaryLocation.get('landing_page_url')
                        or primaryLocation.get('pdf_url')
                    )
                if not resultUrl:
                    click.echo(
                        click.style(
                            "Skipping search result with no URL.",
                            fg=(255, 165, 0),
                        )
                    )
                    continue
                if resultUrl in seenUrls:
                    continue
                seenUrls.add(resultUrl)
                searchResult['url'] = resultUrl
                searchResult['content'] = contentReq(url=resultUrl)
                if not searchResult['content']:
                    continue
                searchResult['id'] = str(len(gatheredResults))
                gatheredResults.append(searchResult)

        # ======================================================================
        # TODO: Embedded interface only. Remove this block later.
        # ======================================================================

        click.echo("")
        click.echo(
            click.style("  Search done", fg=(201, 138, 160), bold=True)
        )
        click.echo(
            click.style("  query      ", fg=(154, 144, 136), bold=True)
            + click.style(str(searchQuery), fg=(243, 234, 223))
        )
        click.echo(
            click.style("  total so far ", fg=(154, 144, 136), bold=True)
            + click.style(str(len(gatheredResults)), fg=(243, 234, 223))
        )
        click.echo("")

        # ======================================================================

    methodRes = gatheredResults

    # TODO: An empty string "" is still sent to the context at the end. This has to be fixed later.
    if not methodRes:
        click.echo(
            click.style(
                "No search results with content were gathered.",
                fg=(228, 180, 196),
            )
        )

        # ======================================================================
        # TODO: Embedded interface only. Remove this block later.
        # ======================================================================

        click.echo("")
        click.echo(
            click.style("  Einstein complete", fg=(201, 138, 160), bold=True)
        )
        click.echo(
            click.style("  searches done  ", fg=(154, 144, 136), bold=True)
            + click.style("0", fg=(243, 234, 223))
        )
        click.echo("")

        # ======================================================================

        return einsteinRes

    jevQuestions = {}

    # Build one promising score question for each usable search result.
    for searchResult in methodRes:
        searchId = searchResult['id']
        jevQuestions[searchId] = {
            "type": "score",
            "instructions": (
                f"How promising is search result {searchId} for achieving "
                "the optimization goal in research_context? Consider its "
                "relevance, technical usefulness, credibility, and "
                "compatibility with every stated limitation."
            ),
            "criteria": [
                (
                    "Not promising: irrelevant, unsupported, redundant, "
                    "not actionable, or incompatible with the stated "
                    "limitations."
                ),
                (
                    "Promising: directly relevant, credible, actionable, "
                    "and likely to improve the current implementation "
                    "within the stated limitations."
                ),
            ],
        }

    jevHeaders = {
        "Authorization": f"Bearer {JEV_API_KEY}",
        "Content-Type": "application/json",
    }

    # JEV only needs the snippet. The stored result keeps the full page.
    jevSearchResults = []

    for searchResult in methodRes:
        resultUrl = searchResult.get("url")
        if not resultUrl:
            resultUrl = searchResult.get("href")
        resultSummary = searchResult.get("body")
        if not resultSummary:
            abstractIndex = searchResult.get("abstract_inverted_index")
            resultSummary = ""
            if isinstance(abstractIndex, dict) and abstractIndex:
                positionedWords = []
                for abstractWord, wordPositions in abstractIndex.items():
                    for wordPosition in wordPositions:
                        positionedWords.append((wordPosition, abstractWord))
                positionedWords.sort()
                summaryWords = []
                for wordPosition, abstractWord in positionedWords:
                    summaryWords.append(abstractWord)
                resultSummary = " ".join(summaryWords)

        jevSearchResult = {
            "id": searchResult["id"],
            "title": searchResult.get("title"),
            "url": resultUrl,
            "summary": resultSummary,
        }
        jevSearchResults.append(jevSearchResult)

    jevPayload = {
        "model": "jev-latest",
        "state": {
            "research_context": researchContext,
            "search_results": jevSearchResults,
        },
        "questions": jevQuestions,
    }

    jevRes = None
    jevAnswers = None
    for jevAttempt in range(1, MAX_JEV_ATTEMPTS + 1):
        try:
            jevRes = requests.post(
                urlJev,
                headers=jevHeaders,
                json=jevPayload,
                timeout=120,
            )
            jevRes.raise_for_status()
            jevAnswers = jevRes.json()['answers']
            for searchResult in methodRes:
                searchId = searchResult['id']
                jevAnswers[searchId]['score']
            break
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            requests.exceptions.RequestException,
        ) as responseError:
            match responseError:
                case requests.exceptions.HTTPError():
                    statusCode = responseError.response.status_code
                    errorReason = (
                        f"the server answered with error {statusCode}"
                    )
                case json.JSONDecodeError():
                    errorReason = "the answer was not valid JSON"
                case requests.exceptions.RequestException():
                    errorReason = "the connection to the server failed"
                case KeyError():
                    errorReason = "the answer was missing expected fields"
                case _:
                    errorReason = str(responseError)
            if jevAttempt < MAX_JEV_ATTEMPTS:
                fallbackMessage = (
                    f"Could not score the evidence: {errorReason}. "
                    f"Retrying ({jevAttempt + 1}/"
                    f"{MAX_JEV_ATTEMPTS})..."
                )
            else:
                fallbackMessage = (
                    f"Could not score the evidence: {errorReason}. "
                    f"No attempts left."
                )
            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )
    else:
        raise RuntimeError(
            "Could not score the evidence after all retry attempts."
        )

    for searchResult in methodRes:
        searchId = searchResult['id']
        searchResult['promising'] = jevAnswers[searchId]['score']
        einsteinRes.append(searchResult)

    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================

    click.echo("")
    click.echo(
        click.style("  Einstein complete", fg=(201, 138, 160), bold=True)
    )
    click.echo(
        click.style("  searches done  ", fg=(154, 144, 136), bold=True)
        + click.style(str(len(einsteinRes)), fg=(243, 234, 223))
    )
    click.echo("")

    # ======================================================================

    return einsteinRes
