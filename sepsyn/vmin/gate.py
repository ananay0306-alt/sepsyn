"""The azeotrope gate that runs before selection.

Underwood is evaluated at the bubble point, where an azeotrope is invisible:
ethanol/water reads alpha 1.9 there. Left alone, the dynamic program returns a
confident minimum vapour for a train that cannot be built.

A sharp-split train separates every pair of components in some column, so ONE
azeotropic pair blocks every sequence. That is why this checks all pairs,
which is deliberately broader than R-03: R-03 asks whether one column can make
its split, this asks whether any train of ordinary columns can exist at all.

Checked at the selection pressure. Azeotropes move with pressure, which is
exactly what pressure-swing distillation exploits, so the refusal names the
pressure rather than claiming the mixture is inseparable.
"""
from sepsyn.azeotropes import Azeotrope, find_azeotropes

ALTERNATIVES = (
    "pressure-swing distillation, if the azeotrope moves enough with pressure",
    "extractive or azeotropic distillation with an entrainer",
    "a non-distillation step for that pair (membrane, adsorption, extraction)",
)


class AzeotropeBlocksSelection(ValueError):
    """Some pair in the train is azeotropic at the selection pressure."""

    def __init__(self, azeotropes: list[Azeotrope], P_Pa: float):
        self.azeotropes = azeotropes
        self.P_Pa = P_Pa
        pairs = "; ".join(a.describe() for a in azeotropes)
        super().__init__(
            f"azeotrope: {pairs}. Every sharp-split "
            f"train has to separate that pair, so no sequence of ordinary "
            f"columns exists and no minimum vapour is reported")


def azeotrope_gate(feed, P_Pa: float) -> list[Azeotrope]:
    """Every azeotropic pair among the components that are actually present."""
    present = [c.name for c in feed.components if c.flow_kmol_hr > 0]
    return find_azeotropes(present, P_Pa)


def format_refusal(exc: AzeotropeBlocksSelection) -> str:
    lines = ["THIS SEPARATION CANNOT BE PERFORMED AS SPECIFIED", ""]
    for a in exc.azeotropes:
        lines.append(f"  AZEOTROPE  {a.describe()}")
    lines += [
        "",
        "  A train of sharp splits separates every pair somewhere, so one",
        "  azeotropic pair blocks every sequence. No minimum vapour is",
        "  reported: Underwood is evaluated at the bubble point, where the",
        "  azeotrope does not show, and its number would be confident",
        "  nonsense.",
        "",
        "  What would work instead:",
    ]
    lines += [f"    - {alt}" for alt in ALTERNATIVES]
    return "\n".join(lines)
