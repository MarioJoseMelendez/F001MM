import json
import os
from pathlib import Path

import click
import requests
from dotenv import load_dotenv
from globalFuncs import createCode, executeCode


load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
JEV_API_KEY = os.getenv('JEV_API_KEY')
urlOpenRouter = 'https://openrouter.ai/api/v1/chat/completions'
urlJev = 'https://api.typesafe.ai/v1/systemone'
MAX_OPENROUTER_ATTEMPTS = 3
MAX_JEV_ATTEMPTS = 3


def Compressor(generalContext, einsteinRes):
    topic = generalContext["topic"]
    limitations = generalContext["limitations"]
    baseline = generalContext["baseline"]
    thereBaseline = generalContext["thereBaseline"]

    #======================================================================
    # [1] Researcher
    #======================================================================

    # =========== {2} Gather Einstein Evidence ===========

    # This lightweight context guides planning without sending full source content.
    compressorContext = []

    for searchResult in einsteinRes:
        searchTitle = searchResult.get("search")

        if not searchTitle:
            searchTitle = searchResult.get("title")

        searchSummary = searchResult.get("body")

        if not searchSummary:
            searchSummary = searchResult.get("abstract_inverted_index")

        if not searchSummary:
            searchSummary = ""

        compressorContext.append({
            "id": searchResult["id"],
            "promising": searchResult["promising"],
            "search": searchTitle,
            "summary": searchSummary,
        })


    # =========== {3} Choose Hypothesis Count ===========






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(click.style("  Researcher", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Asking JEV how many hypotheses to create...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    hypothesisCriteria = {}

    for count in range(5, 51):
        hypothesisCount = str(count)
        hypothesisDescription = f"Create exactly {count} distinct hypotheses."
        hypothesisCriteria[hypothesisCount] = hypothesisDescription

    jevHeaders = {
        "Authorization": f"Bearer {JEV_API_KEY}",
        "Content-Type": "application/json",
    }

    jevState = {
        "problem": {
            "topic": topic,
            "limitations": limitations,
        },
        "research_results": compressorContext,
    }

    jevPayload = {
        "model": "jev-latest",
        "state": jevState,
        "questions": {
            "hypothesis_count": {
                "type": "choice",
                "instructions": (
                    "How many distinct implementation hypotheses should be "
                    "created for this problem? Choose the smallest sufficient "
                    "whole number between 5 and 50."
                ),
                # TODO: Revisit the 5-50 hypothesis range as the project evolves.
                "criteria": hypothesisCriteria,
            },
        },
    }

    for jevAttempt in range(1, MAX_JEV_ATTEMPTS + 1):
        try:
            jevRequest = requests.post(
                urlJev,
                headers=jevHeaders,
                json=jevPayload,
                timeout=120,
            )
            jevRequest.raise_for_status()

            jevResponse = jevRequest.json()
            hypothesisAnswer = jevResponse['answers']['hypothesis_count']
            numHypotheses = int(hypothesisAnswer['choice'])

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
                    errorReason = "the response was not valid JSON"
                case requests.exceptions.RequestException():
                    errorReason = "the connection to the server failed"
                case KeyError():
                    errorReason = "the response did not include a hypothesis count"
                case _:
                    errorReason = "the hypothesis count was not a valid number"

            if jevAttempt < MAX_JEV_ATTEMPTS:
                fallbackMessage = (
                    f"Could not decide how many hypotheses to create: "
                    f"{errorReason}. Retrying ({jevAttempt + 1}/"
                    f"{MAX_JEV_ATTEMPTS})..."
                )
            else:
                fallbackMessage = (
                    f"Could not decide how many hypotheses to create: "
                    f"{errorReason}. No attempts left."
                )

            click.echo(
                click.style(
                    fallbackMessage,
                    fg=(228, 180, 196),
                )
            )
    else:
        raise RuntimeError(
            "Could not decide how many hypotheses to create after all retry "
            "attempts."
        )






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style("  JEV decision", fg=(201, 138, 160), bold=True)
    )
    click.echo(
        click.style("  numHypotheses  ", fg=(154, 144, 136), bold=True)
        + click.style(str(numHypotheses), fg=(243, 234, 223))
    )
    click.echo(
        click.style(
            "  Researcher will now write each hypothesis.",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    compressorHeaders = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    baselineCodePath = baseline["code_path"]

    if thereBaseline:
        with open(baselineCodePath, "r", encoding="utf-8") as baselineFile:
            baselineCode = baselineFile.read()
    else:
        baselineCode = ""

    researcherRes = []

    for hypothesisNumber in range(numHypotheses):






        # ======================================================================
        # TODO: Embedded interface only. Remove this block later.
        # ======================================================================
        click.echo("")
        click.echo(
            click.style(
                f"  Hypothesis {hypothesisNumber + 1}/{numHypotheses}",
                fg=(228, 180, 196),
                bold=True,
            )
        )
        click.echo(
            click.style("  Writing hypothesis...", fg=(154, 144, 136))
        )
        click.echo("")
        # ======================================================================






        # =========== {4} Select Supporting Evidence ===========

        compressorPayload = {
            "model": "openrouter/free",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You will receive a JSON object with two parts:\n"
                        "- `problem`: the topic and the limitations that must "
                        "be respected. This is not always \"improve existing "
                        "source code\". There may later be a baseline that is "
                        "code, a formula, a prior attempt, something currently "
                        "being tried, or another artifact. There may also be NO "
                        "baseline: starting from zero with only the problem.\n"
                        "- `evidence`: a list of research results. Each result "
                        "has an `id`, a `promising` score from 0 to 1 (higher "
                        "means more useful), a `search` title, and a short "
                        "`summary`.\n\n"
                        "Follow these steps in order:\n"
                        "1. Read `problem` so you know the topic and which "
                        "limitations must be respected. Do not assume the work "
                        "is rewriting a Python file.\n"
                        "2. Read every item in `evidence`.\n"
                        "3. Pick the items you need to read in full before "
                        "writing one hypothesis. That hypothesis may improve an "
                        "existing baseline or invent a first solution if there "
                        "is none. Prefer items with higher `promising` scores. "
                        "Skip items unrelated to the problem.\n"
                        "4. Pick at least one item.\n"
                        "5. Copy the `id` of every item you picked exactly as it "
                        "appears.\n\n"
                        "Your answer must be only this JSON object and nothing "
                        "else:\n"
                        "{\"letsSee\": [\"0\", \"2\"]}\n\n"
                        "Rules for the answer:\n"
                        "- \"0\" and \"2\" are only an example. Use the real ids "
                        "you picked.\n"
                        "- The key must be exactly `letsSee`. Do not add other "
                        "keys.\n"
                        "- Every id must be a string, for example \"3\", not 3.\n"
                        "- Do not write explanations, Markdown, code fences, or "
                        "any text before or after the JSON.\n"
                        "- Do not write the hypothesis yet."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "problem": {
                                "topic": topic,
                                "limitations": limitations,
                            },
                            "evidence": compressorContext,
                        },
                        indent=2,
                    ),
                },
            ],
        }

        # TODO: In the future we have to separate evidence in two lists.
        # TODO: One used to log the evidence used to create the hypothesis.
        # TODO: The other used by the agent to select the evidence in each iteration of creating a hy
        # TODO: Currently exists a single call to create a hypothesis, its not necessary yet.

        availableEvidenceIds = []

        for searchResult in compressorContext:
            availableEvidenceIds.append(str(searchResult["id"]))

        for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
            try:
                compressorRequest = requests.post(
                    urlOpenRouter,
                    headers=compressorHeaders,
                    json=compressorPayload,
                    timeout=120,
                )
                compressorRequest.raise_for_status()

                compressorResponse = compressorRequest.json()
                compressorMessage = compressorResponse[
                    'choices'
                ][0]['message']['content']

                if compressorMessage is None:
                    raise ValueError("the model returned an empty answer")

                compressorRes = json.loads(compressorMessage)

                if not isinstance(compressorRes, dict):
                    raise TypeError("the answer was not a JSON object")

                if set(compressorRes.keys()) != {"letsSee"}:
                    raise ValueError("the answer used unexpected fields")

                letsSee = compressorRes["letsSee"]

                if not isinstance(letsSee, list) or not letsSee:
                    raise ValueError("no evidence was selected")

                for evidenceId in letsSee:
                    if not isinstance(evidenceId, str):
                        raise ValueError("an evidence ID was not written as text")

                    if evidenceId not in availableEvidenceIds:
                        raise ValueError("an evidence ID does not exist")

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
                        f"Could not select the evidence to read: {errorReason}. "
                        f"Retrying ({openRouterAttempt + 1}/"
                        f"{MAX_OPENROUTER_ATTEMPTS})..."
                    )
                else:
                    fallbackMessage = (
                        f"Could not select the evidence to read: {errorReason}. "
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
                "Could not select the evidence to read after all retry attempts."
            )

        # These IDs determine which complete Einstein results enter the next stage.
        letsSee = compressorRes["letsSee"]


        # =========== {5} Create Grounded Hypothesis ===========

        selectedIds = []

        for evidenceId in letsSee:
            selectedIds.append(str(evidenceId))

        # Selected records retain every field from Einstein, including full content.
        selectedEvidence = []

        for searchResult in einsteinRes:
            if searchResult["id"] in selectedIds:
                selectedEvidence.append(searchResult)

        hypothesisMessages = [
            {
                "role": "system",
                "content": (
                    "You will receive a JSON object with these parts:\n"
                    "- `hypothesis_number`: the number of the hypothesis you are "
                    "creating now.\n"
                    "- `problem`: `topic`, `limitations`, `baseline` "
                    "(`description`, `code_path`, `results`), and "
                    "`baseline_code` when a file was loaded. The baseline is NOT "
                    "always source code.\n"
                    "- `evidence_selection`: the ids chosen in the previous "
                    "step.\n"
                    "- `selected_evidence`: the complete research sources for "
                    "those ids, including their full `content`.\n"
                    "- `previous_hypotheses`: hypotheses already created. It may "
                    "be empty.\n\n"
                    "Facts you must use:\n"
                    "1. The baseline is NOT always source code. It may be code, "
                    "a formula, a prior attempt, something currently being "
                    "tried, or another artifact in `problem.baseline` "
                    "(`description`, `code_path`, `results`).\n"
                    "2. Your hypothesis depends on: (a) what we want to obtain, "
                    "which is in `problem.baseline.results` (the master-context "
                    "metrics); (b) what the baseline actually is.\n"
                    "3. There may be NO baseline: starting from zero with only "
                    "the problem (topic + limitations). If so, invent the first "
                    "solution from the problem. Still respect every limitation. "
                    "Still produce the same JSON keys: `hypothesis`, `sources`, "
                    "and `implementationPrompt`.\n\n"
                    "Follow these steps in order:\n"
                    "1. Read `problem.topic` and `problem.limitations`. Then read "
                    "`problem.baseline` as it actually is. If `baseline_code` is "
                    "real source code, understand it. If the baseline is a "
                    "formula, a description, a prior attempt, or empty, do not "
                    "treat the task as \"rewrite this Python file\".\n"
                    "2. Find one concrete idea. Ground it in the baseline "
                    "artifact, the problem, or the evidence. Do not invent "
                    "unsupported reasons. Do not assume the only goal is making "
                    "Python code faster.\n"
                    "3. Question your idea before accepting it. Ask: Is it "
                    "supported by the baseline, the problem, or the evidence? "
                    "Does it respect every limitation? Could it make the results "
                    "wrong? If any answer is bad, choose another idea. Critical "
                    "thinking matters more than anything else.\n"
                    "4. Compare your idea with every item in "
                    "`previous_hypotheses`. If it shares the main idea, the "
                    "mechanism, or an important implementation detail with any "
                    "of them, discard it and choose a clearly different idea.\n"
                    "5. Write `hypothesis`: say what to try, why it should "
                    "improve the result variables we want (or why it is a valid "
                    "first solution if starting from zero), and which evidence "
                    "ids support it.\n"
                    "6. Write `sources`: the list of evidence ids from "
                    "`evidence_selection` that support your hypothesis. Include "
                    "at least one id. Copy each id exactly as it appears, as a "
                    "string. Only use ids from `evidence_selection`.\n"
                    "7. Write `implementationPrompt`: the instructions for the "
                    "next model. That next model has only one job: write the "
                    "artifact needed to measure the result variables (often "
                    "Python code that implements or tests the idea). It will "
                    "not run the artifact, test it, measure it, or decide if it "
                    "works. Testing and measuring happen later in a different "
                    "step, so do not ask it to do them. Write "
                    "`implementationPrompt` as you would for a very intelligent "
                    "inexperienced coder: it learns fast and follows "
                    "instructions exactly, but it does not know this project, "
                    "it does not guess missing details, and it needs every step "
                    "explained in simple, concrete words. Do not call that next "
                    "model a child. Therefore `implementationPrompt` must:\n"
                    "   a. Describe how to produce that artifact. If the "
                    "baseline is code, name what to change. If it is a formula, "
                    "a description, or an empty start, say how to implement "
                    "from that. Do not wrap the whole world as \"rewrite this "
                    "Python file\".\n"
                    "   b. Give numbered steps in order, saying exactly what to "
                    "add, what to replace, and what to keep.\n"
                    "   c. Explain in simple words why each important step is "
                    "done and which evidence supports it.\n"
                    "   d. List everything that must not change: every "
                    "limitation, and if the baseline is code with an interface, "
                    "that interface (function signature, inputs, outputs, data "
                    "types, dimensions). If there is no baseline, the "
                    "limitations still apply.\n"
                    "   e. Forbid new libraries, unrelated edits, and "
                    "optimizations not required by the hypothesis.\n"
                    "   f. Describe exactly what the finished artifact must do "
                    "and what result variables it must make measurable, so it "
                    "is correct without the next model having to test it.\n"
                    "   g. Not ask the next model to run, test, benchmark, or "
                    "verify anything. It only writes the artifact, which the "
                    "flow still stores as {\"code\": \"...\"}.\n"
                    "   h. Not contain the finished artifact. It describes the "
                    "work; the next model writes it.\n\n"
                    "Your answer must be only this JSON object and nothing "
                    "else:\n"
                    "{\"hypothesis\": \"...\", \"sources\": [\"0\"], "
                    "\"implementationPrompt\": \"...\"}\n\n"
                    "Rules for the answer:\n"
                    "- Replace each \"...\" with your text. Neither text value "
                    "can be empty.\n"
                    "- `hypothesis` and `implementationPrompt` must be strings, "
                    "not lists, objects, or null.\n"
                    "- `sources` is required. It must be a list with at least "
                    "one id, and every id must be a string that appears in "
                    "`evidence_selection`. \"0\" is only an example.\n"
                    "- Use exactly the keys `hypothesis`, `sources`, and "
                    "`implementationPrompt`. Do not add other keys.\n"
                    "- Inside the strings, write line breaks as \\n so the JSON "
                    "stays valid.\n"
                    "- Do not write explanations, Markdown, code fences, safety "
                    "labels, or any text before or after the JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "hypothesis_number": hypothesisNumber + 1,
                        "problem": {
                            "topic": topic,
                            "limitations": limitations,
                            "baseline": baseline,
                            "baseline_code": baselineCode,
                        },
                        "evidence_selection": compressorRes,
                        "selected_evidence": selectedEvidence,
                        "previous_hypotheses": researcherRes,
                    },
                    indent=2,
                ),
            },
        ]

        hypothesisPayload = {
            "model": "openrouter/free",
            "response_format": {"type": "json_object"},
            "messages": hypothesisMessages,
        }

        for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
            try:
                hypothesisRequest = requests.post(
                    urlOpenRouter,
                    headers=compressorHeaders,
                    json=hypothesisPayload,
                    timeout=120,
                )
                hypothesisRequest.raise_for_status()

                hypothesisResponse = hypothesisRequest.json()
                hypothesisMessage = hypothesisResponse[
                    'choices'
                ][0]['message']['content']

                if hypothesisMessage is None:
                    raise ValueError("the model returned an empty answer")

                hypothesisData = json.loads(hypothesisMessage)

                if not isinstance(hypothesisData, dict):
                    raise TypeError("the answer was not a JSON object")

                expectedHypothesisKeys = {
                    "hypothesis",
                    "sources",
                    "implementationPrompt",
                }

                if "sources" not in hypothesisData:
                    raise ValueError("the hypothesis did not include its sources")

                if set(hypothesisData.keys()) != expectedHypothesisKeys:
                    raise ValueError("the answer used unexpected fields")

                if not isinstance(hypothesisData["hypothesis"], str):
                    raise ValueError("the hypothesis was not written as text")

                if not hypothesisData["hypothesis"].strip():
                    raise ValueError("the hypothesis was empty")

                if not isinstance(hypothesisData["implementationPrompt"], str):
                    raise ValueError(
                        "the implementation prompt was not written as text"
                    )

                if not hypothesisData["implementationPrompt"].strip():
                    raise ValueError("the implementation prompt was empty")

                hypothesisSources = hypothesisData["sources"]

                if not isinstance(hypothesisSources, list) or not hypothesisSources:
                    raise ValueError("the hypothesis did not include its sources")

                for sourceId in hypothesisSources:
                    if not isinstance(sourceId, str):
                        raise ValueError("a source ID was not written as text")

                    if sourceId not in selectedIds:
                        raise ValueError(
                            "a source ID was not part of the selected evidence"
                        )

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
                        f"Could not create hypothesis {hypothesisNumber + 1}: "
                        f"{errorReason}. Retrying ({openRouterAttempt + 1}/"
                        f"{MAX_OPENROUTER_ATTEMPTS})..."
                    )
                else:
                    fallbackMessage = (
                        f"Could not create hypothesis {hypothesisNumber + 1}: "
                        f"{errorReason}. No attempts left."
                    )

                click.echo(
                    click.style(
                        fallbackMessage,
                        fg=(228, 180, 196),
                    )
                )
        else:
            raise RuntimeError(
                f"Could not create hypothesis {hypothesisNumber + 1} after all "
                "retry attempts."
            )

        hypothesisRes = {
            "id": str(hypothesisNumber + 1),
            "hypothesis": hypothesisData["hypothesis"],
            "prompt": hypothesisData["implementationPrompt"],
            "sources": hypothesisSources,
        }
        researcherRes.append(hypothesisRes)






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style(
            "  Researcher complete. Hypotheses:",
            fg=(201, 138, 160),
            bold=True,
        )
    )
    for researcherHypothesis in researcherRes:
        hypothesisId = researcherHypothesis["id"]
        hypothesisText = researcherHypothesis["hypothesis"]
        click.echo("")
        click.echo(
            click.style(
                f"  hypothesis #{hypothesisId}",
                fg=(228, 180, 196),
                bold=True,
            )
        )
        click.echo(click.style(f"  {hypothesisText}", fg=(243, 234, 223)))
    click.echo("")
    # ======================================================================






    #======================================================================
    # [2] Experimenter
    #======================================================================
    # FALEN_CODE_DIR is one visitor's directory. Unset keeps the shared folder.
    sessionCodeDir = os.environ.get("FALEN_CODE_DIR")
    if sessionCodeDir:
        playgroundPath = sessionCodeDir
    else:
        playgroundPath = str(Path(__file__).resolve().parent / "temporaryCode")

    experimenterRes = []






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(click.style("  Experimenter", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Writing an implementation for each hypothesis...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    # =========== {6} Write Hypothesis Code ===========
    for hypothesisRes in researcherRes:
        experimentPayload = {
            "model": "openrouter/free",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You will receive a JSON object with two parts:\n"
                        "- `baseline_code`: contents loaded from the baseline "
                        "path when a file exists. The baseline is NOT always "
                        "source code.\n"
                        "- `implementation_prompt`: how to produce the "
                        "artifact.\n\n"
                        "Follow these steps in order:\n"
                        "1. Read `implementation_prompt` and follow it "
                        "exactly.\n"
                        "2. Decide what the baseline actually is. It may be "
                        "code, a formula, a prior attempt, something currently "
                        "being tried, or another artifact. There may be NO "
                        "useful baseline: starting from zero with only the "
                        "problem.\n"
                        "3. Write the artifact needed to measure the result "
                        "variables. This is often Python code that implements "
                        "or tests the idea. If the baseline is code, use it. If "
                        "it is a formula, a description, or an empty start, "
                        "implement from that. Do not wrap the whole world as "
                        "\"rewrite this Python file\".\n"
                        "4. Return only this JSON and nothing else:\n"
                        '{"code": "<complete Python file>"}\n\n'
                        "Rules for the answer:\n"
                        "- The key must be exactly `code`. Do not add other "
                        "keys.\n"
                        "- `code` must be a non-empty string.\n"
                        "- Do not write explanations, Markdown, code fences, or "
                        "any text before or after the JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "baseline_code": baselineCode,
                            "implementation_prompt": hypothesisRes["prompt"],
                        },
                        indent=2,
                    ),
                },
            ],
        }

        for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
            try:
                experimentRequest = requests.post(
                    urlOpenRouter,
                    headers=compressorHeaders,
                    json=experimentPayload,
                    timeout=120,
                )
                experimentRequest.raise_for_status()

                experimentMessage = experimentRequest.json()[
                    "choices"
                ][0]["message"]["content"]

                if experimentMessage is None:
                    raise ValueError("the model returned an empty answer")

                experimentData = json.loads(experimentMessage)

                if not isinstance(experimentData, dict):
                    raise TypeError("the answer was not a JSON object")

                if "code" not in experimentData:
                    raise ValueError("the answer did not include the code")

                if not isinstance(experimentData["code"], str):
                    raise ValueError("the code was not written as text")

                if not experimentData["code"].strip():
                    raise ValueError("the code was empty")

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
                        f"Could not write the code for hypothesis "
                        f"{hypothesisRes['id']}: {errorReason}. Retrying ("
                        f"{openRouterAttempt + 1}/{MAX_OPENROUTER_ATTEMPTS})..."
                    )
                else:
                    fallbackMessage = (
                        f"Could not write the code for hypothesis "
                        f"{hypothesisRes['id']}: {errorReason}. No attempts left."
                    )

                click.echo(
                    click.style(
                        fallbackMessage,
                        fg=(228, 180, 196),
                    )
                )
        else:
            raise RuntimeError(
                f"Could not write the code for hypothesis {hypothesisRes['id']} "
                "after all retry attempts."
            )

        experimentRes = {
            "id": hypothesisRes["id"],
            "name": f"hypothesis{hypothesisRes['id']}",
            "code": experimentData["code"],
        }
        experimenterRes.append(experimentRes)

    # Clear accidental leftover scripts before new ones are created.
    if os.path.isdir(playgroundPath):
        for fileName in os.listdir(playgroundPath):
            if not fileName.endswith(".py"):
                continue

            codeFilePath = os.path.join(playgroundPath, fileName)
            os.remove(codeFilePath)

    # =========== {7} Save Hypothesis Code ===========
    for experimentRes in experimenterRes:
        createCode(
            name=experimentRes["name"],
            code=experimentRes["code"],
            motherPath=playgroundPath,
        )






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style("  Experimenter complete", fg=(201, 138, 160), bold=True)
    )
    click.echo(
        click.style("  implementations  ", fg=(154, 144, 136), bold=True)
        + click.style(str(len(experimenterRes)), fg=(243, 234, 223))
    )
    click.echo("")
    # ======================================================================






    #======================================================================
    # [3] Evaluator
    #======================================================================






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(click.style("  Evaluator", fg=(228, 180, 196), bold=True))
    click.echo(
        click.style(
            "  Adding tests and measuring each implementation...",
            fg=(154, 144, 136),
        )
    )
    click.echo("")
    # ======================================================================






    # =========== {8} Add Latency Tests ===========
    for hypothesisIndex in range(len(experimenterRes)):
        hypothesisRes = researcherRes[hypothesisIndex]
        experimentRes = experimenterRes[hypothesisIndex]
        addTestsPayload = {
            "model": "openrouter/free",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You will receive a JSON object with `problem`, "
                        "`hypothesis`, and `experiment_code`. "
                        "`experiment_code` is the artifact to measure, not "
                        "always a rewrite of an existing Python product file.\n\n"
                        "Follow these steps in order:\n"
                        "1. Return `experiment_code` EXACTLY the same, only "
                        "adding the tests needed to measure the variables in "
                        "`problem.baseline.results`. Use those exact names.\n"
                        "2. If `problem.baseline.results` is missing or empty, "
                        "do not add those prints. Leave the artifact unchanged "
                        "except you still return the same JSON shape.\n"
                        "3. For each variable in `problem.baseline.results`, "
                        "compute a numeric value into a Python variable, then "
                        "add exactly this print and no other — the print must "
                        "call the variable (f-string), not print a name as "
                        "literal text: "
                        'print(f"Falen> exactname:{variable}"). '
                        "Do not take the example literally as text to copy "
                        "into the print; do not print the variable name as a "
                        "string; print the numeric value held by the "
                        "variable. Metric NAMES come from "
                        "`problem.baseline.results`; `latency_ms` below is "
                        "only an abstract illustration of the pattern:\n"
                        "   latency_ms = <computed numeric value>\n"
                        "   print(f\"Falen> latency_ms:{latency_ms}\")\n"
                        "4. Every test must print a numeric result. It must "
                        "evaluate a number, strictly.\n"
                        "5. Return only this JSON: "
                        '{"code": "<complete Python file>"}'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "problem": {
                                "topic": topic,
                                "limitations": limitations,
                                "baseline": baseline,
                            },
                            "hypothesis": hypothesisRes["hypothesis"],
                            "experiment_code": experimentRes["code"],
                        },
                        indent=2,
                    ),
                },
            ],
        }

        for openRouterAttempt in range(1, MAX_OPENROUTER_ATTEMPTS + 1):
            try:
                addTestsRequest = requests.post(
                    urlOpenRouter,
                    headers=compressorHeaders,
                    json=addTestsPayload,
                    timeout=120,
                )
                addTestsRequest.raise_for_status()

                addTestsMessage = addTestsRequest.json()[
                    "choices"
                ][0]["message"]["content"]

                if addTestsMessage is None:
                    raise ValueError("the model returned an empty answer")

                addTestsData = json.loads(addTestsMessage)

                if not isinstance(addTestsData, dict):
                    raise TypeError("the answer was not a JSON object")

                if "code" not in addTestsData:
                    raise ValueError("the answer did not include the code")

                if not isinstance(addTestsData["code"], str):
                    raise ValueError("the code was not written as text")

                if not addTestsData["code"].strip():
                    raise ValueError("the code was empty")

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
                        f"Could not add tests for hypothesis "
                        f"{hypothesisRes['id']}: {errorReason}. Retrying ("
                        f"{openRouterAttempt + 1}/{MAX_OPENROUTER_ATTEMPTS})..."
                    )
                else:
                    fallbackMessage = (
                        f"Could not add tests for hypothesis "
                        f"{hypothesisRes['id']}: {errorReason}. No attempts left."
                    )

                click.echo(
                    click.style(
                        fallbackMessage,
                        fg=(228, 180, 196),
                    )
                )
        else:
            raise RuntimeError(
                f"Could not add tests for hypothesis {hypothesisRes['id']} "
                "after all retry attempts."
            )

        experimentRes["code"] = addTestsData["code"]
        createCode(
            name=experimentRes["name"],
            code=experimentRes["code"],
            motherPath=playgroundPath,
        )

    falenRes = []

    # =========== {9} Measure Hypothesis Code ===========
    for hypothesisIndex in range(len(experimenterRes)):
        hypothesisRes = researcherRes[hypothesisIndex]
        experimentRes = experimenterRes[hypothesisIndex]
        codeExecutions = executeCode(
            name=experimentRes["name"],
            motherPath=playgroundPath,
            numExecutions=5,
        )

        # These names come from the master context and decide which Falen> prints count as measurements.
        evaluatedVariables = []
        for measuredVariable in baseline["results"]:
            evaluatedVariables.append(measuredVariable)

        experimentRes["results"] = []
        # Each run stores its measured values for later averaging.
        for codeExecution in codeExecutions:
            # These lines are the terminal output that the Falen> search will read.
            terminalLines = []
            for terminalLine in codeExecution.stdout.splitlines():
                terminalLines.append(str(terminalLine))

            # runMatches keeps what this run obtained for each master-context variable.
            runMatches = []
            for terminalLine in terminalLines:
                for measuredVariable in evaluatedVariables:
                    if terminalLine.startswith(f"Falen> {measuredVariable}:"):
                        measuredNumber = float(terminalLine.split(":", 1)[1])
                        runMatches.append({
                            measuredVariable: measuredNumber,
                        })

            experimentRes["results"].append(runMatches)

        variableTotals = {}
        variableCounts = {}
        for measuredVariable in evaluatedVariables:
            variableTotals[measuredVariable] = 0
            variableCounts[measuredVariable] = 0

        for runMatches in experimentRes["results"]:
            for runMatch in runMatches:
                for measuredVariable in runMatch:
                    variableTotals[measuredVariable] = (
                        variableTotals[measuredVariable] + runMatch[measuredVariable]
                    )
                    variableCounts[measuredVariable] = (
                        variableCounts[measuredVariable] + 1
                    )

        # This average is the measured value of each master-context variable across all runs.
        avgResult = {}
        for measuredVariable in evaluatedVariables:
            avgResult[measuredVariable] = (
                variableTotals[measuredVariable] / variableCounts[measuredVariable]
            )
        experimentRes["avgResult"] = avgResult

        falenRes.append({
            "id": hypothesisRes["id"],
            "hypothesis": hypothesisRes["hypothesis"],
            "evidence": hypothesisRes["sources"],
            "avgResult": avgResult,
        })


    #======================================================================
    # [4] Compressor
    #======================================================================

    # =========== {10} Rank Best Hypotheses ===========
    # This ranking is what Falen returns after evaluation.
    compressorRes = []

    for measuredVariable in baseline["results"]:
        # topHypotheses is stored in compressorRes under this master-context variable.
        topHypotheses = []
        rankedHypothesisIds = []

        # Lower averages rank first; the master-context metrics treat a smaller number as better.
        for rankPosition in range(3):
            bestHypothesisId = None
            bestAverage = None
            for falenResult in falenRes:
                hypothesisId = falenResult["id"]
                if hypothesisId in rankedHypothesisIds:
                    continue

                hypothesisAverage = falenResult["avgResult"][measuredVariable]
                if bestAverage is None:
                    bestHypothesisId = hypothesisId
                    bestAverage = hypothesisAverage
                elif hypothesisAverage < bestAverage:
                    bestHypothesisId = hypothesisId
                    bestAverage = hypothesisAverage

            if bestHypothesisId is None:
                break

            # rankedHypothesisIds keeps this hypothesis from being ranked twice for the same variable.
            rankedHypothesisIds.append(bestHypothesisId)
            topHypotheses.append({
                bestHypothesisId: bestAverage,
            })

        compressorRes.append({
            measuredVariable: topHypotheses,
        })






    # ======================================================================
    # TODO: Embedded interface only. Remove this block later.
    # ======================================================================
    click.echo("")
    click.echo(
        click.style(
            "  Compressor ranking",
            fg=(201, 138, 160),
            bold=True,
        )
    )
    for rankedVariable in compressorRes:
        for measuredVariable in rankedVariable:
            topHypotheses = rankedVariable[measuredVariable]
            click.echo("")
            click.echo(
                click.style(
                    f"  {measuredVariable}",
                    fg=(228, 180, 196),
                    bold=True,
                )
            )
            rankPosition = 1
            for rankedHypothesis in topHypotheses:
                for hypothesisId in rankedHypothesis:
                    hypothesisAverage = rankedHypothesis[hypothesisId]
                    click.echo(
                        click.style(
                            f"    #{rankPosition}  hypothesis {hypothesisId}  "
                            f"{hypothesisAverage}",
                            fg=(243, 234, 223),
                        )
                    )
                rankPosition = rankPosition + 1
    click.echo("")
    # ======================================================================






    return falenRes
