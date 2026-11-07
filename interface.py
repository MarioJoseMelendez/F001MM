# ====================================================================
# ====================================================================
# {1} MAIN MODULE: FALEN CLI (SCIENTIFIC AGENT ENVIRONMENT)
# ====================================================================
# Flashy CLI shell around the real Falen loop. Collects a user prompt,
# calls Orchestrator, and prints the measured result. Phase loading
# lives in the agent files until those embedded blocks are removed.
# ====================================================================

import sys
import time
from pathlib import Path

import click
from click_shell import shell


# Run with the project venv (agent deps such as ddgs live there), from the repository root:
#   .venv\Scripts\python.exe interface.py

# {3} Configure stdout and stderr to UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_AGENTS_DIR = Path(__file__).resolve().parent / "src" / "agents"
_ENTERPRISE_DIR = _AGENTS_DIR / "enterprise"
for _pathDir in (_ENTERPRISE_DIR, _AGENTS_DIR):
    if str(_pathDir) not in sys.path:
        sys.path.insert(0, str(_pathDir))

try:
    from enterprise.orchestrator import Orchestrator
except ModuleNotFoundError as importError:
    _VENV_PYTHON = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    raise SystemExit(
        f"Missing dependency {importError.name!r} under {sys.executable}.\n"
        f"Use the project venv from the repository root:\n"
        f"  {_VENV_PYTHON} {Path(__file__).name}"
    ) from importError


# cli.md tokens — cream, dusty pink, muted. No neon.
CLI_TEXT = (243, 234, 223)
CLI_ACCENT = (228, 180, 196)
CLI_ACCENT_SOFT = (201, 138, 160)
CLI_MUTED = (154, 144, 136)

KERNEL_EXAMPLE_PROBLEM = (
    "Improve the performance of the current matrix multiplication "
    "implementation."
)

FALEN_BANNER_LINES = [
    r"    ███████╗ █████╗ ██╗     ███████╗███╗   ██╗",
    r"    ██╔════╝██╔══██╗██║     ██╔════╝████╗  ██║",
    r"    █████╗  ███████║██║     █████╗  ██╔██╗ ██║",
    r"    ██╔══╝  ██╔══██║██║     ██╔══╝  ██║╚██╗██║",
    r"    ██║     ██║  ██║███████╗███████╗██║ ╚████║",
    r"    ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝",
]


def CliText(message, **styleKwargs):
    return click.style(message, fg=CLI_TEXT, **styleKwargs)


def CliAccent(message, **styleKwargs):
    return click.style(message, fg=CLI_ACCENT, **styleKwargs)


def CliAccentSoft(message, **styleKwargs):
    return click.style(message, fg=CLI_ACCENT_SOFT, **styleKwargs)


def CliMuted(message, **styleKwargs):
    return click.style(message, fg=CLI_MUTED, **styleKwargs)


def PrintRule():
    click.echo(CliMuted("  ────────"))


def PrintFalenBanner():
    click.echo("")
    for bannerLine in FALEN_BANNER_LINES:
        click.echo(CliAccent(bannerLine, bold=True))
    click.echo("")


def PrintAnimatedBanner():
    # One dusty-pink ink, soft fade into full accent (not a neon rainbow).
    fadeSteps = [
        (80, 55, 65),
        (120, 80, 95),
        (160, 110, 130),
        (190, 140, 155),
        CLI_ACCENT_SOFT,
        CLI_ACCENT,
    ]

    click.echo("")
    for fadeColor in fadeSteps:
        click.echo("\033[F" * (len(FALEN_BANNER_LINES) + 1), nl=False)
        for bannerLine in FALEN_BANNER_LINES:
            click.echo(click.style(bannerLine, fg=fadeColor, bold=True))
        time.sleep(0.06)
    click.echo("")


def PrintSectionTitle(sectionTitle):
    click.echo("")
    PrintRule()
    click.echo(CliAccent(f"  {sectionTitle}", bold=True))
    click.echo("")


def PrintMetricRow(metricLabel, metricValue):
    click.echo(
        CliMuted(f"  {metricLabel:<16}", bold=True)
        + CliText(str(metricValue))
    )


def PrintLoadingScreen(agentName, detail):
    # One accent spinner character — no rainbow bar.
    frames = ["·", "o", "O", "o"]
    click.echo("")
    click.echo(CliAccent(f"  {agentName}", bold=True))
    click.echo(CliMuted(f"  {detail}"))
    for frameChar in frames:
        click.echo(
            "\r"
            + CliAccent(f"  {frameChar} loading...", bold=True),
            nl=False,
        )
        time.sleep(0.08)
    click.echo("")
    click.echo("")


def PrintIntroduce():
    click.clear()
    PrintAnimatedBanner()
    click.echo(CliMuted("  Find better solutions to difficult problems."))
    click.echo("")
    click.echo(CliAccent("  Human scientists", bold=True) + CliMuted("          AI research agents"))
    click.echo(CliText("  Vision and hypotheses") + CliMuted("     Autonomous execution"))
    click.echo(CliMuted("  Intuition, discovery") + CliText("      Blocked kernels, speedup"))
    click.echo("")
    PrintRule()
    click.echo(CliAccent("  Falen introduce", bold=True))
    click.echo(CliMuted("  Empowering human scientists."))
    click.echo("")


def RunFalenLoop(userPrompt=None):
    PrintAnimatedBanner()
    PrintSectionTitle("Scientific experiment")

    PrintMetricRow(
        "AGENTS",
        "Translator / Einstein / Researcher / Experimenter / Evaluator",
    )
    click.echo("")

    if userPrompt is None:
        userPrompt = click.prompt(
            CliAccent("What should Falen investigate?", bold=True)
        )

    click.echo("")
    PrintMetricRow("PROBLEM", userPrompt)
    click.echo("")
    PrintLoadingScreen("Orchestrator", "starting the scientific loop")

    Orchestrator(userPrompt)

    click.echo(CliAccentSoft("  Falen finished this research loop."))
    click.echo(
        CliMuted(
            "  Translator → Einstein → Researcher → Experimenter → Evaluator"
        )
    )
    click.echo("")


@shell(
    prompt=click.style("falen > ", fg=CLI_MUTED),
    intro=(
        "\n"
        + click.style("Falen", fg=CLI_ACCENT, bold=True)
        + "\n"
        "Type 'introduce' for the full visual, 'run' to investigate, or 'manual' for commands.\n"
    ),
)
def falenEnv():
    pass


@falenEnv.command()
def run():
    """Collect a user prompt and run the real Falen research loop."""
    RunFalenLoop()


@falenEnv.command(name="kernelExample")
def kernelExample():
    """Run the real agent loop on the fixed kernel problem."""
    RunFalenLoop(KERNEL_EXAMPLE_PROBLEM)


@falenEnv.command()
def introduce():
    """Show a full-screen visual representation of Falen."""
    PrintIntroduce()


@falenEnv.command()
def manual():
    """Show the command list."""
    click.echo("")
    PrintRule()
    click.echo(CliAccent("  Commands", bold=True))
    click.echo("")
    click.echo(CliMuted("  introduce      ", bold=True) + CliText("Full-screen visual."))
    click.echo(CliMuted("  run            ", bold=True) + CliText("Collect a problem and run the agent loop."))
    click.echo(CliMuted("  kernelExample  ", bold=True) + CliText("Same as run."))
    click.echo(CliMuted("  about          ", bold=True) + CliText("Show the Falen agent architecture."))
    click.echo(CliMuted("  manual         ", bold=True) + CliText("Show this command list."))
    click.echo(CliMuted("  exit           ", bold=True) + CliText("Leave the shell."))
    click.echo("")


@falenEnv.command()
def about():
    """Show the current Falen architecture."""
    PrintAnimatedBanner()
    PrintSectionTitle("Architecture")
    PrintMetricRow("Translator", "turns the user prompt into an experiment contract")
    PrintMetricRow("Einstein", "decides searches and gathers literature")
    PrintMetricRow("Researcher", "chooses a hypothesis count and writes hypotheses")
    PrintMetricRow("Experimenter", "implements each hypothesis")
    PrintMetricRow("Evaluator", "measures the result variables")
    PrintMetricRow("Compressor", "ranks the measured hypotheses")
    click.echo("")
    click.echo(CliMuted("  This build runs the real agents. It is not a simulation."))
    click.echo("")


if __name__ == "__main__":
    falenEnv()
