"""Country for a port.

The `schedule` table has 15 columns and none of them is `country`, but the
finder filters by country and the CSV export has a Country column — so it has to
come from somewhere. It is derived here rather than stored, which keeps the
table exactly as specified.

The derivation is the UN/LOCODE rule, not a guess: a LOCODE is a 2-letter ISO
3166-1 country code followed by a 3-letter location code, so NLRTM is
Netherlands/Rotterdam and INNSA is India/Nhava Sheva. That holds for every code
the scrapers produce.

PROVISIONAL: reference/Code.gs has still not been supplied, so how the Apps
Script version gets its country is unknown. If it uses a lookup table, replace
this module with it — the finder only calls country_for_port() and
country_options(), so the swap is contained.
"""

from __future__ import annotations

#: ISO 3166-1 alpha-2 -> the name the team would recognise. Covers the lanes we
#: actually sail; anything missing falls back to the code itself, which is
#: visibly odd in the dropdown rather than silently wrong.
ISO_COUNTRIES: dict[str, str] = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AU": "Australia",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BH": "Bahrain",
    "BR": "Brazil",
    "CA": "Canada",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "DE": "Germany",
    "DK": "Denmark",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EG": "Egypt",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HK": "Hong Kong",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IT": "Italy",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KR": "South Korea",
    "KW": "Kuwait",
    "LB": "Lebanon",
    "LK": "Sri Lanka",
    "MA": "Morocco",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "TH": "Thailand",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "US": "United States",
    "VN": "Vietnam",
    "YE": "Yemen",
    "ZA": "South Africa",
}

#: Ports whose LOCODE prefix does not give the answer we want. Empty for now;
#: kept so an exception can be added without touching the rule above.
PORT_OVERRIDES: dict[str, str] = {}


def country_for_port(pod_code: str | None) -> str:
    """Country name for a POD code, or '' when it cannot be worked out."""
    code = (pod_code or "").strip().upper()
    if not code:
        return ""
    if code in PORT_OVERRIDES:
        return PORT_OVERRIDES[code]
    if len(code) < 2:
        return ""
    return ISO_COUNTRIES.get(code[:2], code[:2])


def iso_for_country(country: str) -> str:
    """Reverse lookup, so a country filter becomes a LOCODE prefix in SQL."""
    wanted = (country or "").strip().casefold()
    if not wanted:
        return ""
    for iso, name in ISO_COUNTRIES.items():
        if name.casefold() == wanted:
            return iso
    # A country the map does not know shows up as its own ISO code.
    return wanted.upper() if len(wanted) == 2 else ""


def country_options(pod_codes) -> list[str]:
    """Sorted, de-duplicated country names for the dropdown."""
    return sorted({c for c in (country_for_port(p) for p in pod_codes) if c})
