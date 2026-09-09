"""Component attributes that no property database carries.

CRC, DIPPR and IUPAC give boiling points and critical constants. None of them
says whether a component is corrosive. Structure does not settle it either:
corrosivity depends on concentration, temperature and the material of
construction, so a functional-group rule would be confidently wrong often
enough to matter.

So these are supplied by the user or they are absent, and absent means the tool
does not know rather than that the component is benign.
"""

KNOWN_TAGS = frozenset({
    "corrosive",
    "hazardous",
    "fouling",
    "thermally_sensitive",
})


class UnknownTag(ValueError):
    """A tag or component that would silently never match anything."""


def parse_tags(specs: list[str],
               names: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """Parse 'HCl:corrosive' or 'HCl:corrosive,hazardous' into a tag map.

    Both an unknown tag and an unknown component are rejected rather than
    ignored. A typo that parses is a tag that never matches a rule, and a rule
    that silently never fires is the failure this project exists to catch.
    """
    tags: dict[str, set[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise UnknownTag(
                f"expected Component:tag, got {spec!r}. Tags available: "
                f"{', '.join(sorted(KNOWN_TAGS))}"
            )
        name, raw = spec.split(":", 1)
        name = name.strip()
        if name not in names:
            raise UnknownTag(
                f"cannot tag {name!r}: it is not in the feed. Feed contains: "
                f"{', '.join(names)}"
            )
        for tag in (t.strip() for t in raw.split(",")):
            if tag not in KNOWN_TAGS:
                raise UnknownTag(
                    f"unknown tag {tag!r} on {name}. Tags available: "
                    f"{', '.join(sorted(KNOWN_TAGS))}"
                )
            tags.setdefault(name, set()).add(tag)
    return {n: frozenset(v) for n, v in tags.items()}
