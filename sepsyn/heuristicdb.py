"""The heuristic database. M4.

Rules answer "given this record, does the rule fire". This is the other
direction: given a question, which textbook heuristics apply, where each comes
from, and which calculation tests it.

A heuristic never decides anything. Nothing in selection, verification or
screening imports this module; the report reads it to put a statement and a
citation beside a score the minimum-vapour optimum already produced. Plain
filtering on `applies_when` is the whole retrieval, deliberately: anything
cleverer would put judgement inside the core.
"""
import os
from dataclasses import dataclass
from functools import lru_cache

import yaml

from sepsyn.engine import _names_in, safe_eval

HEURISTICS_PATH = os.path.join(os.path.dirname(__file__), "heuristics.yaml")

# The only names an applies_when may use. Sequencing heuristics are about the
# shape of the feed, not about any one column's properties.
SEQUENCING_FIELDS = frozenset({"n_components"})

SCOPES = frozenset({"sequencing"})

# The calculations a heuristic may point at. Each is a sepsyn mode that
# produces the number the heuristic is scored against.
TESTED_BY = frozenset({"vmin"})


@dataclass(frozen=True)
class Heuristic:
    id: str
    statement: str
    source: str
    source_verified: bool
    scope: str
    applies_when: str
    proxy: str
    tested_by: str
    conflicts_with: tuple[str, ...]
    measured: tuple[str, ...]

    @property
    def citation(self) -> str:
        return self.source + ("" if self.source_verified else
                              " (citation unverified)")


def load_heuristics(path: str | None = None) -> tuple[Heuristic, ...]:
    """Load and validate. Like the rule loader, every defect is a load error:
    a heuristic that loads broken is guidance that silently stops appearing."""
    from sepsyn.sequencing.heuristics import PROXIES

    where = path or HEURISTICS_PATH
    with open(where) as fh:
        raw = yaml.safe_load(fh) or []
    out = []
    for h in raw:
        out.append(Heuristic(
            id=h["id"], statement=" ".join(h["statement"].split()),
            source=" ".join((h.get("source") or "").split()),
            source_verified=bool(h.get("source_verified", False)),
            scope=h["scope"], applies_when=h["applies_when"],
            proxy=h["proxy"], tested_by=h["tested_by"],
            conflicts_with=tuple(h.get("conflicts_with") or ()),
            measured=tuple(h.get("measured") or ()),
        ))

    ids = [h.id for h in out]
    for h in out:
        if ids.count(h.id) > 1:
            raise ValueError(f"duplicate heuristic id {h.id!r} in {where}")
        if not h.source:
            raise ValueError(
                f"heuristic {h.id} has no source. An uncited heuristic is the "
                f"unaudited guidance this database exists to keep out.")
        if h.scope not in SCOPES:
            raise ValueError(f"heuristic {h.id} has scope {h.scope!r}; must "
                             f"be one of {sorted(SCOPES)}")
        if h.tested_by not in TESTED_BY:
            raise ValueError(
                f"heuristic {h.id} is tested by {h.tested_by!r}, which is not "
                f"a sepsyn calculation; must be one of {sorted(TESTED_BY)}")
        if h.proxy not in PROXIES:
            raise ValueError(
                f"heuristic {h.id} names proxy {h.proxy!r}, which does not "
                f"exist; known: {sorted(PROXIES)}")
        try:
            names = _names_in(h.applies_when)
        except SyntaxError as exc:
            raise ValueError(f"heuristic {h.id} has an unparseable "
                             f"applies_when {h.applies_when!r}: {exc}") from exc
        for name in names:
            if name not in SEQUENCING_FIELDS:
                raise ValueError(
                    f"heuristic {h.id} references {name!r}; applies_when may "
                    f"use only {sorted(SEQUENCING_FIELDS)}")
        for other in h.conflicts_with:
            if other not in ids:
                raise ValueError(f"heuristic {h.id} conflicts with unknown "
                                 f"heuristic {other!r}")

    proxies = [h.proxy for h in out]
    for p in proxies:
        if proxies.count(p) > 1:
            raise ValueError(f"proxy {p!r} is claimed by two heuristics; a "
                             f"score could then carry either citation")
    return tuple(out)


@lru_cache(maxsize=1)
def default_heuristics() -> tuple[Heuristic, ...]:
    return load_heuristics()


def applicable(heuristics, n_components: int) -> tuple[Heuristic, ...]:
    """The heuristics whose applies_when holds for this feed."""
    ns = {"n_components": n_components}
    return tuple(h for h in heuristics if safe_eval(h.applies_when, ns))


def by_proxy(heuristics) -> dict[str, Heuristic]:
    return {h.proxy: h for h in heuristics}
