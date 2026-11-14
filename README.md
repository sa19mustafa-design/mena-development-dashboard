# MENA Development and Governance Dashboard

**Does prosperity bring democracy?** This project tests that question across **21 Middle East and North Africa (MENA) countries from 1990 to 2025**, using **29 indicators** from the World Bank, UNDP, V-Dem and Freedom House.

🔗 **[Interactive Tableau dashboard](https://public.tableau.com/app/profile/mustafa.saqib/viz/MENADevelopmentandGovernanceDashboard)** · **[Full report (PDF)](https://drive.google.com/file/d/1rwwQRjtvw_o3ClhwN2dI2O0l74LQn4hB/view?usp=sharing)** · **[Project page](https://sites.google.com/msqb.net/mustafa-saqib/data-analytics/projects/mena-development-dashboard)**

---

## Key finding

| Relationship (2019–2023 country averages) | Spearman ρ |
|---|---|
| GDP per capita ↔ Human Development Index | **0.92** |
| GDP per capita ↔ Governance quality (WGI) | **≈ 0.7** |
| GDP per capita ↔ Political rights (Freedom House) | **−0.05** |
| GDP per capita ↔ Electoral democracy (V-Dem) | **−0.39** |

Wealth tracks human development and state capacity, but **not democracy**. The negative democracy correlation is driven largely by the Gulf (GCC) monarchies; a robustness check excluding the GCC is included in the report.

## Dashboards

1. **[Regional Overview](https://public.tableau.com/views/MENADevelopmentandGovernanceDashboard/RegionalOverview)**: map and headline indicators across the region
2. **[Economic & Human Development](https://public.tableau.com/views/MENADevelopmentandGovernanceDashboard/2EconomicHumanDevelopment)**: GDP, HDI, schooling, life expectancy
3. **[Political Development](https://public.tableau.com/views/MENADevelopmentandGovernanceDashboard/Dashboard3)**: democracy, rights and governance scores
4. **[Country Profile](https://public.tableau.com/views/MENADevelopmentandGovernanceDashboard/4CountryProfile)**: drill-down for any single country

## Data sources

| Source | Indicators |
|---|---|
| World Bank WDI (API) | GDP, growth, unemployment, inflation, population, life expectancy, schooling, female labor force, Gini, military spending, refugees, IDPs |
| World Bank WGI (API) | Voice & Accountability, Political Stability, Government Effectiveness, Regulatory Quality, Rule of Law, Control of Corruption |
| UNDP Human Development Report | HDI, IHDI, GII, schooling, GNI per capita |
| V-Dem (via Our World in Data) | Electoral Democracy Index |
| Freedom House (via Our World in Data) | Political Rights, Civil Liberties |

**Countries (21):** Algeria, Bahrain, Djibouti, Egypt, Iran, Iraq, Israel, Jordan, Kuwait, Lebanon, Libya, Morocco, Oman, Qatar, Saudi Arabia, Syria, Tunisia, Türkiye, UAE, West Bank and Gaza, Yemen. They're grouped into five subregions (GCC, Levant & Iraq, North Africa, Iran & Türkiye, Yemen & Djibouti).

> Note: West Bank and Gaza has no Freedom House or V-Dem values in this dataset.

## Method

Following the Google Data Analytics framework: **Ask → Prepare → Process → Analyze → Share → Act**.

- **Process:** `build_mena_dataset.py` pulls the World Bank API (with retries and local caching), reshapes the UNDP wide file, merges the OWID files, standardizes country codes and writes tidy outputs.
- **Analyze:** Spearman rank correlations on 2019–2023 country averages, pairwise deletion for missing values, robustness check excluding the GCC.
- **Share:** four Tableau Public dashboards and a 21-page written report.

## Repository structure

```
├── build_mena_dataset.py   # data pipeline (Python / pandas)
├── requirements.txt
├── inputs/                 # UNDP + OWID source files (download separately, see below)
├── data/
│   ├── mena_long.csv       # tidy long format, 17,550 rows
│   ├── mena_wide.csv       # one row per country-year, 756 × 33
│   └── coverage_report.csv # first/last year and data count per indicator
└── report/
    └── MENA_Dashboard_Case_Study.pdf
```

## Reproduce

```bash
pip install -r requirements.txt
# Put the UNDP HDR composite-indices CSV and the OWID CSVs
# (electoral-democracy-index, political-rights-score-fh, civil-liberties-score-fh) in inputs/
python build_mena_dataset.py
# Outputs are written to output/
```

The World Bank data downloads automatically, and the other files are optional. The script skips any source it can't find.

## Tools

Python (pandas, requests) · Tableau Public · Excel · Spearman correlation analysis

## Author

**Mustafa Saqib, LL.M., Ph.D.**: Visiting Scholar, Rutgers University–Camden
[Website](https://sites.google.com/msqb.net/mustafa-saqib) · [Tableau Public](https://public.tableau.com/app/profile/mustafa.saqib)

*Data are © their respective providers and are used under their terms; see each source for licensing.*
