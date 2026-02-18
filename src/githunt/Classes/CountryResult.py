from dataclasses import dataclass

@dataclass
class CountryResult:
    code: str
    name: str
    flag: str
    score: float
    probability: float
    match_fraction: float
    wake_fraction: float
    tz_count: int
