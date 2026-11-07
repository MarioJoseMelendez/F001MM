# F001MM

F001MM means Falen test 001 Mario Melendez.

This repository is a first attempt at a scientific-agent architecture. It takes
a problem, researches the literature, proposes hypotheses as executable code,
runs them and evaluates the measured result.

## What we found

The architecture ran end to end. It was very expensive, and it did not improve
the results. The extra agents added tokens, requests, latency and failure
points. In several cases the pipeline produced worse answers than one direct
model call.

We do not recommend this design. A paper will be added to this repository later
and will examine the cost, the failure modes and the comparison against a
baseline call.

## Architecture

```
user prompt
   │
   ▼
Translator ──► experiment contract (topic, limitations, baseline, metrics)
   │
   ▼
Einstein ────► literature research (web + papers, one planning response)
   │
   ▼
Researcher ──► hypothesis plan (JEV decides how many hypotheses)
   │
   ▼
Experimenter ► generated Python hypotheses, executed in temporaryCode/
   │
   ▼
Evaluator ───► measured results, compared against the baseline
   │
   ▼
Compressor ──► ranks the measured hypotheses
   │
   ▼
explanation printed to the user
```

**Translator** (`orchestrator.py`) converts the prompt into a JSON contract with
the topic, the limitations, the baseline and the variables to measure. It only
uses a baseline the user provided and never invents measurements.

**Einstein** (`einstein.py`) proposes web and paper searches in one planning
response. `globalFuncs.py` runs them through DDGS and OpenAlex and fetches
content for the most promising results.

**Researcher, Experimenter and Evaluator** (`compressor.py`) filter the
evidence, ask JEV for a hypothesis count, generate candidate Python code, run it
and evaluate the output.

**Compressor** ranks the hypotheses that survived evaluation.

**Tracker** (`tracker.py`) records problems and results. It uses Supabase when
credentials exist and SQLite otherwise.

The loop is sequential. There is no parallel agent execution and no
cross-agent retry loop.

## Layout

```
F001MM/
├── interface.py                     # click shell, the agent CLI
├── sessionBroker.py                 # one ttyd per browser session and proxy
├── start.sh                         # starts the broker
├── tracker.py                       # optional ops logging (Supabase or SQLite)
├── requirements.txt
├── .env.example
└── src/agents/
    ├── globalFuncs.py               # web and paper search, code generation and execution
    └── enterprise/
        ├── orchestrator.py          # Translator, loop orchestration, explanation
        ├── einstein.py              # research agent
        ├── compressor.py            # Researcher, Experimenter and Evaluator
        ├── prompts.json             # Einstein prompts
        └── temporaryCode/           # hypothesis code written and cleaned per run
```

The agent files keep the original flat imports. `interface.py` adds the agent
directories to `sys.path` before importing the loop.

## Requirements

- Python 3.13
- [ttyd](https://github.com/tsl0922/ttyd) on `PATH` for the browser terminal.
  You can set `FALEN_TTYD_BIN` instead.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in the keys
```

## API keys

Create a `.env` file from `.env.example`.

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | Every LLM call in the loop (Translator, Einstein, hypotheses, explanation) |
| `JEV_API_KEY` | yes | TypeSafe JEV, used to decide how many hypotheses to generate |
| `FALEN_CODE_DIR` | no | Directory where hypothesis code is written. The broker sets it per session |
| `FALEN_SESSION_ID` | no | Session id attached to tracker records |
| `FALEN_TTYD_BIN` | no | Path to `ttyd` when it is not on `PATH` |
| `PORT` | no | Broker port, default `7681` |
| `SUPABASE_URL` and `SUPABASE_SECRET_KEY` | no | Remote ops logging. Without them the tracker uses SQLite |
| `FALEN_TRACKER_DB` | no | Local tracker SQLite path |

The loop spends real tokens on OpenRouter on every run. A single problem can
trigger several model calls plus web and paper fetches.

## How to test it

### Terminal only

```bash
python interface.py
```

The shell has these commands.

- `run` asks for a problem and starts the full loop.
- `kernelExample` runs a fixed matrix-multiplication problem.
- `about`, `manual`, `introduce` and `exit` cover the rest.

Try these first.

1. `about` renders the architecture without calling any API.
2. `kernelExample` with a trivial NumPy problem exercises the full pipeline.
3. Inspect `src/agents/enterprise/temporaryCode/` while it runs. Generated
   hypotheses are written there and deleted at the end.
4. Change `FALEN_CODE_DIR` to keep the generated code for inspection.

### Browser terminal with ttyd

```bash
bash start.sh
# or, on Windows without a POSIX shell
python sessionBroker.py
```

The broker listens on `PORT`, default `7681`. Open `http://localhost:7681/`.
Each visitor is redirected to `/s/<sessionId>/`, where a dedicated `ttyd`
process runs `interface.py` with its own code directory under `sessions/`.

## Notes and limitations

- Generated Python code is executed locally without isolation. Do not run this
  on a machine you do not trust the model with.
- Generated `.py` files in `sessions/` and `temporaryCode/` are deleted at the
  end of a run.
- The loop is sequential and has no per-agent retries beyond simple HTTP
  retries.
- The evaluation step measures what the generated code reports. It does not
  prove that the measurement is meaningful.
- There is no academic path and no HTTP API in this repository.

## Paper

A paper about this architecture will be added to this repository later.

## License

This work is licensed under the Creative Commons Attribution 4.0
International License. See `LICENSE`.

If you use it, cite this repository.

> Mario José Melendez Vasquez. F001MM, Falen test 001.
> https://github.com/MarioJoseMelendez/F001MM

The license requires attribution. Keep the citation when you reuse the
material.
