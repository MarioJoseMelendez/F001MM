import json
import os
import sys
from pathlib import Path

_agentsDir = Path(__file__).resolve().parents[1]
_repoRoot = Path(__file__).resolve().parents[3]
sys.path.append(str(_repoRoot))
if str(_agentsDir) not in sys.path:
    sys.path.insert(0, str(_agentsDir))

import click
import requests
from dotenv import load_dotenv

from compressor import Compressor
from einstein import einstein
from tracker import RecordFalenRes, RecordProblemSubmitted


load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
urlOpenRouter = 'https://openrouter.ai/api/v1/chat/completions'
MAX_OPENROUTER_ATTEMPTS = 3


def Orchestrator(userPrompt):

    # Broker sets FALEN_SESSION_ID; local CLI falls back to "local".
    sessionId = os.environ.get("FALEN_SESSION_ID", "local")
    RecordProblemSubmitted(sessionId, userPrompt)

    #======================================================================
    # [1] Translator
    #======================================================================

    # =========== {1} Define Optimization Experiment ===========

    translatorHeaders = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    translatorPayload = {
        "model": "openrouter/free",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Translator. You convert one user prompt into a "
                    "JSON contract for an optimization experiment.\n\n"
                    "You will receive a JSON object with:\n"
                    "- `userPrompt`: the only real input. This text is the "
                    "topic. Copy it in your reasoning exactly, word for word.\n"
                    "- `limitations`: an empty list you must fill.\n"
                    "- `baseline`: an empty object you must fill.\n\n"
                    "Follow these steps in order:\n"
                    "1. Read `userPrompt`. Treat that exact text as the topic. "
                    "Do not rewrite it. Do not shorten it. Do not add words.\n"
                    "2. Decide the problem class: math, programming, or other.\n"
                    "3. Fill `limitations`.\n"
                    "   - Use only limitations the user stated.\n"
                    "   - If the user did not state limitations, infer the "
                    "minimum constraints that this problem class requires.\n"
                    "   - Example: a matrix math problem implies keep the same "
                    "numerical result and use fewer or simpler steps.\n"
                    "   - Do not invent extra constraints the problem does not "
                    "imply.\n"
                    "4. Fill `baseline`.\n"
                    "   - Use ONLY prior attempts, results, or a Python file "
                    "the user mentioned.\n"
                    "   - If the user gave numbers, put them in "
                    "`baseline.results` with those names.\n"
                    "   - If the user gave a .py path, put it in `code_path`. "
                    "Write `description` from their words.\n"
                    "   - If the user gave neither results nor a file, do not "
                    "invent measurements or paths.\n"
                    "   - If there are no baseline results: choose the "
                    "evaluation variable name(s) from the problem. Example: "
                    "want a matrix solved with less procedure → a metric that "
                    "captures that, named clearly. Fill `results` as a dict of "
                    "those names. Values must be null, not fake numbers.\n"
                    "   - If there is no Python file, `code_path` must be \"\".\n"
                    "   - If there is no user-provided baseline, write that in "
                    "`description`. Do not invent a library, file, or method "
                    "the user did not mention.\n"
                    "5. Write zero assumptions about facts the user did not "
                    "provide. No fake latency. No fake files. No fake "
                    "libraries. Inferring limitation text and metric NAMES "
                    "when missing is allowed. Inventing data is not.\n\n"
                    "Your answer must be only this JSON object and nothing "
                    "else:\n"
                    "{\"limitations\": [\"...\"], \"baseline\": "
                    "{\"description\": \"...\", \"code_path\": \"\", "
                    "\"results\": {\"metric_name\": null}}}\n\n"
                    "Rules for the answer:\n"
                    "- The keys must be exactly `limitations` and `baseline`. "
                    "Do not add other keys. Do not add `topic`.\n"
                    "- `limitations` must be a list of strings.\n"
                    "- `baseline` must be an object with exactly these keys: "
                    "`description`, `code_path`, `results`.\n"
                    "- `description` must be a string.\n"
                    "- `code_path` must be a string. Use \"\" unless the user "
                    "gave a Python file path.\n"
                    "- `results` must be an object with at least one metric "
                    "name. Each value must be a number the user provided, or "
                    "null. Never invent a number.\n"
                    "- Do not write explanations, Markdown, code fences, or "
                    "any text before or after the JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "userPrompt": userPrompt,
                        "limitations": [],
                        "baseline": {
                            "description": "",
                            "code_path": "",
                            "results": {},
                        },
                    },
                    indent=2,
                ),
            },
        ],
    }






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(click.style("  Translator", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Converting your prompt into an experiment contract...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
        try:
            translatorRequest = requests.post(
                urlOpenRouter,
                headers=translatorHeaders,
                json=translatorPayload,
                timeout=120,
            )
            translatorRequest.raise_for_status()

            translatorResponse = translatorRequest.json()
            translatorMessage = translatorResponse[
                'choices'
            ][0]['message']['content']

            if translatorMessage is None:
                raise ValueError("the model returned an empty answer")

            translatorRes = json.loads(translatorMessage)

            if not isinstance(translatorRes, dict):
                raise TypeError("the answer was not a JSON object")

            if set(translatorRes.keys()) != {"limitations", "baseline"}:
                raise ValueError("the answer used unexpected fields")

            limitations = translatorRes["limitations"]

            if not isinstance(limitations, list) or not limitations:
                raise ValueError("no limitations were returned")

            for limitation in limitations:
                if not isinstance(limitation, str):
                    raise ValueError("a limitation was not written as text")

            baseline = translatorRes["baseline"]

            if not isinstance(baseline, dict):
                raise TypeError("baseline was not a JSON object")

            if set(baseline.keys()) != {"description", "code_path", "results"}:
                raise ValueError("baseline used unexpected fields")

            if not isinstance(baseline["description"], str):
                raise ValueError("description was not written as text")

            if not isinstance(baseline["code_path"], str):
                raise ValueError("code_path was not written as text")

            baselineResults = baseline["results"]

            if not isinstance(baselineResults, dict) or not baselineResults:
                raise ValueError("no evaluation variables were returned")

            for metricName in baselineResults:
                metricValue = baselineResults[metricName]

                if metricValue is None:
                    continue

                if isinstance(metricValue, bool):
                    raise ValueError("a result value was not a number or null")

                if not isinstance(metricValue, (int, float)):
                    raise ValueError("a result value was not a number or null")

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
                    f"Could not translate the problem: {errorReason}. "
                    f"Retrying ({openRouterAttempt + 1}/"
                    f"{MAX_OPENROUTER_ATTEMPTS})..."
                )
            else:
                fallbackMessage = (
                    f"Could not translate the problem: {errorReason}. "
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
            "Could not translate the problem after all retry attempts."
        )

    # topic is always the user prompt so the model cannot drift.
    topic = userPrompt
    limitations = translatorRes["limitations"]
    baseline = translatorRes["baseline"]

    baselineCodePath = baseline["code_path"]
    thereBaseline = False

    if baselineCodePath is not None and baselineCodePath != "":
        if not baselineCodePath.endswith(".py"):
            click.echo(
                click.style(
                    "Only .py files are accepted for the moment.",
                    fg=(228, 180, 196),
                )
            )
            raise ValueError("Only .py files are accepted for the moment.")

        thereBaseline = True
    else:
        baseline["code_path"] = ""

    generalContext = {
        "topic": topic,
        "limitations": limitations,
        "baseline": baseline,
        "thereBaseline": thereBaseline,
    }






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style("  Translator complete", fg=(201, 138, 160), bold=True)
    )
    click.echo(
        click.style("  topic        ", fg=(154, 144, 136), bold=True)
        + click.style(topic, fg=(243, 234, 223))
    )
    click.echo(click.style("  limitations", fg=(154, 144, 136), bold=True))
    for limitationText in limitations:
        click.echo(click.style(f"    - {limitationText}", fg=(243, 234, 223)))
    click.echo(
        click.style("  baseline     ", fg=(154, 144, 136), bold=True)
        + click.style(baseline["description"], fg=(243, 234, 223))
    )
    click.echo(
        click.style("  thereBaseline", fg=(154, 144, 136), bold=True)
        + click.style(f" {thereBaseline}", fg=(243, 234, 223))
    )
    click.echo("")
    click.echo(
        click.style(
            "  Starting Einstein — researching literature.",
            fg=(201, 138, 160),
        )
    )
    click.echo("")
    # ======================================================================






    einsteinRes = einstein(
        topic=topic,
        limitations=limitations,
        baseline=baseline,
        thereBaseline=thereBaseline,
    )






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(click.style("  Researcher", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Planning hypotheses from Einstein's evidence...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    falenRes = Compressor(generalContext, einsteinRes)
    # Persist compressor output for this session before explain/cleanup.
    RecordFalenRes(sessionId, falenRes)






    #======================================================================
    # [2] Explain Results
    #======================================================================

    # =========== {2} Explain Results to User ===========

    explainHeaders = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    explainPayload = {
        "model": "openrouter/free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain experiment results to the user in clear "
                    "English. Use only the context you receive. Do not invent "
                    "numbers or hypotheses that are not in the context. Write "
                    "plain text for the user, not JSON and not Markdown code "
                    "fences."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Explain these results to the user.",
                        "falenRes": falenRes,
                    },
                    indent=2,
                ),
            },
        ],
    }






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style("  Explaining results", fg=(228, 180, 196), bold=True)
    )
    click.echo(
        click.style(
            "  Turning the experiment findings into a clear summary...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
        try:
            explainRequest = requests.post(
                urlOpenRouter,
                headers=explainHeaders,
                json=explainPayload,
                timeout=120,
            )
            explainRequest.raise_for_status()

            explainResponse = explainRequest.json()
            explainMessage = explainResponse[
                'choices'
            ][0]['message']['content']

            if explainMessage is None:
                raise ValueError("the model returned an empty answer")

            explainText = str(explainMessage).strip()

            if not explainText:
                raise ValueError("the model returned an empty answer")

            break
        except (
            KeyError,
            TypeError,
            ValueError,
            requests.exceptions.RequestException,
        ) as responseError:
            match responseError:
                case requests.exceptions.HTTPError():
                    statusCode = responseError.response.status_code
                    errorReason = f"the server answered with error {statusCode}"
                case requests.exceptions.RequestException():
                    errorReason = "the connection to the server failed"
                case KeyError():
                    errorReason = "the answer was missing expected fields"
                case _:
                    errorReason = str(responseError)

            if openRouterAttempt < MAX_OPENROUTER_ATTEMPTS:
                fallbackMessage = (
                    f"Could not explain the results: {errorReason}. "
                    f"Retrying ({openRouterAttempt + 1}/"
                    f"{MAX_OPENROUTER_ATTEMPTS})..."
                )
            else:
                fallbackMessage = (
                    f"Could not explain the results: {errorReason}. "
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
            "Could not explain the results after all retry attempts."
        )






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style("  Results summary", fg=(201, 138, 160), bold=True)
    )
    click.echo("")
    click.echo(
        click.style(explainText, fg=(243, 234, 223))
    )
    click.echo("")
    # ======================================================================






    # =========== {3} Clean Temporary Code ===========

    # TODO: When the loop is complete and larger context is needed, the code
    # must NOT delete the hypothesis context.
    sessionCodeDir = os.environ.get("FALEN_CODE_DIR")
    if sessionCodeDir:
        playgroundPath = sessionCodeDir
    else:
        playgroundPath = str(
            Path(__file__).resolve().parent / "temporaryCode"
        )

    if os.path.isdir(playgroundPath):
        for fileName in os.listdir(playgroundPath):
            if not fileName.endswith(".py"):
                continue

            codeFilePath = os.path.join(playgroundPath, fileName)
            os.remove(codeFilePath)
