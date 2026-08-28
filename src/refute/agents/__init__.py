from enum import Enum

from .investigator import Investigation, investigate


class AgentRole(str, Enum):
    INVESTIGATOR = "investigator"
    REPRODUCER = "reproducer"
    CHALLENGER = "challenger"
    VERIFIER = "verifier"


__all__ = ["AgentRole", "Investigation", "investigate"]
