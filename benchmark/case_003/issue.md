# Username formatting should trim only surrounding whitespace

`format_username` should normalize case and remove leading or trailing whitespace while preserving meaningful internal spaces. The current implementation leaves surrounding whitespace intact.
