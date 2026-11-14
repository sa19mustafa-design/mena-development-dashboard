"""
MENA Development and Governance Dashboard: master dataset builder
==================================================================
Builds one tidy (long) CSV for Tableau from:
  1. World Bank WDI + Worldwide Governance Indicators  (downloaded automatically)
  2. UNDP HDR composite indices CSV (HDI, IHDI, GII...)  (you download, optional)
  3. Freedom House "All data" Excel file                  (you download, optional)
  4. Our World in Data CSVs (EIU Democracy Index, V-Dem)  (you download, optional)
  5. Any tidy CSV you prepare yourself (e.g. WJP)          (optional)

Output (in ./output):
  mena_long.csv       -> Tableau data source (same columns as before, plus
                         'subregion' and 'dimension')
  mena_wide.csv       -> one row per country-year, one column per indicator
                         (for scatter plots, e.g. GDP per capita vs. HDI)
  coverage_report.csv -> first/last year and number of years per country x indicator

Setup (once):   pip install pandas requests openpyxl
Run:            python build_mena_dataset.py
Put downloaded files in ./inputs  (see INPUT FILES below). Missing files are skipped.
"""

from pathlib import Path
import sys
import time

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
START_YEAR, END_YEAR = 1990, 2025
BASE = Path(__file__).resolve().parent
INPUTS = BASE / "inputs"
OUTPUT = BASE / "output"
CACHE = BASE / "cache"          # raw World Bank downloads, so re-runs are fast

# Country names match your existing mena_long.csv (World Bank spelling).
COUNTRIES = {
    "ARE": "United Arab Emirates", "BHR": "Bahrain", "DJI": "Djibouti",
    "DZA": "Algeria", "EGY": "Egypt, Arab Rep.", "IRN": "Iran, Islamic Rep.",
    "IRQ": "Iraq", "ISR": "Israel", "JOR": "Jordan", "KWT": "Kuwait",
    "LBN": "Lebanon", "LBY": "Libya", "MAR": "Morocco", "OMN": "Oman",
    "PSE": "West Bank and Gaza", "QAT": "Qatar", "SAU": "Saudi Arabia",
    "SYR": "Syrian Arab Republic", "TUN": "Tunisia", "TUR": "Turkiye",
    "YEM": "Yemen, Rep.",
}

SUBREGIONS = {
    "Gulf (GCC)": ["ARE", "BHR", "KWT", "OMN", "QAT", "SAU"],
    "Levant & Iraq": ["IRQ", "ISR", "JOR", "LBN", "PSE", "SYR"],
    "North Africa": ["DZA", "EGY", "LBY", "MAR", "TUN"],
    "Iran & Turkiye": ["IRN", "TUR"],
    "Yemen & Djibouti": ["YEM", "DJI"],
}
SUBREGION_OF = {iso: reg for reg, isos in SUBREGIONS.items() for iso in isos}

# World Bank indicators: code -> (indicator name, dimension, API source id)
# source 2 = World Development Indicators, source 3 = Worldwide Governance Indicators
WB_INDICATORS = {
    # Economic development
    "NY.GDP.MKTP.CD":    ("GDP (current US$)", "Economic", 2),
    "NY.GDP.PCAP.CD":    ("GDP per capita (current US$)", "Economic", 2),
    "NY.GDP.PCAP.PP.CD": ("GDP per capita, PPP (current international $)", "Economic", 2),
    "NY.GDP.MKTP.KD.ZG": ("GDP growth (annual %)", "Economic", 2),
    "SL.UEM.TOTL.ZS":    ("Unemployment (% of labor force, ILO est.)", "Economic", 2),
    "FP.CPI.TOTL.ZG":    ("Inflation, consumer prices (annual %)", "Economic", 2),
    "SP.POP.TOTL":       ("Population, total", "Economic", 2),
    # Human development
    "SP.DYN.LE00.IN":    ("Life expectancy at birth (years)", "Human", 2),
    "SE.SEC.ENRR":       ("School enrollment, secondary (% gross)", "Human", 2),
    # Inequality and gender
    "SL.TLF.CACT.FE.ZS": ("Female labor force participation (% ages 15+, ILO est.)", "Inequality & Gender", 2),
    "SI.POV.GINI":       ("Gini index", "Inequality & Gender", 2),
    # Security and stability
    "MS.MIL.XPND.GD.ZS": ("Military expenditure (% of GDP)", "Security", 2),
    "SM.POP.REFG.OR":    ("Refugees by country of origin", "Security", 2),
    "VC.IDP.TOCV":       ("Internally displaced persons (conflict & violence)", "Security", 2),
    # Political development (Worldwide Governance Indicators)
    "VA.EST": ("WGI: Voice and Accountability", "Political", 3),
    "PV.EST": ("WGI: Political Stability / No Violence", "Political", 3),
    "GE.EST": ("WGI: Government Effectiveness", "Political", 3),
    "RQ.EST": ("WGI: Regulatory Quality", "Political", 3),
    "RL.EST": ("WGI: Rule of Law", "Political", 3),
    "CC.EST": ("WGI: Control of Corruption", "Political", 3),
}

# ---------------------------------------------------------------------------
# INPUT FILES (optional; put them in ./inputs, any file name matching the pattern)
# ---------------------------------------------------------------------------
# UNDP: hdr.undp.org -> Data Center -> Documentation and downloads
#       -> "All composite indices and components time series" (CSV)
UNDP_PATTERN = "*HDR*omposite*.csv"
UNDP_INDICATORS = {   # column prefix in UNDP file -> (name, dimension)
    "hdi":    ("Human Development Index (HDI)", "Human"),
    "le":     ("UNDP life expectancy (years)", "Human"),
    "eys":    ("Expected years of schooling", "Human"),
    "mys":    ("Mean years of schooling", "Human"),
    "gnipc":  ("GNI per capita, PPP (2021 $)", "Human"),
    "ihdi":   ("Inequality-adjusted HDI (IHDI)", "Inequality & Gender"),
    "gii":    ("Gender Inequality Index (GII)", "Inequality & Gender"),
    "lfpr_f": ("UNDP female labor force participation (%)", "Inequality & Gender"),
}

# Freedom House: freedomhouse.org -> Reports -> Freedom in the World
#                -> Data -> "All Data, FIW 2013-20XX" (Excel)
FH_PATTERN = "*FIW*.xlsx"
FH_NAMES = {   # Freedom House spelling -> ISO3 (West Bank used for PSE)
    "Algeria": "DZA", "Bahrain": "BHR", "Djibouti": "DJI", "Egypt": "EGY",
    "Iran": "IRN", "Iraq": "IRQ", "Israel": "ISR", "Jordan": "JOR",
    "Kuwait": "KWT", "Lebanon": "LBN", "Libya": "LBY", "Morocco": "MAR",
    "Oman": "OMN", "Qatar": "QAT", "Saudi Arabia": "SAU", "Syria": "SYR",
    "Tunisia": "TUN", "Turkey": "TUR", "Türkiye": "TUR", "Turkiye": "TUR",
    "United Arab Emirates": "ARE", "Yemen": "YEM", "West Bank": "PSE",
}

# Our World in Data: download the chart's CSV ("Download" -> "Full data (CSV)")
#   ourworldindata.org/grapher/democracy-index-eiu          (EIU Democracy Index)
#   ourworldindata.org/grapher/electoral-democracy-index    (V-Dem, optional)
OWID_FILES = {   # file name in ./inputs -> (indicator name, source, dimension)
    "democracy-index-eiu.csv": ("EIU Democracy Index (0-10)", "EIU via Our World in Data", "Political"),
    "electoral-democracy-index.csv": ("V-Dem Electoral Democracy Index (0-1)", "V-Dem via Our World in Data", "Political"),
}

# Any other source (e.g. WJP Rule of Law Index): prepare a CSV named extra_*.csv
# with columns: iso3, year, indicator, value, source, dimension
EXTRA_PATTERN = "extra_*.csv"

COLUMNS = ["iso3", "country", "subregion", "dimension", "indicator", "source", "year", "value"]


# ---------------------------------------------------------------------------
# STEP 1: World Bank
# ---------------------------------------------------------------------------
def wb_get(url, params, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # network hiccup or API error: wait and retry
            if i == tries - 1:
                raise
            print(f"    retrying ({e})")
            time.sleep(3 * (i + 1))


def parse_wb(payload, code):
    """Turn a World Bank API JSON page into tidy rows."""
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return []
    rows = []
    for rec in payload[1]:
        if rec.get("value") is None:
            continue
        iso = rec.get("countryiso3code") or rec["country"]["id"]
        if iso not in COUNTRIES:
            continue
        rows.append({"iso3": iso, "year": int(rec["date"]), "value": float(rec["value"]), "code": code})
    return rows


def fetch_world_bank():
    CACHE.mkdir(exist_ok=True)
    frames = []
    countries = ";".join(COUNTRIES)
    for code, (name, dim, src) in WB_INDICATORS.items():
        cache_file = CACHE / f"wb_{code}.csv"
        if cache_file.exists():
            df = pd.read_csv(cache_file)
            print(f"  [cache] {name}: {len(df)} rows")
        else:
            # Try the standard code first, then alternatives the API sometimes uses
            # (WGI codes moved to a GOV_WGI_ prefix; some series need no source id).
            attempts = [(code, src), (code, None)]
            if src == 3:
                attempts = [(code, 3), (f"GOV_WGI_{code}", 3), (f"GOV_WGI_{code}", None), (code, None)]
            df, last_err = pd.DataFrame(), "no data returned"
            for try_code, try_src in attempts:
                url = f"https://api.worldbank.org/v2/country/{countries}/indicator/{try_code}"
                params = {"format": "json", "date": f"{START_YEAR}:{END_YEAR}", "per_page": 20000}
                if try_src:
                    params["source"] = try_src
                try:
                    df = pd.DataFrame(parse_wb(wb_get(url, params, tries=2), code))
                except Exception as e:
                    last_err = f"download failed ({e})"
                    continue
                if not df.empty:
                    break
            if df.empty:
                print(f"  [skip]  {name}: {last_err}")
                continue
            df.to_csv(cache_file, index=False)
            print(f"  [ok]    {name}: {len(df)} rows")
        src_name = "World Bank WDI" if src == 2 else "World Bank WGI"
        frames.append(df.assign(indicator=name, dimension=dim, source=src_name))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# STEP 2: Optional files
# ---------------------------------------------------------------------------
def first_match(pattern):
    hits = sorted(INPUTS.glob(pattern))
    return hits[-1] if hits else None


def load_undp():
    path = first_match(UNDP_PATTERN)
    if not path:
        print("  [skip]  UNDP file not found in inputs/")
        return pd.DataFrame()
    raw = pd.read_csv(path, encoding="latin-1")
    raw = raw[raw["iso3"].isin(COUNTRIES)]
    long = raw.melt(id_vars="iso3", var_name="col", value_name="value")
    parts = long["col"].str.extract(r"^(?P<prefix>[a-z_]+?)_(?P<year>\d{4})$")
    long = pd.concat([long, parts], axis=1).dropna(subset=["year"])
    long = long[long["prefix"].isin(UNDP_INDICATORS)]
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    long["year"] = long["year"].astype(int)
    long["indicator"] = long["prefix"].map(lambda p: UNDP_INDICATORS[p][0])
    long["dimension"] = long["prefix"].map(lambda p: UNDP_INDICATORS[p][1])
    long["source"] = "UNDP HDR"
    print(f"  [ok]    UNDP ({path.name}): {len(long)} rows")
    return long[["iso3", "year", "value", "indicator", "dimension", "source"]]


def load_freedom_house():
    path = first_match(FH_PATTERN)
    if not path:
        print("  [skip]  Freedom House file not found in inputs/")
        return pd.DataFrame()
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    for _, sheet in sheets.items():
        hdr = sheet.index[sheet.apply(lambda r: r.astype(str).str.contains("Country/Territory").any(), axis=1)]
        if len(hdr):
            break
    else:
        print("  [skip]  Freedom House: could not find the 'Country/Territory' header")
        return pd.DataFrame()
    df = sheet.iloc[hdr[0] + 1:].copy()
    df.columns = [str(c).strip() for c in sheet.iloc[hdr[0]]]
    df["iso3"] = df["Country/Territory"].astype(str).str.strip().map(FH_NAMES)
    df = df.dropna(subset=["iso3"])
    measures = {"Total": "Freedom House: Total score (0-100)",
                "PR": "Freedom House: Political Rights (0-40)",
                "CL": "Freedom House: Civil Liberties (0-60)"}
    out = []
    for col, name in measures.items():
        if col in df.columns:
            part = df[["iso3", "Edition", col]].rename(columns={"Edition": "year", col: "value"})
            out.append(part.assign(indicator=name))
    out = pd.concat(out)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out = out.dropna(subset=["value", "year"])
    out["year"] = out["year"].astype(int)   # report edition year
    print(f"  [ok]    Freedom House ({path.name}): {len(out)} rows (PSE = West Bank)")
    return out.assign(dimension="Political", source="Freedom House")


def load_owid():
    frames = []
    for fname, (name, source, dim) in OWID_FILES.items():
        path = INPUTS / fname
        if not path.exists():
            print(f"  [skip]  {fname} not found in inputs/")
            continue
        raw = pd.read_csv(path)
        value_col = [c for c in raw.columns if c not in ("Entity", "Code", "Year", "Day")][0]
        df = raw.rename(columns={"Code": "iso3", "Year": "year", value_col: "value"})
        df = df[df["iso3"].isin(COUNTRIES)].dropna(subset=["value"])
        frames.append(df[["iso3", "year", "value"]].assign(indicator=name, source=source, dimension=dim))
        print(f"  [ok]    {fname}: {len(df)} rows")
    return pd.concat(frames) if frames else pd.DataFrame()


def load_extra():
    frames = []
    for path in sorted(INPUTS.glob(EXTRA_PATTERN)):
        df = pd.read_csv(path)
        df = df[df["iso3"].isin(COUNTRIES)]
        frames.append(df[["iso3", "year", "value", "indicator", "source", "dimension"]])
        print(f"  [ok]    {path.name}: {len(df)} rows")
    return pd.concat(frames) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# STEP 3: Combine, check, save
# ---------------------------------------------------------------------------
def main():
    INPUTS.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)

    print("Step 1/3  World Bank")
    parts = [fetch_world_bank()]
    print("Step 2/3  Optional files in inputs/")
    parts += [load_undp(), load_freedom_house(), load_owid(), load_extra()]

    df = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    if df.empty:
        sys.exit("No data collected. Check your internet connection.")

    df["year"] = df["year"].astype(int)
    df = df[df["year"].between(START_YEAR, END_YEAR)]
    df["country"] = df["iso3"].map(COUNTRIES)
    df["subregion"] = df["iso3"].map(SUBREGION_OF)
    df = (df[COLUMNS]
          .drop_duplicates(["iso3", "indicator", "year"], keep="last")
          .sort_values(["dimension", "indicator", "country", "year"]))

    print("Step 3/3  Saving")
    df.to_csv(OUTPUT / "mena_long.csv", index=False)

    wide = df.pivot_table(index=["iso3", "country", "subregion", "year"],
                          columns="indicator", values="value").reset_index()
    wide.to_csv(OUTPUT / "mena_wide.csv", index=False)

    cov = (df.groupby(["dimension", "indicator", "country"])["year"]
             .agg(first_year="min", last_year="max", years_of_data="count").reset_index())
    cov.to_csv(OUTPUT / "coverage_report.csv", index=False)

    print(f"\nDone: {len(df):,} rows, {df['indicator'].nunique()} indicators, "
          f"{df['iso3'].nunique()} countries -> {OUTPUT}")
    gaps = cov[cov["last_year"] < END_YEAR - 3]
    if not gaps.empty:
        print(f"Note: {len(gaps)} country-indicator pairs end before {END_YEAR - 3} "
              f"(see coverage_report.csv).")


if __name__ == "__main__":
    main()
