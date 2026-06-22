"""Shared graph state types.

ConsultantState is the typed dict threaded through every pipeline node; ClientProfile
and Fund describe the nested shapes (the client's risk profile and a per-fund record
produced by load_funds). Each node reads a subset of these keys and returns a partial
dict that LangGraph merges back into the running state.
"""

from typing import TypedDict, Literal, Optional

class ClientProfile(TypedDict):
    risk_level: str          # Conservative|Moderate|Moderately Aggressive|Aggressive
    shariah: Optional[bool]  # True | False | None (no preference)
    experience: Literal["new", "experienced"]
    upfront_capital_rm: float
    target_annual_return_pct: float          # percent p.a., e.g. 5.0
    goals: Optional[str]
    client_name: str         # optional; load_profile normalizes + defaults to "" (generic)

class Fund(TypedDict, total=False):
    abbr: str
    name: str
    shariah: bool
    fund_type: str
    risk_level: int
    status: str              # "Qualified" | "Disqualified"
    weighted_alpha: float
    returns: dict            # {"ytd":{"fund","bench","alpha"}, "1y":..., "3y":..., "5y":..., "10y":...}
    alpha_efficiency: dict                 # {"ytd","1y","3y","5y","10y"}
    assets: dict             # {"dom_equity","for_equity","fi","mm","deposits","other"}
    geo: dict                # %/country, exact FundMaster headers: {"USA","Taiwan","Korea","Japan","France","Germany","China","Singapore","Netherlands","Indonesia","Australia","Geo Other"}
    top5_holdings: list
    volatility_factor: float
    lipper_class: str
    benchmark: str
    drawdown: Optional[float]
    days_from_ath: Optional[int]

class CFSScore(TypedDict):
    abbr: str
    alpha_n: float
    returnfit_n: float
    efficiency_n: float
    momentum_n: float
    composite: float
    weights: dict            # {"alpha","returnfit","efficiency","momentum"}
    derived_class: str       # Equity-equivalent | Balanced | Defensive

class Holding(TypedDict):
    abbr: str
    role: str                # core | structural:gold | structural:money_market | satellite | exposure_gap
    allocation_pct: float

class ConsultantState(TypedDict, total=False):
    # inputs
    client_profile: ClientProfile
    macro_context: dict
    fundmaster_path: str
    thread_id: str
    no_review: bool
    model: str
    output_dir: str
    # computed
    eligible_funds: list
    filtered_funds: list
    cfs_scores: list
    portfolio: list
    fees: dict
    # review
    proposed_allocation: dict
    resume_payload: dict
    # generation
    proposal_html: str
    # validation
    violations: list
    repair_iterations: int
    # output
    output_path: str
    # HITL resume
    _universe: set
