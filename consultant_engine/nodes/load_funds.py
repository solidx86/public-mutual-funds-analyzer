import openpyxl
from consultant_engine.state import ConsultantState

# Step 1b: funds excluded from retail eligibility
WHOLESALE = {"PBCPF", "PWSIF", "PIWSIF", "PeWS20F"}


def _excluded(name: str, abbr: str) -> bool:
    if name is None or abbr is None:
        return True
    return name.startswith("PB ") or abbr.endswith("-B") or abbr in WHOLESALE


def load_funds(state: ConsultantState) -> dict:
    path = state["fundmaster_path"]
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Master"]

    # Read geo header names from row 3, cols 41–52
    geo_headers = []
    for col in range(41, 53):
        cell_val = ws.cell(3, col).value
        geo_headers.append(cell_val if cell_val is not None else f"col{col}")

    # Period names in order, starting at col 15; 5 periods × 3 cols each
    PERIOD_NAMES = ["ytd", "1y", "3y", "5y", "10y"]
    AE_KEYS = ["ytd", "1y", "3y", "5y", "10y"]
    ASSET_KEYS = ["dom_equity", "for_equity", "fi", "mm", "deposits", "other"]

    eligible_funds = []

    # Data starts at row 4; stop when col 2 (abbr) is empty
    row = 4
    while True:
        abbr = ws.cell(row, 2).value
        if abbr is None or str(abbr).strip() == "":
            break

        abbr = str(abbr).strip()
        name_val = ws.cell(row, 1).value
        name = str(name_val).strip() if name_val is not None else ""

        if _excluded(name, abbr):
            row += 1
            continue

        shariah_raw = ws.cell(row, 3).value
        shariah = True if str(shariah_raw).strip().lower() == "yes" else False

        fund_type = ws.cell(row, 4).value
        risk_level_raw = ws.cell(row, 6).value
        risk_level = int(risk_level_raw) if risk_level_raw is not None else None

        status_val = ws.cell(row, 10).value
        status = str(status_val).strip() if status_val is not None else None

        walpha_raw = ws.cell(row, 14).value
        weighted_alpha = float(walpha_raw) if walpha_raw is not None else None

        # Returns: cols 15–29, 5 periods × 3 cols each
        returns = {}
        for i, period in enumerate(PERIOD_NAMES):
            base_col = 15 + i * 3
            fund_r = ws.cell(row, base_col).value
            bench_r = ws.cell(row, base_col + 1).value
            alpha_r = ws.cell(row, base_col + 2).value
            returns[period] = {
                "fund": float(fund_r) if fund_r is not None else None,
                "bench": float(bench_r) if bench_r is not None else None,
                "alpha": float(alpha_r) if alpha_r is not None else None,
            }

        # AE: cols 30–34
        ae = {}
        for i, key in enumerate(AE_KEYS):
            val = ws.cell(row, 30 + i).value
            ae[key] = float(val) if val is not None else None

        # Assets: cols 35–40
        assets = {}
        for i, key in enumerate(ASSET_KEYS):
            val = ws.cell(row, 35 + i).value
            assets[key] = float(val) if val is not None else None

        # Geo: cols 41–52, keyed by row-3 headers
        geo = {}
        for i, header in enumerate(geo_headers):
            val = ws.cell(row, 41 + i).value
            geo[header] = float(val) if val is not None else None

        # Top-5 holdings — col 64 is a " | "-delimited string in the real workbook
        # (build_sheet_data.py joins with ' | '). Split to a list so overlap checks
        # compare holding names, not characters.
        top5_raw = ws.cell(row, 64).value
        if top5_raw is None or top5_raw == "":
            top5 = []
        else:
            top5 = [h.strip() for h in str(top5_raw).split("|") if h.strip()]

        vf_raw = ws.cell(row, 65).value
        vf = float(vf_raw) if vf_raw is not None else None

        lipper_class_raw = ws.cell(row, 67).value
        lipper_class = str(lipper_class_raw).strip() if lipper_class_raw is not None else None

        benchmark_raw = ws.cell(row, 68).value
        benchmark = str(benchmark_raw).strip() if benchmark_raw is not None else None

        # Explicit None checks — 0.0 is a valid drawdown
        drawdown_raw = ws.cell(row, 72).value
        drawdown = float(drawdown_raw) if drawdown_raw is not None else None

        days_raw = ws.cell(row, 73).value
        days_from_ath = int(days_raw) if days_raw is not None else None

        fund: dict = {
            "abbr": abbr,
            "name": name,
            "shariah": shariah,
            "fund_type": fund_type,
            "risk_level": risk_level,
            "status": status,
            "weighted_alpha": weighted_alpha,
            "returns": returns,
            "ae": ae,
            "assets": assets,
            "geo": geo,
            "top5": top5,
            "vf": vf,
            "lipper_class": lipper_class,
            "benchmark": benchmark,
            "drawdown": drawdown,
            "days_from_ath": days_from_ath,
        }
        eligible_funds.append(fund)
        row += 1

    wb.close()
    return {"eligible_funds": eligible_funds}
