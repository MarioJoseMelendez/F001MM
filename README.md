# F001MM — Scientific Agent (first attempt)

An experimental multi-agent loop that turns a natural-language problem into a
measured experiment: it reads the problem, researches the literature, proposes
hypotheses in code, runs them, and explains the result.

This repository is a **snapshot of the agent core** extracted from the Falen
project, with one change: it only ships the `enterprise` path. There is no
academic agent and no HTTP API here. The CLI is served over `ttyd`, one session
per visitor.

## How the loop works

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
explanation printed to the user
```

- **Translator** (`orchestrator.py`) converts the prompt into a JSON contract.
  It only uses a baseline the user actually provided; it does not invent
  measurements.
- **Einstein** (`einstein.py`) makes a single planning response that proposes
  searches. `globalFuncs.py` runs them locally through DDGS (web) and OpenAlex
  (papers), then fetches page content for the most promising results.
- **Researcher / Experimenter / Evaluator** (`compressor.py`) select the
  promising evidence, ask JEV for a hypothesis count, generate candidate
  Python code, execute it, and evaluate the measured output.
- **Tracker** (`tracker.py`) records submitted problems and results. It is
  optional: without Supabase credentials it falls back to local SQLite.

## Layout

```
F001MM/
├── interface.py                     # click shell — the actual agent CLI
├── sessionBroker.py                 # one ttyd per browser session + proxy
├── start.sh                         # starts the broker
├── tracker.py                       # optional ops logging (Supabase / SQLite)
├── requirements.txt
├── .env.example
└── src/agents/
    ├── globalFuncs.py               # web + paper search, code generation/execution
    └── enterprise/
        ├── orchestrator.py          # Translator, loop orchestration, explanation
        ├── einstein.py              # research agent
        ├── compressor.py            # Researcher / Experimenter / Evaluator
        ├── prompts.json             # Einstein prompts
        └── temporaryCode/           # hypothesis code written and cleaned per run
```

The agent files keep the original flat imports, so `interface.py` adds the
agent directories to `sys.path` before importing the loop.

## Setup

Requires Python 3.13 and [ttyd](https://github.com/tsl0922/ttyd) on `PATH`
(or point `FALEN_TTYD_BIN` at the binary).

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in the keys
```

## Run

### Terminal only

```bash
python interface.py
```

Then use the shell commands:

- `run` — ask for a problem and start the loop.
- `kernelExample` — run the fixed matrix-multiplication example.
- `introduce`, `about`, `manual`, `exit`.

### With ttyd

```bash
bash start.sh
```

The broker listens on `PORT` (default `7681`). Open `http://localhost:7681/`:
each visitor is redirected to `/s/<sessionId>/`, where a dedicated `ttyd`
process runs `interface.py` with its own code directory under `sessions/`.

On Windows without a POSIX shell, run the broker directly:

```bash
python sessionBroker.py
```

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | All LLM calls |
| `JEV_API_KEY` | yes | Hypothesis-count decision (TypeSafe JEV) |
| `FALEN_CODE_DIR` | no | Where hypothesis code is written; set per ttyd session |
| `FALEN_SESSION_ID` | no | Session id attached to tracker records |
| `FALEN_TTYD_BIN` | no | Path to `ttyd` when it is not on `PATH` |
| `PORT` | no | Broker port, default `7681` |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | no | Remote ops logging |
| `FALEN_TRACKER_DB` | no | Local tracker SQLite path |

## Status and limitations

- Single sequential loop; no retries across agents.
- One research response per run, with a fixed cap on searches.
- Generated code is executed locally without isolation.
- `sessions/` and `temporaryCode/` are scratch space: generated `.py` files are
  deleted when a run finishes.

## License

Not decided yet.
