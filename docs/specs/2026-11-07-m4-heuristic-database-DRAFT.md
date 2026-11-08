# M4, heuristic database and retrieval: DRAFT scope, not approved

**Date:** 2026-11-07
**Status:** DRAFT. Written so the next session starts from decisions, not a
blank page. Nothing here is built, and no heuristic content was written,
because the content is being drafted separately and inventing it would be
exactly the unaudited guidance this project exists to prevent.

## What STATUS.md already fixes

"Store separation heuristics as conditional guidance that triggers a
calculation, never as answers." The rule schema already carries `requires`
and `limitations` (the EXTRA milestone), and `rules.yaml` plus
`equipment_rules.yaml` already hold the binary heuristics as rules.

## What M4 would add on top of that

Rules today answer one question: given this record, does the rule fire. M4 is
the other direction: given a question ("can I separate X from Y", "which
column first"), which heuristics apply, and which calculation does each one
send you to. A heuristic entry would carry:

| field | example |
|---|---|
| id, statement, source | "Remove the most plentiful component first", Seider ch. 9 |
| applies_when | an expression over the same restricted namespace the rules use |
| triggers | the sepsyn calculation that tests it: `--vmin`, `--sequence`, a rule id |
| conflicts_with | other heuristic ids, and what the measurement said when they conflicted |
| measured | links to findings, e.g. the M6 scorecard where all four sequencing heuristics landed within 1.6 % |

## Decisions that are yours

1. **Where the content comes from.** The separately drafted list, the
   `Binary_Distillation_Heuristics.pdf` steps, a textbook chapter, or a mix.
   Each entry needs a citation; which sources count?
2. **Scope.** Distillation only, or also the non-distillation candidates the
   screening already names (decanter, extractive, pressure swing, adsorption)?
3. **Retrieval.** Plain filtering on `applies_when` is enough for tens of
   entries. Anything fancier (embeddings, an LLM picking entries) would put
   judgement inside the core, which M5 deliberately kept out.
4. **Does a heuristic ever change a verdict?** The current design says no:
   heuristics point at calculations, the calculations decide.

## Suggested first slice once 1 and 2 are answered

The four sequencing heuristics already exist in `sequencing/heuristics.py` and
are already scored against the minimum-vapour optimum. Moving them into the
database format first proves the schema on content that is already measured.
