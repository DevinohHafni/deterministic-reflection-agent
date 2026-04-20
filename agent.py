#!/usr/bin/env python3
"""
Daily Reflection Tree Agent
Walks the reflection-tree.json deterministically.
No LLM calls at runtime — pure tree traversal.
"""

import json
import sys
import os
import re
import time
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# ANSI colours (gracefully disabled on Windows)
# ─────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty() and os.name != "nt"

def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def cyan(t):    return c(t, "96")
def yellow(t):  return c(t, "93")
def green(t):   return c(t, "92")
def dim(t):     return c(t, "2")
def bold(t):    return c(t, "1")
def magenta(t): return c(t, "95")
def red(t):     return c(t, "91")


# ─────────────────────────────────────────────
# Tree loader
# ─────────────────────────────────────────────

def load_tree(path: str) -> dict:
    """Load JSON tree, strip JS-style // comments, return id→node dict."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip single-line comments so the file is valid JSON
    cleaned = re.sub(r"//[^\n]*", "", raw)

    nodes_list = json.loads(cleaned)
    tree = {node["id"]: node for node in nodes_list}
    return tree


# ─────────────────────────────────────────────
# State helpers
# ─────────────────────────────────────────────

def make_state() -> dict:
    return {
        "answers":  {},          # node_id -> chosen option string
        "signals":  defaultdict(int),  # e.g. "axis1:internal" -> 3
        "path":     [],          # ordered list of visited node ids
    }


def apply_signals(node: dict, chosen_index: int, state: dict):
    """Parse and apply the signal for the chosen option index."""
    signals = node.get("signal", [])
    if not signals or chosen_index >= len(signals):
        return

    raw = signals[chosen_index]  # e.g. "axis1:internal+2"
    if not raw or raw.strip() == "":
        return

    # Parse  key:subkey+N  or  key:subkey
    m = re.match(r"([^+]+)(?:\+(\d+))?", raw.strip())
    if m:
        key   = m.group(1).strip()   # e.g. "axis1:internal"
        value = int(m.group(2)) if m.group(2) else 1
        state["signals"][key] += value


def axis_dominant(state: dict, axis: str, pole_a: str, pole_b: str) -> str:
    """Return whichever pole has the higher tally, defaulting to pole_a."""
    a = state["signals"].get(f"{axis}:{pole_a}", 0)
    b = state["signals"].get(f"{axis}:{pole_b}", 0)
    return pole_a if a >= b else pole_b


def resolve_style_label(state: dict) -> dict:
    """Map raw signal tallies to human-readable style labels for interpolation."""
    a1 = axis_dominant(state, "axis1", "internal", "external")
    a2 = axis_dominant(state, "axis2", "growth", "fixed")

    # axis3: three-level
    hi  = state["signals"].get("axis3:ocb_high", 0)
    mid = state["signals"].get("axis3:ocb_mid", 0)
    lo  = state["signals"].get("axis3:ocb_low", 0)
    if hi >= lo and hi >= mid:
        a3 = "proactive"
    elif mid > lo:
        a3 = "situational"
    else:
        a3 = "task-focused"

    # axis4
    a4_hi = state["signals"].get("axis4:high", 0)
    a4_lo = state["signals"].get("axis4:low", 0)
    if a4_hi > a4_lo:
        a4 = "team-oriented"
    elif a4_hi == a4_lo:
        a4 = "balanced"
    else:
        a4 = "self-oriented"

    return {
        "axis1_style": "internally driven" if a1 == "internal" else "externally oriented",
        "axis2_style": "growth"            if a2 == "growth"   else "fixed",
        "axis3_style": a3,
        "axis4_style": a4,
    }


def interpolate(text: str, state: dict) -> str:
    """Replace {node_id.answer} and {axis*_style} placeholders."""
    styles = resolve_style_label(state)

    # Replace axis style placeholders
    for key, val in styles.items():
        text = text.replace("{" + key + "}", val)

    # Replace {NODE_ID.answer} with what was selected at that node
    def replace_answer(m):
        node_id = m.group(1)
        return state["answers"].get(node_id, "…")

    text = re.sub(r"\{([A-Z0-9_]+)\.answer\}", replace_answer, text)
    return text


# ─────────────────────────────────────────────
# Decision routing
# ─────────────────────────────────────────────

def evaluate_decision(node: dict, state: dict, tree: dict) -> str:
    """
    Evaluate a decision node's logic string and return the next node id.

    Supported logic syntax (from the tree JSON):
      "if axis1_internal >= axis1_external then A1_Q2 else A1_REF1"
      "if axis2_growth >= axis2_fixed then A2_Q2 else A2_REF1"
      "if axis3_ocb_high >= axis3_ocb_low then A3_Q2 else A3_REF1"
      "if axis4_high >= axis4_low then A4_Q2 else A4_REF1"
    """
    logic = node.get("logic", "")
    m = re.match(
        r"if\s+(\S+)\s*(>=|>|<=|<|==)\s*(\S+)\s+then\s+(\S+)\s+else\s+(\S+)",
        logic.strip(),
        re.IGNORECASE,
    )
    if not m:
        # Fallback: follow 'next' or first child
        return node.get("next", _first_child(node["id"], tree))

    lhs_key, op, rhs_key, then_id, else_id = m.groups()

    def signal_val(k):
        # "axis1_internal" → "axis1:internal"
        return state["signals"].get(k.replace("_", ":", 1), 0)

    lhs = signal_val(lhs_key)
    rhs = signal_val(rhs_key)

    ops = {
        ">=": lhs >= rhs,
        ">":  lhs >  rhs,
        "<=": lhs <= rhs,
        "<":  lhs <  rhs,
        "==": lhs == rhs,
    }
    return then_id if ops[op] else else_id


def _first_child(parent_id: str, tree: dict) -> str | None:
    for node in tree.values():
        if node.get("parentId") == parent_id:
            return node["id"]
    return None


def next_node_id(node: dict, tree: dict, state: dict) -> str | None:
    """Resolve the next node to visit after the current one."""
    explicit = node.get("next")
    if explicit:
        return explicit
    return _first_child(node["id"], tree)


# ─────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────

DIVIDER = dim("─" * 60)

def print_divider():
    print(DIVIDER)

def slow_print(text: str, delay: float = 0.018):
    """Print text character-by-character for a typewriter effect."""
    if not sys.stdout.isatty():
        print(text)
        return
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

def ask_choice(options: list[str]) -> tuple[int, str]:
    """Prompt user to pick a numbered option. Returns (0-based index, text)."""
    for i, opt in enumerate(options, 1):
        print(f"  {bold(str(i))}.  {opt}")
    print()

    while True:
        raw = input(cyan("  Your choice (enter number): ")).strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx, options[idx]
        print(red("  Please enter a valid number."))


def press_enter(prompt: str = "  Press Enter to continue…"):
    input(dim(prompt))


# ─────────────────────────────────────────────
# Node renderers
# ─────────────────────────────────────────────

def render_start(node, state, tree):
    print()
    print_divider()
    slow_print(bold(cyan(f"  {node['text']}")))
    print_divider()
    time.sleep(0.5)
    return next_node_id(node, tree, state)


def render_question(node, state, tree):
    print()
    print_divider()
    slow_print(yellow(f"  {interpolate(node['text'], state)}"))
    print()
    idx, chosen = ask_choice(node["options"])
    state["answers"][node["id"]] = chosen
    apply_signals(node, idx, state)
    print(green(f"\n  ✓ You chose: "{chosen}"\n"))
    # question nodes always go to their explicit 'next'
    return node.get("next") or _first_child(node["id"], tree)


def render_decision(node, state, tree):
    # Invisible to user
    return evaluate_decision(node, state, tree)


def render_reflection(node, state, tree):
    print()
    print_divider()
    text = interpolate(node["text"], state)
    slow_print(magenta(f"  💭  {text}"))
    print()
    press_enter()
    return next_node_id(node, tree, state)


def render_bridge(node, state, tree):
    print()
    slow_print(dim(f"  ── {interpolate(node['text'], state)} ──"))
    time.sleep(0.4)
    return next_node_id(node, tree, state)


def render_summary(node, state, tree):
    print()
    print_divider()
    slow_print(bold(green("  📋  YOUR REFLECTION SUMMARY")))
    print_divider()
    text = interpolate(node["text"], state)
    slow_print(f"\n  {text}\n")

    # Print signal tallies
    print(dim("  Signal tallies:"))
    for key, val in sorted(state["signals"].items()):
        print(dim(f"    {key}: {val}"))

    print()
    press_enter("  Press Enter to close your session…")
    return next_node_id(node, tree, state)


def render_end(node, state, tree):
    print()
    print_divider()
    slow_print(bold(cyan(f"  {node['text']}")))
    print_divider()
    print()
    return None   # terminates the loop


# ─────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────

RENDERERS = {
    "start":      render_start,
    "question":   render_question,
    "decision":   render_decision,
    "reflection": render_reflection,
    "bridge":     render_bridge,
    "summary":    render_summary,
    "end":        render_end,
}


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────

def run(tree_path: str):
    tree  = load_tree(tree_path)
    state = make_state()

    print()
    print(bold(cyan("  ╔══════════════════════════════════════╗")))
    print(bold(cyan("  ║    Daily Reflection Tree Agent       ║")))
    print(bold(cyan(f"  ║    {datetime.now().strftime('%A, %d %b %Y  %H:%M')}"
                    + " " * (23 - len(datetime.now().strftime('%A, %d %b %Y  %H:%M'))) + "║")))
    print(bold(cyan("  ╚══════════════════════════════════════╝")))

    current_id = "START"

    while current_id is not None:
        node = tree.get(current_id)
        if node is None:
            print(red(f"\n  [ERROR] Node '{current_id}' not found in tree. Exiting."))
            break

        state["path"].append(current_id)
        node_type = node.get("type", "")
        renderer  = RENDERERS.get(node_type)

        if renderer is None:
            print(red(f"\n  [WARN] Unknown node type '{node_type}' at '{current_id}'. Skipping."))
            current_id = next_node_id(node, tree, state)
            continue

        current_id = renderer(node, state, tree)

    # Session complete — save transcript
    save_transcript(state, tree)


# ─────────────────────────────────────────────
# Transcript saver
# ─────────────────────────────────────────────

def save_transcript(state: dict, tree: dict):
    styles   = resolve_style_label(state)
    filename = f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    lines = [
        "# Reflection Session Transcript",
        f"**Date:** {datetime.now().strftime('%A, %d %b %Y %H:%M')}",
        "",
        "## Path Taken",
        "",
    ]

    for node_id in state["path"]:
        node = tree.get(node_id, {})
        ntype = node.get("type", "")
        if ntype == "question":
            lines.append(f"**Q [{node_id}]:** {node.get('text','')}")
            lines.append(f"→ *{state['answers'].get(node_id, '—')}*")
            lines.append("")
        elif ntype in ("reflection", "bridge", "summary"):
            lines.append(f"*[{ntype.upper()}]* {node.get('text','')}")
            lines.append("")

    lines += [
        "## Signal Summary",
        "",
    ]
    for key, val in sorted(state["signals"].items()):
        lines.append(f"- `{key}`: {val}")

    lines += [
        "",
        "## Style Profile",
        "",
    ]
    for k, v in styles.items():
        lines.append(f"- **{k}**: {v}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(dim(f"  Transcript saved → {filename}\n"))


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    tree_file = sys.argv[1] if len(sys.argv) > 1 else "reflection-tree.json"

    if not os.path.exists(tree_file):
        print(red(f"\n  Tree file not found: {tree_file}"))
        print(f"  Usage: python agent.py <path-to-tree.json>\n")
        sys.exit(1)

    try:
        run(tree_file)
    except KeyboardInterrupt:
        print("\n\n  Session interrupted. See you tomorrow.\n")
