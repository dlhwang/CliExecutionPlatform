"""Bounded OpenSCAD runtime diagnostics for LLM refinement feedback."""

from runner.exceptions import CLIExecutionError

MAX_DIAGNOSTIC_CHARS = 1500

_RULES = (
    (
        "Current top level object is empty.",
        "SCAD_EMPTY_TOP_LEVEL",
        "OpenSCAD produced no top-level geometry.",
    ),
    (
        "Ignoring 3D child object for 2D operation",
        "SCAD_2D_3D_MIXED_OPERATION",
        "A 3D child was passed to a 2D operation.",
    ),
)


def build_runtime_feedback(error: CLIExecutionError) -> str:
    """Build feedback exclusively from the exception's already-bounded tails."""
    tails = (("stderr", error.stderr), ("stdout", error.stdout))
    lines = [f"OpenSCAD execution failed with exit code {error.exit_code}."]
    matches: list[str] = []

    for needle, rule_id, description in _RULES:
        for stream_name, tail in tails:
            match = next((line for line in tail.splitlines() if needle in line), None)
            if match is not None:
                matches.append(f"- [{rule_id}] {description}\n  {stream_name}: {match[:300]}")
                break

    if matches:
        lines.extend(matches)
    else:
        for stream_name, tail in tails:
            if tail:
                lines.append(f"- {stream_name} bounded tail:\n{tail}")

    feedback = "\n".join(lines)
    if len(feedback) > MAX_DIAGNOSTIC_CHARS:
        feedback = feedback[: MAX_DIAGNOSTIC_CHARS - 36].rstrip() + "\n... [additional output omitted]"
    return feedback
