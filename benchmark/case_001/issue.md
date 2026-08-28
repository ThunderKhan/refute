# Zero is a valid percentage

`clamp_percentage` should accept every integer from 0 through 100 inclusive. The current implementation raises `ValueError` for `0`, even though zero is a valid percentage.
