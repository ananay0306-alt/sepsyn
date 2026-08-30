# sepsyn — status

Updated 2026-08-30. Check this file; it is the tracker.
`cat STATUS.md` beats scrolling a chat log.

## Where we are

| | |
|---|---|
| Milestones done | **1 of 6** (M1 is the foundation the other five sit on) |
| Tests | **125 passing**, 11 s |
| Blocking right now | **iCloud has evicted the project.** See "Environment" below. It outranks everything. |
| Waiting on you | **3 decisions** (below). M2 does not move until these are made. |

## Environment problem, fix this first

`~/Desktop` is iCloud synced and iCloud is **out of quota**. Files are evicted
to stubs and must re-download on access, so the machine crawls.

| | evicted |
|---|---|
| `.venv` | 19,294 of 28,295 files |
| `dwsim-mcp` | 48 of 71 files |
| `sepsyn` | 224 of 407 files |

`brctl status` reports "Error uploading asset: Quota exceeded" 1,320 times.

Symptoms seen: `import thermosteam` hung over 7 minutes with no output; the
test suite went from 11 s to a 10 minute timeout. Nothing is corrupted or
deleted, dataless files re-download intact.

**Fix: move the project off `~/Desktop`.** Freeing iCloud space only helps
until it fills again. After moving, recreate `.venv` (its scripts hardcode
absolute paths) and re-register the MCP server with
`claude mcp add --scope user dwsim <new-path>/dwsim-mcp.sh`. Git is unaffected.

**This contaminates Risk 5.** The seven DWSIM configurations that failed on
2026-08-27 ran against a server 68 % evicted. Run 6 failed with a real
numerical message (mass balance 2.57e-4 against a 1e-4 tolerance) and that
result stands, but runs 3, 4, 5 and 7 failed on *timeout*, which is exactly what
a starved filesystem produces. **Re-test Risk 5 on a healthy machine before
planning around it.**

## Decisions waiting on you

- [ ] **1. Merge `m2-risk2-shortcut-config` into `main`?**
      5 commits, all documentation, each stands alone. *Recommend: yes.*
- [ ] **2. Switch the M2 bring-up case to benzene/toluene?**
      Methanol/water/glycerol was chosen when both sides were shortcut methods
      and will not solve rigorously. Benzene/toluene solved rigorously in
      seconds. *Recommend: yes*, keep methanol/water as a later stress case.
- [ ] **3. M2 transport — live subprocess, recorded fixtures, or both?**
      Solve times of minutes make a live adapter impractical in the suite.
      *Recommend: both* — fixtures for a hermetic suite, live behind an opt-in
      marker, since fixtures alone prove nothing about the protocol.

## The road

### [x] M1 — screen, design, verify · COMPLETE, MERGED
Feed in, nine screening rules, column design, verification out. One simulator,
binary keys, no flowsheet.
- [x] All 12 tasks
- [x] Five success criteria checked by hand, not inferred from the suite
- [x] Re-verified live 08-27: H2/methane INFEASIBLE citing R-04;
      methanol/water/glycerol designs a column, all five checks pass

### [x] EXTRA — rule schema extension · COMPLETE, MERGED
Unplanned, built 08-27. Rules can now declare the calculation they still need
instead of only a verdict.
- [x] `requires` + `limitations`, both defaulting empty — additive
- [x] Fourth verdict `undetermined`, distinct from `unknown`; rejected at load
      if it names no calculation
- [x] R-09 stops asserting refrigeration before the pressure search that could
      refute it has run
- Done now because it makes M4 a default-valued field instead of a migration

### [ ] M2 — rigorous cross-validation · BLOCKED, NOT PLANNED
How far is sepsyn's shortcut design from a rigorous answer? DWSIM's rigorous
column is the REFERENCE, not a peer, so the gap measures shortcut error.
- [x] Scope A ruled
- [x] Risk 2 resolved — `ShortcutColumn` spec inputs are public *fields*
- [x] Found: the old acceptance criterion could not fail — recoveries impose
      the products, leaving one free number
- [ ] **Risk 5 BLOCKING, and now in doubt** — rigorous reference did not solve
      the acceptance case in seven configurations, but four failed on timeout
      while the filesystem was starved. Re-test before trusting it
- [ ] Risk 1 OPEN — the adapter's transport, and the real work
- [ ] Not planned into tasks

Every gap found on 08-27, and what it turned out to be:

| apparent gap | true cause | corrected |
|---|---|---|
| stages, 43 % | actual vs theoretical stage basis | 16.9 % |
| stages, 16.9 % | absolute reflux vs matched R/Rmin | 6.5 % |
| condenser duty, 58 % | partial vs total condenser | 6.3 % |
| Rmin, 24 % (binary) | **unexplained** | — |

The lesson: every large disagreement but one was a configuration or definition
mismatch, not physics. **The harness must assert configuration equivalence, not
just compare numbers.**

### [~] Workflow steps from the binary heuristics list · ITEM 1 DONE
The 41 step design sequence, being folded into the rule table. sepsyn already
covered about 20 of the 41.
- [x] **Item 1** — reboiler side pressure rule (R-10) and thermal limit (R-11);
      record gains `bottoms_T_at_column_P` and `steam_T`; `safe_eval` now
      permits arithmetic so thresholds can be expressed against another
      property in the rule file. 34 engine tests pass
- [ ] **Item 2** — verification checks 39, 40, 41 (duty, end temperatures,
      energy balance). BLOCKED: needs duty fields on `ColumnResult` and a
      working BioSTEAM, so it waits on the environment fix
- [ ] Item 3 — feed condition q, steps 15 to 17
- [ ] Item 4 — equipment choices as rules, steps 22 to 25
- [ ] Item 5 — a thin skill as the conversational front door

### [ ] M3 — sequencing multicomponent trains · NOT STARTED, NO SPEC
Today the tool stops at one column and says so. The "NOT SPECIFIED … separate
products need a second column" note is this milestone announcing itself.

### [ ] M4 — heuristic database & retrieval · NOT STARTED, NO SPEC
Store separation heuristics as conditional guidance that triggers a
calculation, never as answers.
- [x] Schema ready ahead of it (see EXTRA)
- [ ] Content being drafted separately
- [ ] Needs its own spec

### [ ] M5 — LLM interface · NOT STARTED, NO SPEC
Wrap the library as an agent or MCP server. The core deliberately has no LLM in
it, so this is a wrapper, not a rewrite.

### [ ] M-B — simulation-direction comparison · DEFERRED BY CHOICE
Specify the column, compare predicted purities. Nothing imposed either side.
- [x] Confirmed available: BioSTEAM `MESHDistillation` takes the same inputs as
      DWSIM's rigorous column
- [ ] Deferred — better test, roughly twice the milestone, so it gets its own

## Where things live

| | |
|---|---|
| `main` | `92d6ed5` — M1 plus the rule schema extension |
| `m2-risk2-shortcut-config` | 5 commits, unmerged — revised M2 spec and every finding |
| Specs | 08-22 M2 spec marked superseded, kept as evidence log; plan from the 08-27 revision |
| Probe flowsheet | `../sepsyn_m2_shortcut_probe.dwxmz`, opens in the DWSIM GUI |
