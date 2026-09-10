# The sequencing layer ranks columns its own screening declined to endorse

**Date:** 2026-09-10
**Status:** confirmed defect, fix identified, not yet fixed
**Severity:** this invalidates the M3 numbers, not merely their precision

## What happened

An attempt to re-rank M3's adversarial feed with rigorous DWSIM refluxes could
not be completed: 8 of the 15 columns in the 5 sequences failed to converge.
The failures were not a harness bug. The columns are not buildable as specified.

Per-column screening on the direct sequence:

| column | keys | pressure | sepsyn's own screening verdict |
|---|---|---|---|
| 0 | Propane/Butane | 13.69 bar | FEASIBLE |
| 1 | Butane/Pentane | 3.78 bar | **UNDETERMINED** |
| 2 | Pentane/Hexane | 1.16 bar | **UNDETERMINED** |

`sequence feasible: True`, `total cost reported: $513,461/yr`.

**Two of three columns were flagged, and the sequence was designed, costed and
ranked as though nothing had been said.**

## The mechanism

Sharp splits are imperfect, so traces propagate: every column in every sequence
receives all four components, including ones far lighter than its keys. That
propagation is correct and was added deliberately in M3.

A downstream column's pressure is then resolved for the lightest member of its
NOMINAL group. The Pentane/Hexane column gets 1.16 bar, the pressure at which
pentane condenses against cooling water. But its feed still carries propane and
butane:

| component | condensing T at 1.16 bar | condenses against 313.1 K water? |
|---|---|---|
| Propane | 234.1 K | **no** |
| Butane | 276.3 K | **no** |
| Pentane | 313.2 K | yes |
| Hexane | 346.2 K | yes |

R-09 fires correctly and returns `undetermined`: refrigeration may be required.
A rigorous MESH solve then cannot converge a total condenser that must condense
propane at 234 K against cooling water. BioSTEAM's Fenske-Underwood-Gilliland
has no such check and designs the column regardless.

## The defect, precisely

`evaluate_sequence` eliminates a sequence only when a column screens
`infeasible`. `undetermined` is recorded on the `ColumnOutcome` and then
ignored.

That is exactly the failure this project exists to prevent, committed by this
project: a rule fired, said it could not confirm the result, and the layer above
printed a confident number anyway. The rule schema was extended specifically so
a rule could say "I do not know"; the sequencing code does not listen.

## A second, smaller defect

Equipment rule E-22a chooses a partial condenser when
`n_supercritical_at_feed > 0`. Propane is not supercritical at 330 K, so E-22a
never fires here, even though the physical situation it exists for is present.
The rule asks "is anything supercritical at FEED conditions" when the question
is "will anything in THIS column's overhead fail to condense at THIS column's
pressure". R-09 already asks the right question; E-22a does not.

## Consequences for M3

The reported numbers rest on columns sepsyn itself declined to endorse. This is
worse than the earlier finding about Underwood's minimum reflux, which made the
absolute costs untrustworthy: here the sequences contain columns that should
never have been designed.

- `$513,461/yr` for the winning sequence: withdrawn.
- The sequence ranking: withdrawn, since every sequence contains at least one
  undetermined column and the count differs between them.
- The Phase B scorecard, `easiest_first` beating `most_plentiful_first` by
  5.1 %: withdrawn, since it is computed from that ranking.

The machinery is not withdrawn. Enumeration, propagation, per-column screening
and the scoring method are all sound, and the per-column screening is what
caught this. Only the numbers are affected.

## The fix

`evaluate_sequence` must treat `undetermined` as blocking a cost, in the same
way M2's `can_report_gap` treats an uncheckable assertion as blocking a gap. A
`SequenceOutcome` containing an undetermined column should report its cost as
`None` with the rule cited, not a number.

Whether such a sequence is eliminated or merely uncosted is a design decision.
Uncosted and reported is probably right: the sequence may be perfectly good once
someone confirms a partial condenser or a light-ends vent, and eliminating it
would hide a viable route.

E-22a should key on the condensing temperature at the column's own pressure
rather than on supercriticality at feed.

## What this vindicates

M2's premise. The cross-validation was built to measure shortcut error and
instead found that the tool was designing unbuildable columns. Neither the
shortcut method nor the cost model would ever have revealed it; only trying to
solve the same column rigorously did.
