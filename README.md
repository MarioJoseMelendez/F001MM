# F001MM — Scientific Agent (first attempt)

An experimental multi-agent loop that turns a natural-language problem into a
measured experiment: it reads the problem, researches the literature, proposes
hypotheses in code, runs them, and explains the result.

This repository is a **snapshot of the agent core** extracted from the Falen
project. It is published as a first working attempt, not as a library. The
behavior is intentionally simple, the loop is sequential, and several sections
are still prototypes. A paper describing the approach and its evaluations is
planned.

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
├── main.py                          # CLI entry point
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

The files keep the original flat imports, so `main.py` adds the agent
directories to `sys.path` before importing the loop.

## Setup

Requires Python 3.13.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in the keys
```

## Run

```bash
python main.py "Improve the performance of the current matrix multiplication implementation."
```

Or without arguments to be prompted:

```bash
python main.py
```

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | All LLM calls |
| `JEV_API_KEY` | yes | Hypothesis-count decision (TypeSafe JEV) |
| `FALEN_CODE_DIR` | no | Where hypothesis code is written; defaults to `temporaryCode/` |
| `FALEN_SESSION_ID` | no | Session id attached to tracker records |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | no | Remote ops logging |
| `FALEN_TRACKER_DB` | no | Local tracker SQLite path |

The loop deletes generated `.py` files from `FALEN_CODE_DIR` (or
`temporaryCode/`) when it finishes, so that directory should be treated as
scratch space, not as storage.

## Status and limitations

- Single sequential loop; no retries across agents.
- One research response per run, with a fixed cap on searches.
- Generated code is executed locally without isolation.
- The `temporaryCode/` files are leftover examples from earlier runs.

## License

Not decided yet.
