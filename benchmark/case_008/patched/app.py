def first_nonempty(values: list[str]) -> str | None:
    return next((value for value in values if len(value) > 0), None)
