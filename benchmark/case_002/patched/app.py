def normalize_percentage(value: int) -> int:
    if value < 0 or value >= 100:
        raise ValueError("percentage must be between 0 and 100")
    return value
