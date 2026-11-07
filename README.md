# F001MM

**Falen test 001 Mario Melendez.**

F001MM is a first attempt at a **scientific-agent architecture**: a set of
specialized agents that take a problem, research the literature, propose
hypotheses as executable code, run them, and evaluate the measured result.

It is published as an honest record of a negative result.

## What we found

The architecture worked end to end, but it was **very expensive to run** and,
in the end, **did not add anything** over a conventional single model call.
The extra agents mostly added weight and latency: more tokens, more requests,
more moving parts, and more places for the loop to drift. In several cases the
multi-agent pipeline produced **worse answers than one direct call** to the
model.

F001MM is therefore not a recommended design. It is the object of study for a
paper that will be uploaded to this repository later, where the cost, the
failure modes, and the cases where the architecture lost to a baseline call
are examined in detail.

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

- **Translator** (`orchestrator.py`) converts the prompt into a JSON contract:
  topic, limitations, baseline, and the variables to measure. It is instructed
  to use only a baseline the user actually provided and never to invent
  measurements.
- **Einstein** (`einstein.py`) makes a single planning response that proposes
  web and paper searches. `globalFuncs.py` executes them locally through DDGS
  (web) and OpenAlex (papers), then fetches content for the most promising
  results.
- **Researcher / Experimenter / Evaluator** (`compressor.py`) filter the
  promising evidence, ask JEV for a hypothesis count, generate candidate Python
  code, execute it, and evaluate the measured output.
- **Compressor** ranks the hypotheses that survived evaluation.
- **Tracker** (`tracker.py`) optionally records submitted problems and results.
  Without Supabase credentials it falls back to a local SQLite file.

Everything is sequential. There is no parallel agent execution and no
cross-agent retry loop.

## Layout

```
F001MM/
├── interface.py                     # click shell — the agent CLI
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

## Requirements

- Python 3.13
- [ttyd](https://github.com/tsl0922/ttyd) on `PATH`, only if you want the
  browser terminal (you can point `FALEN_TTYD_BIN` at the binary instead)

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
| `FALEN_CODE_DIR` | no | Directory where hypothesis code is written; the broker sets it per session |
| `FALEN_SESSION_ID` | no | Session id attached to tracker records |
| `FALEN_TTYD_BIN` | no | Path to `ttyd` when it is not on `PATH` |
| `PORT` | no | Broker port, default `7681` |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | no | Remote ops logging; without them the tracker uses SQLite |
| `FALEN_TRACKER_DB` | no | Local tracker SQLite path |

The loop spends real tokens on OpenRouter on every run. A single problem can
trigger several model calls plus web and paper fetches.

## How to test it

### Terminal only

```bash
python interface.py
```

Inside the shell:

- `run` — ask for a problem and start the full loop.
- `kernelExample` — run a fixed matrix-multiplication problem.
- `about` / `manual` / `introduce` / `exit`.

Good first checks:

1. `about` renders the architecture without calling any API.
2. `kernelExample` with a trivial NumPy problem exercises the full pipeline.
3. Inspect `src/agents/enterprise/temporaryCode/` while it runs; generated
   hypotheses are written there and deleted at the end.
4. Change `FALEN_CODE_DIR` to keep the generated code for inspection.

### Browser terminal with ttyd

```bash
bash start.sh
# or, on Windows without a POSIX shell:
python sessionBroker.py
```

The broker listens on `PORT` (default `7681`). Open `http://localhost:7681/`:
each visitor is redirected to `/s/<sessionId>/`, where a dedicated `ttyd`
process runs `interface.py` with its own code directory under `sessions/`.

## Notes and limitations

- Generated Python code is executed locally **without isolation**. Do not run
  this on a machine you do not trust the model with.
- `sessions/` and `temporaryCode/` are scratch space: generated `.py` files are
  deleted when a run finishes.
- The loop is sequential and has no per-agent retries beyond simple HTTP
  retries.
- The evaluation step measures what the generated code reports; it does not
  prove that the measurement is meaningful.
- There is no academic path and no HTTP API in this repository.

## Paper

A paper analyzing this architecture — cost, failure modes, and the comparison
against a conventional single call — will be added to this repository.

## License

Not decided yet.
