from preptrack.models.enums import BlockCategory


def allocate_minutes(
    available_minutes: int,
    percentages: dict[str, float],
    news_minutes: int = 20,
) -> dict[BlockCategory, int]:
    """Allocate minutes per category from blueprint percentages.

    Deducts news_minutes first, then distributes remaining by percentage.
    Returns a dict of BlockCategory → minutes (rounded, summing to remaining).
    """
    remaining = max(0, available_minutes - news_minutes)

    raw: dict[BlockCategory, float] = {}
    for cat_name, pct in percentages.items():
        cat = BlockCategory(cat_name)
        raw[cat] = remaining * (pct / 100.0)

    # Round down, then distribute remainder to largest fractional parts
    floored: dict[BlockCategory, int] = {cat: int(v) for cat, v in raw.items()}
    remainder = remaining - sum(floored.values())

    if remainder > 0:
        fractionals = sorted(
            raw.keys(),
            key=lambda c: raw[c] - floored[c],
            reverse=True,
        )
        for i in range(min(remainder, len(fractionals))):
            floored[fractionals[i]] += 1

    return floored
