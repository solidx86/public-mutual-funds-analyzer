"""
Public Mutual MFR Fund Performance Extractor (v2)
- Coordinate-based right-column extraction for Top5 Holdings, Sectors, Geo Breakdown
- YTD returns, Distribution Policy, Asset Allocation, Volatility Class
- Latest-MFR-only file discovery
- Fund Objective classification from PHS
"""

import pdfplumber
import re
import json
import os
import sys
import glob
from collections import defaultdict

# ╔══════════════════════════════════════════════════════════════════╗
# ║  CONFIGURE THESE PATHS before running                          ║
# ╚══════════════════════════════════════════════════════════════════╝
_FUNDS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = os.path.join(_FUNDS_DIR, "Unit Trust (UT)")
PHS_DIR  = os.path.join(_FUNDS_DIR, "Unit Trust (UT)", "Product Highlight Sheet (PHS)")
OUT_DIR  = _FUNDS_DIR

TARGET_PERIODS = ["1-year", "3-year", "5-year", "10-year"]

MONTH_ORDER = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
               'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}


# ── MFR File Discovery ───────────────────────────────────────────────────────

def discover_latest_mfr_files(base_dir):
    """Find only the latest MFR files per series by parsing month-year from filenames."""
    all_files = [f for f in os.listdir(base_dir) if f.startswith('[MFR') and f.endswith('.pdf')]

    series_best = {}  # series_name -> (date_val, filepath)
    for fname in all_files:
        m = re.match(r'\[MFR\s+([A-Z]{3})(\d{2})\]\s*(.+)\.pdf$', fname)
        if not m:
            continue
        month_str, year_str, series = m.group(1), m.group(2), m.group(3).strip()
        month_val = MONTH_ORDER.get(month_str, 0)
        date_val = int(year_str) * 100 + month_val

        if series not in series_best or date_val > series_best[series][0]:
            series_best[series] = (date_val, os.path.join(base_dir, fname))

    result = [v[1] for v in series_best.values()]
    print(f"Discovered {len(result)} latest MFR files:")
    for f in result:
        print(f"  {os.path.basename(f)}")
    return result


# ── Right-Column Extraction (coordinate-based) ───────────────────────────────

def extract_right_column(page, page_width=595.2):
    """Extract text from the right column of an MFR page using word coordinates."""
    midpoint = page_width * 0.52
    try:
        words = page.extract_words(keep_blank_chars=True)
    except Exception:
        return ""

    lines = defaultdict(list)
    for word in words:
        if word['x0'] >= midpoint:
            y_key = round(word['top'] / 4) * 4
            lines[y_key].append(word)

    result = []
    for y_key in sorted(lines.keys()):
        line_words = sorted(lines[y_key], key=lambda w: w['x0'])
        line_text = ' '.join(w['text'] for w in line_words)
        result.append(line_text)

    return '\n'.join(result)


def extract_sectors_from_right_col(right_col):
    """Parse Top 5 Sectors from right-column text.
    Handles both 'Top 5 Sectors' and standalone 'Sectors' headings.
    """
    sectors = []
    in_sector = False
    for line in right_col.split('\n'):
        stripped = line.strip()
        # Trigger on 'Top 5 Sectors' OR standalone 'Sectors' heading
        if 'Top 5 Sectors' in line:
            in_sector = True
            continue
        if not in_sector and stripped == 'Sectors':
            in_sector = True
            continue
        if in_sector and stripped == 'Sectors':
            # Skip duplicate 'Sectors' sub-heading after 'Top 5 Sectors'
            continue
        if in_sector and ('Top 5 Holdings' in line or 'Top 5 Bond' in line
                          or 'Security Name' in line or 'Holdings' in stripped):
            break
        if in_sector:
            m = re.search(r'([A-Za-z][A-Za-z,/ \-&\.]+?)\s+(\d+\.\d+)%', line)
            if m:
                sectors.append({'sector': m.group(1).strip(), 'weight': m.group(2) + '%'})
    return sectors[:5]


def extract_holdings_from_right_col(right_col):
    """Parse Top 5 Holdings from right-column text."""
    holdings = []
    in_holdings = False
    for line in right_col.split('\n'):
        if 'Security Name' in line:
            in_holdings = True
            after = line.split('Security Name')[-1].strip()
            if after and len(after) > 3 and not re.match(r'^[\d.%\-]+$', after):
                holdings.append(after)
            continue
        if in_holdings:
            if len(holdings) >= 5:
                break
            if any(x in line for x in ['Distribution', 'Notes:', 'Sukuk', 'Islamic Bonds',
                                        'Islamic Commercial', '* Sukuk']):
                break
            cleaned = line.strip()
            if cleaned and len(cleaned) > 3 and not re.match(r'^[\d.%\-\s]+$', cleaned):
                holdings.append(cleaned)
    return holdings[:5]


def extract_geo_from_right_col(right_col):
    """Parse geographical breakdown from right-column text."""
    # Known country/region names to accept
    KNOWN_COUNTRIES = {
        'USA', 'China', 'Taiwan', 'Korea', 'Japan', 'India', 'Hong Kong',
        'Singapore', 'Thailand', 'Indonesia', 'Vietnam', 'Malaysia', 'Philippines',
        'Australia', 'New Zealand', 'UK', 'United Kingdom', 'France', 'Germany',
        'Netherlands', 'Switzerland', 'Italy', 'Spain', 'Sweden', 'Denmark',
        'Norway', 'Finland', 'Ireland', 'Canada', 'Brazil', 'Mexico', 'South Africa',
        'Saudi Arabia', 'Qatar', 'UAE', 'Egypt', 'Turkey', 'Russia', 'Poland',
        'Czech Republic', 'Others',
    }

    geo = {}
    in_geo = False
    for line in right_col.split('\n'):
        if 'Geographical Breakdown' in line:
            in_geo = True
            continue
        if in_geo and line.strip() == 'Breakdown':
            continue
        if in_geo:
            if any(x in line for x in ['Top 5', 'Performance', 'Breakdown of', 'Sectors']):
                break
            m = re.search(r'([A-Za-z][A-Za-z ]+?)\s+(\d+\.\d+)%', line)
            if m:
                name = m.group(1).strip()
                # Only accept known countries/regions
                if name in KNOWN_COUNTRIES:
                    geo[name] = float(m.group(2))
    return geo


# ── Full-Text Extraction Functions ───────────────────────────────────────────

def extract_pages_from_pdf(pdf_path):
    """Extract page-by-page text, right-column text, and allocation from a PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        pw = pdf.pages[0].width if pdf.pages else 595.2
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            right_col = extract_right_column(page, pw)
            alloc = extract_allocation_from_page(page)
            if text:
                pages.append((i + 1, text, right_col, alloc))
    return pages


def parse_fund_pages(pages):
    """Split raw pages into per-fund blocks. Returns (fund_meta, full_text, right_col_text, alloc)."""
    fund_blocks = []
    current_fund = None
    current_text = []
    current_right = []
    current_alloc = {}

    for page_num, text, right_col, alloc in pages:
        lines = text.split('\n')
        header_match = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Pattern 1: ALL-CAPS e.g. "PUBLIC GROWTH FUND (PGF) EPFQualified Fund"
            # Also handles "EPF Qualified Fund" (space after EPF) and mixed-case abbr like "P SmallCap"
            m = re.match(r'^([A-Z][A-Z0-9 &\-\./]+)\(([A-Za-z0-9\- ]+)\)\s*(?:EPF\s*\w*(?:\s+\w+)*)?$', stripped)
            if m and i < 5:
                header_match = m
                break
            # Pattern 2: Mixed-case e-Series
            m2 = re.match(r'^(PUBLIC\s+e-[A-Za-z0-9 &\-\./]+FUND[A-Za-z0-9 \-]*)\(([A-Za-z0-9\- ]+)\)\s*$',
                          stripped, re.IGNORECASE)
            if m2 and i < 5:
                header_match = m2
                break
            # Pattern 3: Islamic e-Series
            m3 = re.match(r'^(PUBLIC\s+e-[A-Za-z0-9 &\-\./]+)\(([A-Za-z0-9\- ]+)\)\s*$', stripped)
            if m3 and i < 5 and ('Fund' in stripped or 'FUND' in stripped):
                header_match = m3
                break

        if header_match:
            if current_fund:
                fund_blocks.append((current_fund, '\n'.join(current_text),
                                    '\n'.join(current_right), current_alloc))
            current_fund = {
                'name': header_match.group(1).strip(),
                'abbr': header_match.group(2).strip(),
                'page': page_num
            }
            current_text = [text]
            current_right = [right_col]
            current_alloc = alloc
        elif current_fund:
            current_text.append(text)
            current_right.append(right_col)
            if alloc and not current_alloc:
                current_alloc = alloc

    if current_fund:
        fund_blocks.append((current_fund, '\n'.join(current_text),
                            '\n'.join(current_right), current_alloc))

    return fund_blocks


def extract_performance(text, fund_name):
    """Extract annualised returns for fund and benchmark."""
    results = {}
    perf_section = re.search(
        r'Performance of .+?(?=Annual Returns for Calendar|Performances of \w+ and)',
        text, re.DOTALL | re.IGNORECASE
    )
    search_text = perf_section.group(0) if perf_section else text

    for period in ["Year-to-Date", "1-year", "3-year", "5-year", "10-year",
                   "20-year", "30-year", "Since Commencement"]:
        # 4 numbers: total_fund, total_bench, ann_fund, ann_bench
        stored = False
        pattern = rf'{re.escape(period)}\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)'
        m = re.search(pattern, search_text, re.IGNORECASE)
        if m:
            try:
                ann_f, ann_b = float(m.group(3)), float(m.group(4))
                results[period] = (ann_f, ann_b)
                stored = True
            except ValueError:
                pass
        if not stored:
            # 2-number version (YTD or fallback)
            pattern2 = rf'{re.escape(period)}\s+([-\d.]+)\s+([-\d.]+)'
            m2 = re.search(pattern2, search_text, re.IGNORECASE)
            if m2:
                try:
                    tot_f, tot_b = float(m2.group(1)), float(m2.group(2))
                    results[period + "_total"] = (tot_f, tot_b)
                except ValueError:
                    pass
    return results


def extract_ytd(performance):
    """Extract YTD total returns from performance dict."""
    if "Year-to-Date_total" in performance:
        f, b = performance["Year-to-Date_total"]
        return {'fund': f, 'benchmark': b}
    if "Year-to-Date" in performance:
        f, b = performance["Year-to-Date"]
        return {'fund': f, 'benchmark': b}
    return None


def extract_annual_returns(text):
    """Extract calendar year annual returns."""
    year_match = re.search(r'Calendar Year\s+((?:\d{4}\s*)+)', text)
    fund_match = re.search(r'Fund Return\s*\(?\s*%?\s*\)?\s*\(%\)\s*((?:[-\d.]+\s*)+)', text)
    if not fund_match:
        fund_match = re.search(r'Fund Return\D*((?:[-\d.]+\s*)+)', text)
    bench_match = re.search(r'Benchmark\s*\(%\)\s*((?:[-\d.]+\s*)+)', text)

    if not (year_match and fund_match and bench_match):
        return {}

    yr_list = year_match.group(1).split()
    fund_vals = fund_match.group(1).split()
    bench_vals = bench_match.group(1).split()

    annual = {}
    for i, yr in enumerate(yr_list):
        if i < len(fund_vals) and i < len(bench_vals):
            try:
                annual[yr] = (float(fund_vals[i]), float(bench_vals[i]))
            except ValueError:
                pass
    return annual


def extract_fund_metadata(text):
    """Extract fund size, launch date, lipper rating, VF, benchmark, distribution policy."""
    meta = {}

    ld = re.search(r'Launch Date\s*:\s*(\d{2}\.\d{2}\.\d{4})', text)
    if ld:
        meta['launch_date'] = ld.group(1)

    nav = re.search(r'NAV\s*:\s*RM([\d,]+\.?\d*)\s*Million', text)
    if nav:
        meta['fund_size_rm_mil'] = nav.group(1).replace(',', '')

    vf = re.search(r'Volatility Factor.*?(\d+\.?\d*)', text)
    if vf:
        meta['volatility_factor'] = vf.group(1)

    lc = re.search(r'Lipper Classification\s*:\s*(.+?)(?:\n|Lipper|•)', text)
    if lc:
        meta['lipper_class'] = lc.group(1).strip()

    bm = re.search(r'Benchmark:\s*\n(.+?)(?:\n\n|\*|Index data|Source)', text, re.DOTALL)
    if bm:
        meta['benchmark'] = ' '.join(bm.group(1).replace('\n', ' ').split())

    # Distribution Policy — strip right-column bleed-through
    dp = re.search(r'Distribution Policy\s*:\s*(.+?)(?:\n|$)', text)
    if dp:
        raw_dp = dp.group(1).strip()
        # Remove right-column contamination
        for noise in ['Geographical Breakdown', 'Top 5', 'Security Name', 'Breakdown of',
                       'Government Investment', 'Sarawak Energy', 'Pengurusan']:
            idx = raw_dp.find(noise)
            if idx > 0:
                raw_dp = raw_dp[:idx].strip()
        meta['distribution_policy'] = raw_dp

    return meta


def extract_allocation_from_page(page):
    """Extract asset allocation using coordinate-based left-column extraction.
    Returns dict of asset_type -> percentage."""
    allocation = {}
    try:
        words = page.extract_words()
    except Exception:
        return allocation

    # Find y-position of "Asset Allocation" heading
    alloc_y = None
    total_y = None
    for w in words:
        if w['text'] == 'Asset':
            # Check if "Allocation" follows nearby
            for w2 in words:
                if w2['text'] == 'Allocation' and abs(w2['top'] - w['top']) < 5:
                    alloc_y = w['top']
                    break
        if w['text'] == 'Total' and alloc_y and w['top'] > alloc_y:
            # Check if "100.0%" follows nearby
            for w2 in words:
                if '100.0%' in w2['text'] and abs(w2['top'] - w['top']) < 5:
                    total_y = w['top']
                    break
        if alloc_y and total_y:
            break

    if not alloc_y:
        return allocation

    end_y = total_y if total_y else alloc_y + 120

    # Get left-column words (x < 310) between heading and Total
    left_words = [w for w in words
                  if w['top'] > alloc_y + 5 and w['top'] < end_y and w['x0'] < 310]

    # Reconstruct lines
    lines_dict = defaultdict(list)
    for w in left_words:
        y_key = round(w['top'] / 4) * 4
        lines_dict[y_key].append(w)

    lines = []
    for y_key in sorted(lines_dict.keys()):
        line_words = sorted(lines_dict[y_key], key=lambda w: w['x0'])
        line_text = ' '.join(w['text'] for w in line_words)
        lines.append(line_text)

    # Parse allocation lines.
    # The PDF layout puts percentage to the right of multi-line labels,
    # with continuation lines AFTER the percentage line.
    # Pattern: [label_start] -> [XX.X%] -> [label_continuation] -> [next_label_start] -> ...
    entries = []  # list of (label_parts, pct)
    current_label_parts = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or 'Asset Type' in line:
            continue

        m = re.search(r'(\d+\.\d+)%', line)
        if m:
            pct = float(m.group(1))
            before_pct = line[:m.start()].strip()
            if before_pct:
                current_label_parts.append(before_pct)

            # Check if next line(s) are continuations (start with "securities" etc.)
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith('securities') or next_line.startswith('Islamic'):
                    if not re.search(r'\d+\.\d+%', next_line):
                        current_label_parts.append(next_line)
                        i += 1
                        continue
                break

            if current_label_parts:
                full_label = ' '.join(current_label_parts)
                allocation[full_label] = pct
            current_label_parts = []
        else:
            current_label_parts.append(line)

    return allocation


# ── Volatility Class ──────────────────────────────────────────────────────────

def classify_volatility(vf_str):
    """Classify VF into volatility class per SC banding as at 31 Jan 2026."""
    if not vf_str:
        return ''
    try:
        vf = float(vf_str)
    except (ValueError, TypeError):
        return ''
    if vf <= 4.245:
        return 'Very Low'
    if vf <= 7.795:
        return 'Low'
    if vf <= 10.235:
        return 'Moderate'
    if vf <= 13.595:
        return 'High'
    return 'Very High'


# ── Fund Objective from PHS ──────────────────────────────────────────────────

def classify_objective_from_phs(abbr, phs_dir=PHS_DIR):
    """Read the fund's PHS to extract and classify the fund objective + category of fund."""
    # Strip spaces from abbreviation for filename (P ITTIKAL -> PITTIKAL)
    clean_abbr = abbr.replace(' ', '')
    phs_path = os.path.join(phs_dir, f'{clean_abbr}_PHS.pdf')
    if not os.path.exists(phs_path):
        return '', '', ''

    try:
        with pdfplumber.open(phs_path) as pdf:
            text = pdf.pages[0].extract_text() or ''
    except Exception:
        return '', '', ''

    # ── Extract Category of Fund ──────────────────────────────────────────────
    phs_category = ''
    cat_match = re.search(r'Category\s+(?:of\s+)?[Ff]und\s*[:\-]?\s*(.+?)(?:\n|Fund type|Type of fund)',
                          text, re.IGNORECASE)
    if cat_match:
        phs_category = cat_match.group(1).strip().rstrip('.')
    else:
        # Fallback: look for "Category" followed by a value
        cat_match2 = re.search(r'Category\s*[:\-]\s*(.+?)(?:\n)', text, re.IGNORECASE)
        if cat_match2:
            phs_category = cat_match2.group(1).strip().rstrip('.')

    # Standardize PHS category into 5 types
    fund_type = classify_phs_category(phs_category)

    # ── Extract objective text ────────────────────────────────────────────────
    m = re.search(r'Fund objective\s*(.*?)(?:Note:|Asset allocation|\nThis fund)',
                  text, re.DOTALL | re.IGNORECASE)
    obj_text = m.group(1).strip()[:300] if m else ''

    if not obj_text:
        m2 = re.search(r'objective.*?(?:To |Seeks? )(.*?)(?:\.|Note:)', text, re.DOTALL | re.IGNORECASE)
        if m2:
            obj_text = m2.group(1).strip()[:300]

    obj_lower = obj_text.lower()

    # Classify objective
    has_growth = any(x in obj_lower for x in ['capital growth', 'growth of capital',
                                                'capital appreciation'])
    has_income = any(x in obj_lower for x in ['income', 'dividend', 'yield'])
    has_both = any(x in obj_lower for x in ['growth and income', 'income and',
                                              'combination of', 'capital growth and income',
                                              'growth & income'])

    if has_both or (has_growth and has_income):
        obj_category = 'Capital Growth + Income'
    elif has_income:
        obj_category = 'Income'
    elif has_growth:
        obj_category = 'Capital Growth'
    elif 'liquidity' in obj_lower or 'capital stability' in obj_lower or 'preserve' in obj_lower:
        obj_category = 'Income'
    elif any(x in obj_lower for x in ['gold', 'commodity', 'price of', 'exposure to']):
        obj_category = 'Capital Growth'
    else:
        obj_category = ''

    return obj_category, obj_text, fund_type


def classify_phs_category(raw_category):
    """Map raw PHS 'Category of Fund' to standardized fund type."""
    if not raw_category:
        return ''
    low = raw_category.lower()

    # Fund of Funds (must check before others)
    if 'fund-of-funds' in low or 'fund of funds' in low:
        return 'Fund of Funds'
    # Money Market
    if 'money market' in low:
        return 'Money Market'
    # Fixed Income (bond, sukuk, fixed income)
    if any(x in low for x in ['bond', 'sukuk', 'fixed income']):
        return 'Fixed Income'
    # Mixed Asset / Balanced
    if any(x in low for x in ['mixed asset', 'balanced']):
        return 'Mixed Asset / Balanced'
    # Equity
    if 'equity' in low:
        return 'Equity'
    # Wholesale funds — check underlying type
    if 'wholesale' in low:
        if 'money' in low:
            return 'Money Market'
        return ''
    return ''


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_fund(performance):
    """Calculate outperformance rate across YTD, 1Y, 3Y, 5Y, 10Y. Min 2 periods.
    YTD is included as a scoring period alongside the annualised periods.
    """
    outperform = 0
    total = 0
    detail = {}

    # Include YTD as a scoring period
    ytd_key = None
    if "Year-to-Date_total" in performance:
        ytd_key = "Year-to-Date_total"
    elif "Year-to-Date" in performance:
        ytd_key = "Year-to-Date"

    if ytd_key:
        fund_ret, bench_ret = performance[ytd_key]
        beats = fund_ret > bench_ret
        detail['ytd'] = {
            'fund': fund_ret,
            'benchmark': bench_ret,
            'outperforms': beats,
            'alpha': round(fund_ret - bench_ret, 2)
        }
        if beats:
            outperform += 1
        total += 1

    for period in TARGET_PERIODS:
        if period in performance:
            fund_ret, bench_ret = performance[period]
            beats = fund_ret > bench_ret
            detail[period] = {
                'fund': fund_ret,
                'benchmark': bench_ret,
                'outperforms': beats,
                'alpha': round(fund_ret - bench_ret, 2)
            }
            if beats:
                outperform += 1
            total += 1

    rate = (outperform / total * 100) if total > 0 else 0
    return outperform, total, round(rate, 1), detail


# ── Asset Class / Geography ───────────────────────────────────────────────────

def determine_asset_class(fund_name, lipper_class, abbr):
    name_upper = fund_name.upper()
    lc = lipper_class.upper() if lipper_class else ''

    # Check Lipper class first for more accurate classification
    if 'MONEY MARKET' in name_upper or 'CASH DEPOSIT' in name_upper or 'CASH MANAGEMENT' in name_upper:
        return 'Money Market'
    if 'SUKUK' in name_upper or 'SUKUK' in lc:
        return 'Bond / Sukuk'
    if 'BALANCED' in name_upper:
        return 'Balanced'
    if 'MIXED ASSET' in lc or ('ALLOCATION' in name_upper and 'TACTICAL' not in name_upper
                                and 'FLEXI' not in name_upper):
        return 'Mixed Asset'
    if 'MIXED' in name_upper or 'ALLOCATION' in name_upper or 'FLEXI' in name_upper:
        return 'Mixed Asset'
    if any(x in name_upper for x in ['BOND', 'FIXED INCOME']):
        return 'Bond / Fixed Income'
    if 'INCOME' in name_upper and 'BOND' in lc:
        return 'Bond / Fixed Income'
    if 'INCOME' in name_upper and 'EQUITY' not in lc:
        return 'Bond / Fixed Income'
    if 'EQUITY' in lc or 'EQUITY' in name_upper:
        if 'MALAYSIA' in lc or any(x in name_upper for x in ['MALAYSIA', 'DOMESTIC']):
            return 'Equity - Malaysia'
        return 'Equity - Foreign'
    # Fallback: use Lipper class keywords
    if any(x in lc for x in ['BOND', 'SUKUK', 'FIXED']):
        return 'Bond / Fixed Income'
    if 'EQUITY' in lc:
        return 'Equity - Malaysia'
    return 'Other'


def determine_geography(fund_name, lipper_class):
    name_upper = fund_name.upper()
    lc = lipper_class.upper() if lipper_class else ''

    if any(x in name_upper for x in ['MALAYSIA', 'DOMESTIC', 'KLCI', 'ITTIKAL']):
        return 'Malaysia'
    if any(x in name_upper for x in ['CHINA', 'GREATER CHINA']):
        return 'Greater China'
    if any(x in name_upper for x in ['ASEAN', 'SOUTHEAST ASIA', 'SOUTH-EAST ASIA']):
        return 'ASEAN'
    if any(x in name_upper for x in ['ASIA PACIFIC', 'FAR-EAST', 'FAR EAST']):
        return 'Asia Pacific'
    if 'ASIA' in name_upper:
        return 'Asia'
    if any(x in name_upper for x in ['US ', 'U.S.', 'AMERICA', 'NASDAQ']):
        return 'United States'
    if any(x in name_upper for x in ['GLOBAL', 'WORLDWIDE']):
        return 'Global'
    if 'INDONESIA' in name_upper:
        return 'Indonesia'
    if 'INDIA' in name_upper:
        return 'India'
    if 'JAPAN' in name_upper:
        return 'Japan'
    if 'AUSTRALIA' in name_upper:
        return 'Australia'
    if 'VIETNAM' in name_upper:
        return 'Vietnam'
    if 'SINGAPORE' in name_upper:
        return 'Singapore'
    return 'Malaysia'


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def process_all_mfrs():
    """Process all latest MFR files and return qualified funds."""
    all_funds = []
    qualified_funds = []

    mfr_files = discover_latest_mfr_files(BASE_DIR)
    if not mfr_files:
        print("ERROR: No MFR files found!")
        return [], []

    for fpath in mfr_files:
        fname = os.path.basename(fpath)
        if not os.path.exists(fpath):
            print(f"  [SKIP] Not found: {fname}")
            continue

        # Skip PRS files — only process UT
        if 'PRS' in fname:
            print(f"  [SKIP] PRS file: {fname}")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {fname}")
        print('='*60)

        pages = extract_pages_from_pdf(fpath)
        fund_blocks = parse_fund_pages(pages)
        print(f"  Found {len(fund_blocks)} fund blocks")

        for fund_meta, text, right_col, page_alloc in fund_blocks:
            performance = extract_performance(text, fund_meta['name'])
            ytd = extract_ytd(performance)
            annual_returns = extract_annual_returns(text)
            metadata = extract_fund_metadata(text)
            asset_alloc = page_alloc  # coordinate-based extraction

            # Right-column data
            sectors = extract_sectors_from_right_col(right_col)
            holdings = extract_holdings_from_right_col(right_col)
            geo = extract_geo_from_right_col(right_col)

            # Scoring
            out_count, total_p, rate, detail = score_fund(performance)

            # Classification
            lc = metadata.get('lipper_class', '')
            asset_class = determine_asset_class(fund_meta['name'], lc, fund_meta['abbr'])
            geography = determine_geography(fund_meta['name'], lc)
            is_shariah = ('shariah' in fname.lower()
                          or 'Islamic' in fund_meta['name']
                          or fund_meta['abbr'].startswith('PI')
                          or fund_meta['abbr'].startswith('PeI')
                          or fund_meta['abbr'].startswith('PeS'))

            # Volatility class
            vc = classify_volatility(metadata.get('volatility_factor'))

            # PHS objective + category
            obj_class, obj_text, phs_fund_type = classify_objective_from_phs(fund_meta['abbr'])

            fund_data = {
                **fund_meta,
                'source_file': fname,
                'asset_class': asset_class,
                'geography': geography,
                'is_shariah': is_shariah,
                'performance': performance,
                'ytd': ytd,
                'annual_returns': annual_returns,
                'outperform_count': out_count,
                'total_periods': total_p,
                'outperform_rate': rate,
                'period_detail': detail,
                'volatility_class': vc,
                'objective_class': obj_class,
                'objective_text': obj_text,
                'phs_fund_type': phs_fund_type,
                'distribution_policy': metadata.get('distribution_policy', ''),
                'asset_allocation': asset_alloc,
                'geo_breakdown': geo,
                'top5_holdings': holdings,
                'top5_sectors': sectors,
                **{k: v for k, v in metadata.items() if k != 'distribution_policy'},
            }
            all_funds.append(fund_data)

            # Weighted Alpha qualification (v8)
            # Weights: YTD 5%, 1Y 15%, 3Y 40%, 5Y 25%, 10Y 15%
            wa_weights = {'ytd': 0.05, '1-year': 0.15, '3-year': 0.40, '5-year': 0.25, '10-year': 0.15}
            wa_available = {}
            for pk, pw in wa_weights.items():
                pd_entry = detail.get(pk, {})
                alpha_val = pd_entry.get('alpha')
                if alpha_val is not None:
                    wa_available[pk] = (pw, alpha_val)
            if len(wa_available) >= 2:
                total_w = sum(w for w, _ in wa_available.values())
                weighted_alpha = sum((w / total_w) * a for w, a in wa_available.values())
                weighted_alpha = round(weighted_alpha, 4)
            else:
                weighted_alpha = None

            qualifies = weighted_alpha is not None and weighted_alpha > 0 and total_p >= 2
            fund_data['weighted_alpha'] = weighted_alpha
            status = "QUAL" if qualifies else "    "
            h_count = len(holdings)
            s_count = len(sectors)
            wa_str = f"{weighted_alpha:+.2f}" if weighted_alpha is not None else "N/A"
            print(f"  {status} {fund_meta['abbr']:15s} | WA:{wa_str:>7s} | {out_count}/{total_p} | "
                  f"H:{h_count} S:{s_count} | {lc[:40]}")

            if qualifies:
                qualified_funds.append(fund_data)

    return all_funds, qualified_funds


if __name__ == "__main__":
    if not BASE_DIR or not OUT_DIR:
        print("ERROR: Please set BASE_DIR, PHS_DIR, and OUT_DIR at the top of this script.")
        sys.exit(1)

    all_funds, qualified = process_all_mfrs()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(qualified)}/{len(all_funds)} funds qualify (>=60% outperformance)")
    print('='*60)

    # Quick stats
    n_with_holdings = sum(1 for f in all_funds if f['top5_holdings'])
    n_with_sectors = sum(1 for f in all_funds if f['top5_sectors'])
    n_with_geo = sum(1 for f in all_funds if f['geo_breakdown'])
    n_with_alloc = sum(1 for f in all_funds if f['asset_allocation'])
    n_with_obj = sum(1 for f in all_funds if f['objective_class'])
    print(f"  Holdings: {n_with_holdings}/{len(all_funds)}")
    print(f"  Sectors:  {n_with_sectors}/{len(all_funds)}")
    print(f"  Geo:      {n_with_geo}/{len(all_funds)}")
    print(f"  Alloc:    {n_with_alloc}/{len(all_funds)}")
    print(f"  PHS Obj:  {n_with_obj}/{len(all_funds)}")

    with open(os.path.join(OUT_DIR, "mfr_results.json"), "w") as fp:
        json.dump({'all_funds': all_funds, 'qualified': qualified, 'base_dir': BASE_DIR}, fp, indent=2)

    print(f"\nResults saved to mfr_results.json")
