from enum import Enum

class Intent(str, Enum):
    POLICY = "POLICY"
    LOAN_ELIGIBILITY = "LOAN_ELIGIBILITY"
    UNKNOWN = "UNKNOWN"
