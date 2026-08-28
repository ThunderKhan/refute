from enum import Enum


class AgentRole(str, Enum):
    INVESTIGATOR = "investigator"
    REPRODUCER = "reproducer"
    CHALLENGER = "challenger"
    VERIFIER = "verifier"


__all__ = ["AgentRole"]
