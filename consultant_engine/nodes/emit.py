import re
from pathlib import Path
from consultant_engine.state import ConsultantState
import consultant_engine


def emit(state: ConsultantState) -> dict:
    """Write the generated proposal HTML to a version-stamped file.

    Filename format: FundProposal_<Profile>_<MonYYYY>[_<ClientLastName>]_v<version>.html
    where:
      - <Profile> = risk_level with spaces removed
      - <MonYYYY> = extracted from fundmaster_path filename (e.g., "Jun2026")
      - [_<ClientLastName>] = included only if client_name is set (last whitespace-separated token)
      - <version> = extracted from proposal_html stamp "fund-consultant v<version>"
    """
    html = state["proposal_html"]
    client_profile = state["client_profile"]
    fundmaster_path = state["fundmaster_path"]
    output_dir = Path(state.get("output_dir", "output/fund_proposals"))

    # Extract version from the HTML stamp "fund-consultant v<version>"
    version_match = re.search(r'fund-consultant v([\d.]+)', html)
    version = version_match.group(1) if version_match else consultant_engine.__version__

    # Extract MonYYYY from fundmaster filename using regex
    # Pattern: PublicMutual_FundMaster_<MonYYYY>_v<ver>.xlsx
    fundmaster_basename = Path(fundmaster_path).name
    match = re.search(r'PublicMutual_FundMaster_([A-Za-z]+\d{4})_v[\d.]+\.xlsx', fundmaster_basename)
    month_year = match.group(1) if match else "Unknown"

    # Extract risk_level and remove spaces
    risk_level = client_profile["risk_level"].replace(" ", "")

    # Build filename
    filename = f"FundProposal_{risk_level}_{month_year}"

    # Add client last name if present
    client_name = client_profile.get("client_name")
    if client_name:
        # Get last whitespace-separated token and strip non-alphanumerics
        last_name = client_name.split()[-1]
        last_name = re.sub(r'[^A-Za-z0-9]', '', last_name)
        if last_name:
            filename += f"_{last_name}"

    # Add version and extension
    filename += f"_v{version}.html"

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path = output_dir / filename
    output_path.write_text(html, encoding='utf-8')

    return {"output_path": str(output_path)}
