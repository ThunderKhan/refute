# Percentage boundaries are inclusive

`normalize_percentage` should accept values from 0 through 100 inclusive. The current implementation rejects both boundary values. A correct patch must restore the full inclusive range, not only the originally reported lower boundary.
