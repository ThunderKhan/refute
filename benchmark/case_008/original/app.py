def first_nonempty(values: list[str]) -> str | None:
    return next((value for value in values if value), None)
