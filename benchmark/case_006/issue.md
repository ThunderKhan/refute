# Truncated text can exceed the requested limit

`truncate(text, limit)` must never return more than `limit` characters. When truncation is required it should use an ellipsis, including very small non-negative limits.
