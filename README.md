# 🌳 Daily Reflection Tree

> A deterministic end-of-day reflection agent built for the DeepThought Fellowship Assignment.  
> No LLM at runtime. Pure decision-tree logic. Same answers → same path → every time.

---

## What This Is

An end-of-day reflection tool that walks an employee through a structured conversation using a hand-engineered decision tree. The user picks from fixed options at each step; the tree branches based on their answers and produces a personalised reflection summary — with zero AI involvement at runtime.

The tree covers three psychological axes in sequence:

| Axis | Spectrum | Grounding |
|------|----------|-----------|
| **1 — Locus** | Victim ↔ Victor | Rotter's Locus of Control (1954), Dweck's Growth Mindset (2006) |
| **2 — Orientation** | Entitlement ↔ Contribution | Organ's OCB (1988), Campbell et al. Psychological Entitlement (2004) |
| **3 — Radius** | Self-Centrism ↔ Altrocentrism | Maslow's Self-Transcendence (1969), Batson's Perspective-Taking (2011) |

---

## Repository Structure

```
├── Decision_tree.png          # Visual diagram of the full branching tree
├── decision_tree.json         # Part A — the tree as structured data (readable without running code)
├── agent.py                   # Part B — CLI agent that walks the tree deterministically
├── requirements.txt           # No third-party dependencies (Python stdlib only)
├── persona1.md                # Sample transcript: Victim · Fixed · Self-oriented path
├── persona2.md                # Sample transcript: Victor · Growth · Team-oriented path
└── README.md                  # This file
```

---

## Part A — The Decision Tree

The tree is defined entirely in `decision_tree.json`. Every possible conversation path can be traced by reading the file — no code execution required.

### Node Types

| Type | Purpose | User Interaction |
|------|---------|-----------------|
| `start` | Opens the session | Auto-advances |
| `question` | Fixed-option question | User picks 1 of 3–4 options |
| `decision` | Internal routing based on signal tallies | Invisible — auto-advances |
| `reflection` | Insight or reframe based on path taken | User reads, presses Enter |
| `bridge` | Transition statement between axes | Auto-advances |
| `summary` | End-of-session synthesis | User reads their profile |
| `end` | Closes the session | Auto-advances |

### How Branching Works

Each question node carries a `signal` array — one entry per option — that increments a named counter when that option is chosen:

```json
"signal": [
  "axis1:internal+2",
  "axis1:external+1",
  "axis1:external+2",
  "axis1:internal+1"
]
```

Decision nodes evaluate accumulated signal tallies against a logic rule:

```json
"logic": "if axis1_internal >= axis1_external then A1_Q2 else A1_REF1"
```

No scoring model. No sentiment analysis. Just integer tallies and lookups.

### Tree Stats

| Metric | Count |
|--------|-------|
| Total nodes | 30 |
| Question nodes | 9 |
| Decision nodes | 4 |
| Reflection nodes | 8 |
| Bridge nodes | 2 |
| Summary + End | 2 |
| Options per question | 4 |
| Axes covered | 3 (+ extended Axis 4) |

---

## Part B — The Agent

### Requirements

- Python **3.10+**
- No third-party packages — standard library only

### Running the Agent

```bash
# Clone the repo
git clone <your-repo-url>
cd <repo-folder>

# Run
python agent.py decision_tree.json
```

The agent will:
1. Load and parse the tree from the JSON file
2. Walk you through each node interactively in the terminal
3. Branch deterministically based on your selections
4. Interpolate your earlier answers into reflection text (e.g. `{A1_Q1.answer}`)
5. Display a signal-tally summary at the end
6. Auto-save a timestamped transcript as `transcript_YYYYMMDD_HHMMSS.md`

### Key Design Decisions

**Determinism guarantee:** Given identical option selections, the agent always produces the identical conversation path and summary. There is no randomness, no LLM call, no network request of any kind at runtime.

**Comment stripping:** The JSON tree uses `// comments` for readability. The agent strips these automatically before parsing, so the source file stays human-readable without breaking the loader.

**Graceful degradation:** ANSI colour output is automatically disabled on non-TTY environments (e.g. piped output, Windows CMD without ANSI support).

---

## Sample Transcripts

Two full session transcripts are included to demonstrate how the same tree produces different conversations for different personas.

### `persona1.md` — Victim · Fixed Mindset · Task-Focused · Self-Oriented

Chooses externally-attributed options throughout. All four decision nodes route to corrective reflection branches. The session surfaces blind spots on every axis without shaming the user.

```
axis1:external  → 4   |   axis1:internal → 0
axis2:fixed     → 4   |   axis2:growth   → 0
axis3:ocb_low   → 4   |   axis3:ocb_high → 0
axis4:low       → 4   |   axis4:high     → 0
```

> *"You show externally oriented control, a fixed mindset, task-focused contribution behavior, and a self-oriented perspective toward impact."*

---

### `persona2.md` — Victor · Growth Mindset · Proactive · Team-Oriented

Chooses internally-attributed options throughout. All four decision nodes skip corrective reflections and route directly to the next question. The session affirms and reinforces positive patterns.

```
axis1:internal  → 4   |   axis1:external → 0
axis2:growth    → 4   |   axis2:fixed    → 0
axis3:ocb_high  → 4   |   axis3:ocb_low  → 0
axis4:high      → 4   |   axis4:low      → 0
```

> *"You show internally driven control, a growth mindset, proactive contribution behavior, and a team-oriented perspective toward impact."*

---

## Design Philosophy

### Why no LLM at runtime?

Reflection tools must be **predictable, auditable, and trustworthy**. An LLM can hallucinate encouragement, vary responses across sessions, or give inconsistent advice. A well-designed tree gives the same quality every time — because a human encoded the intelligence into the structure itself.

> *The tree is the product. The LLM is the power tool used to build it.*

### Why fixed options only?

Free-text input requires AI classification to interpret — which reintroduces LLM dependency. Fixed options force the designer to do the hard work upfront: defining options that genuinely span the spectrum of human experience, honestly and without leading the user.

### Why these three axes, in this order?

The axes build on each other intentionally:

- Recognising **agency** (Axis 1) is a prerequisite for asking what you did with it.
- Seeing your own **contribution vs entitlement** (Axis 2) becomes possible once you accept agency.
- Widening your **radius of concern** to others (Axis 3) is the natural endpoint — self-transcendence as Maslow framed it.

A user who answers honestly will move through a genuine arc of self-discovery across the three axes, not three independent questionnaires.

---

## Anti-Hallucination Guardrails

Since LLMs were used during *design* (question drafting, persona testing, critique), the following guardrails were applied to prevent hallucinated output from entering the final product:

1. **All reflection text is static strings** — no generated content at runtime.
2. **Interpolation is purely mechanical** — `{placeholder}` replaced by stored answer strings, not model-generated summaries.
3. **Signal tallies are integers** — no probabilistic scoring, no model inference.
4. **Every branching rule is human-readable** — the `logic` field is an explicit `if/then/else` that any developer can audit without running code.
5. **Psychological framing was verified against primary sources** — Rotter (1954), Dweck (2006), Organ (1988), Campbell et al. (2004), Maslow (1969), Batson (2011).

---

## References

| Framework | Author | Year |
|-----------|--------|------|
| Locus of Control | Julian B. Rotter | 1954 |
| Mindset: The New Psychology of Success | Carol S. Dweck | 2006 |
| Organizational Citizenship Behavior | Dennis W. Organ | 1988 |
| Psychological Entitlement | Campbell, Bonacci, Shelton et al. | 2004 |
| Self-Transcendence (Z-Theory) | Abraham Maslow | 1969 |
| Empathy and Altruism | C. Daniel Batson | 2011 |

---

*Built as part of the DeepThought Fellowship Assignment — Role Simulation Track.*  
*AI tools (Claude, ChatGPT) were used during design and iteration. The final product contains zero LLM calls.*
