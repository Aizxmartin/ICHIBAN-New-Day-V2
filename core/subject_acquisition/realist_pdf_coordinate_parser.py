from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import re


@dataclass
class RealistSubjectFacts:
    """
    Normalized subject facts extracted from a Realist/CoreLogic PDF.

    This parser is intentionally conservative:
    - Extracts values that are directly visible in the PDF text layer.
    - Leaves uncertain values blank rather than guessing.
    - Supports RealAVM labels that include the trademark symbol.
    """

    source: str = "realist_corelogic"

    full_address: Optional[str] = None
    county: Optional[str] = None
    apn: Optional[str] = None
    clip: Optional[str] = None
    schedule_number: Optional[str] = None

    sale_price: Optional[int] = None
    sale_date: Optional[str] = None
    price_per_sqft_finished: Optional[float] = None

    building_sqft: Optional[int] = None
    lot_sqft: Optional[int] = None
    lot_acres: Optional[float] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    land_use_county: Optional[str] = None
    land_use_corelogic: Optional[str] = None

    beds: Optional[float] = None
    full_baths: Optional[float] = None
    half_baths: Optional[float] = None
    total_baths: Optional[float] = None
    total_rooms: Optional[int] = None

    building_sqft_above_ground: Optional[int] = None
    basement_sqft: Optional[int] = None
    finished_basement_sqft: Optional[int] = None
    unfinished_basement_sqft: Optional[int] = None
    total_building_sqft: Optional[int] = None
    finished_building_sqft: Optional[int] = None

    heat_type: Optional[str] = None
    roof_material: Optional[str] = None
    exterior: Optional[str] = None
    buildings_count: Optional[int] = None

    owner_name: Optional[str] = None
    owner_name_2: Optional[str] = None
    owner_occupied: Optional[str] = None

    property_zip: Optional[str] = None
    neighborhood_code: Optional[str] = None
    neighborhood_name: Optional[str] = None
    school_district: Optional[str] = None
    elementary_school: Optional[str] = None
    middle_school: Optional[str] = None
    high_school: Optional[str] = None
    subdivision: Optional[str] = None
    zoning: Optional[str] = None
    block: Optional[str] = None
    lot: Optional[str] = None

    market_value_land: Optional[int] = None
    market_value_improved: Optional[int] = None
    market_value_total: Optional[int] = None
    assessed_value_land: Optional[int] = None
    assessed_value_improved: Optional[int] = None
    assessed_value_total: Optional[int] = None
    latest_tax_year: Optional[int] = None
    latest_tax_amount: Optional[int] = None

    sell_score_rating: Optional[str] = None
    sell_score: Optional[int] = None

    real_avm: Optional[int] = None
    real_avm_low: Optional[int] = None
    real_avm_high: Optional[int] = None
    real_avm_confidence_score: Optional[int] = None
    real_avm_forecast_standard_deviation: Optional[int] = None
    real_avm_value_as_of: Optional[str] = None

    confidence: str = "low"
    warnings: List[str] = field(default_factory=list)
    raw_text_sample: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_realist_subject(file_path: str | Path) -> RealistSubjectFacts:
    """
    Parse a Realist/CoreLogic PDF after diagnostics recommend:
        realist_pdf_coordinate_parser
    """

    path = Path(file_path)
    facts = RealistSubjectFacts()

    if not path.exists():
        facts.warnings.append("File does not exist.")
        return facts

    text = _extract_pdf_text(path)
    clean = _clean_text(text)
    facts.raw_text_sample = clean[:3000]

    if not clean:
        facts.warnings.append("No extractable text found.")
        return facts

    _parse_header(clean, facts)
    _parse_summary_row(clean, facts)
    _parse_owner_info(clean, facts)
    _parse_location_info(clean, facts)
    _parse_tax_info(clean, facts)
    _parse_assessment_values(clean, facts)
    _parse_characteristics(clean, facts)
    _parse_sell_score(clean, facts)
    _parse_avm_fields(clean, facts)
    _parse_sales_history(clean, facts)

    _reconcile_bath_count(facts)

    facts.confidence = _score_confidence(facts)
    _add_missing_core_warnings(facts)

    return facts


def _extract_pdf_text(path: Path) -> str:
    """
    Extract text from a Realist/CoreLogic PDF.

    Some Realist PDFs expose useful words through pdfplumber/coordinate text even
    when pypdf is unavailable or returns weak plain text. This function tries pypdf
    first, then falls back to pdfplumber.
    """

    parts: List[str] = []

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))

        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
    except Exception:
        pass

    text = "\n".join(parts).strip()

    if len(text) >= 50:
        return text

    plumber_parts: List[str] = []

    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                try:
                    page_text = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=3,
                        layout=False,
                    ) or ""

                    if page_text.strip():
                        plumber_parts.append(page_text)
                        continue

                    words = page.extract_words(
                        x_tolerance=2,
                        y_tolerance=3,
                        keep_blank_chars=False,
                        use_text_flow=False,
                    )

                    word_text = " ".join(
                        word.get("text", "")
                        for word in words
                        if word.get("text")
                    )

                    if word_text.strip():
                        plumber_parts.append(word_text)

                except Exception:
                    continue
    except Exception:
        pass

    fallback_text = "\n".join(plumber_parts).strip()

    if fallback_text:
        return fallback_text

    return text


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2122", "™")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()


def _parse_header(text: str, facts: RealistSubjectFacts) -> None:
    m = re.search(
        r"^(?P<address>.+?),\s*(?P<county>[A-Za-z &]+ County)\s+APN:\s*(?P<apn>[A-Za-z0-9\-]+)",
        text,
        flags=re.IGNORECASE,
    )

    if m:
        facts.full_address = _clean_value(m.group("address"))
        facts.county = _clean_value(m.group("county"))
        facts.apn = _clean_value(m.group("apn"))

    facts.clip = _extract_text_between(
        text,
        "CLIP:",
        ["Beds", "Full Baths", "Sale Price"],
    )


def _parse_summary_row(text: str, facts: RealistSubjectFacts) -> None:
    facts.beds = _extract_float_after_label(text, "Beds")
    facts.full_baths = _extract_float_after_label(text, "Full Baths")
    facts.half_baths = _extract_float_after_label(text, "Half Baths")

    facts.sale_price = _extract_money_after_label(text, "Sale Price")
    facts.sale_date = _extract_date_after_label(text, "Sale Date")
    facts.building_sqft = _extract_int_after_label(text, "Bldg Sq Ft")
    facts.lot_sqft = _extract_int_after_label(text, "Lot Sq Ft")
    facts.year_built = _extract_year_after_label(text, "Yr Built")

    prop_type = _extract_text_between(
        text,
        "Type",
        ["OWNER INFORMATION", "Owner Name", "COMMUNITY INSIGHTS"],
    )

    if prop_type:
        facts.property_type = prop_type.strip().split()[0]


def _parse_owner_info(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(
        text,
        "OWNER INFORMATION",
        ["COMMUNITY INSIGHTS", "LOCATION INFORMATION"],
    )

    if not section:
        return

    facts.owner_name = _extract_text_between(
        section,
        "Owner Name",
        ["Mailing ZIP", "Owner Name 2", "Mailing Address"],
    )

    facts.owner_name_2 = _extract_text_between(
        section,
        "Owner Name 2",
        ["Mailing Carrier Route", "Mailing Address", "Owner Occupied"],
    )

    facts.owner_occupied = _extract_text_between(
        section,
        "Owner Occupied",
        ["Mailing City", "DMA", "Mail Flag"],
    )


def _parse_location_info(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(
        text,
        "LOCATION INFORMATION",
        ["TAX INFORMATION", "ASSESSMENT", "BUILDING INFORMATION", "CHARACTERISTICS"],
    )

    if not section:
        return

    facts.property_zip = _extract_text_between(
        section,
        "Property Zip",
        ["Topography", "Property Zip4"],
    )

    facts.neighborhood_code = _extract_text_between(
        section,
        "Neighborhood Code",
        ["Property Carrier Route", "Neighborhood Name"],
    )

    facts.neighborhood_name = _extract_text_between(
        section,
        "Neighborhood Name (OnBoard)",
        ["School District", "Traffic"],
    )

    facts.school_district = _extract_text_between(
        section,
        "School District",
        ["Traffic", "Elementary School"],
    )

    facts.elementary_school = _extract_text_between(
        section,
        "Elementary School",
        ["Township", "Middle School"],
    )

    facts.middle_school = _extract_text_between(
        section,
        "Middle School",
        ["Range", "High School"],
    )

    facts.high_school = _extract_text_between(
        section,
        "High School",
        ["Section", "Subdivision"],
    )

    facts.subdivision = _extract_text_between(
        section,
        "Subdivision",
        ["Quarter", "Zoning", "Block"],
    )

    facts.zoning = _extract_text_between(
        section,
        "Zoning",
        ["Block", "Census Tract"],
    )

    facts.block = _extract_text_between(
        section,
        "Block",
        ["Census Tract", "Lot", "Condo Floor"],
    )

    lot_match = re.search(
        r"\bLot\s+([A-Za-z0-9\-]+)\s+(?:Condo Floor|Within|Location Influence)",
        section,
        flags=re.IGNORECASE,
    )

    if lot_match:
        facts.lot = lot_match.group(1).strip()


def _parse_tax_info(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(
        text,
        "TAX INFORMATION",
        ["ASSESSMENT & TAX", "ASSESSMENT", "CHARACTERISTICS"],
    )

    if not section:
        return

    schedule = _extract_text_between(
        section,
        "Schedule Number",
        ["Homestead", "Tax", "Tax Year", "Assessed", "Appraised", "Market", "% Improved"],
    )

    if schedule:
        facts.schedule_number = schedule.strip().split()[0]


def _parse_assessment_values(text: str, facts: RealistSubjectFacts) -> None:
    """
    Extract the newest/leftmost assessment values.
    In this Realist format, the first dollar amount after each label is the current/preliminary year.
    """

    section = _section(
        text,
        "ASSESSMENT & TAX",
        ["CHARACTERISTICS", "Lot Frontage", "SELL SCORE"],
    )

    if not section:
        return

    facts.market_value_land = _extract_first_money_in_row(section, "Market Value - Land")
    facts.market_value_improved = _extract_first_money_in_row(section, "Market Value - Improved")
    facts.market_value_total = _extract_first_money_in_row(section, "Market Value - Total")

    facts.assessed_value_land = _extract_first_money_in_row(section, "Assessed Value - Land")
    facts.assessed_value_improved = _extract_first_money_in_row(section, "Assessed Value - Improved")
    facts.assessed_value_total = _extract_first_money_in_row(section, "Assessed Value - Total")

    tax_rows = re.findall(r"\b(20[0-9]{2})\s+\$([0-9,]+)", section)

    if tax_rows:
        year, amount = tax_rows[-1]
        facts.latest_tax_year = int(year)
        facts.latest_tax_amount = _to_int(amount)


def _parse_characteristics(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(
        text,
        "CHARACTERISTICS",
        ["FEATURES", "SELL SCORE", "ESTIMATED VALUE"],
    )

    if not section:
        return

    facts.lot_acres = _extract_float_after_label(section, "Lot Acres")

    facts.land_use_county = _extract_text_between(
        section,
        "Land Use - County",
        ["Land Use - CoreLogic", "Building Type"],
    )

    facts.land_use_corelogic = _extract_text_between(
        section,
        "Land Use - CoreLogic",
        ["Building Type", "Style", "Year Built"],
    )

    facts.building_sqft_above_ground = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Above Ground",
    )

    facts.basement_sqft = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Basement",
    )

    facts.finished_basement_sqft = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Finished Basement",
    )

    facts.unfinished_basement_sqft = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Unfinished Basement",
    )

    facts.total_building_sqft = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Total",
    )

    facts.finished_building_sqft = _extract_int_after_label(
        section,
        "Bldg Sq Ft - Finished",
    )

    facts.heat_type = _extract_text_between(
        section,
        "Heat Type",
        ["Patio Type", "Garage Type", "Roof Material"],
    )

    facts.roof_material = _extract_text_between(
        section,
        "Roof Material",
        ["Construction", "Exterior", "Floor Cover"],
    )

    facts.exterior = _extract_text_between(
        section,
        "Exterior",
        ["Floor Cover", "Foundation", "Pool"],
    )

    facts.buildings_count = _extract_int_after_label(section, "# Buildings")
    facts.total_rooms = _extract_int_after_label(section, "Total Rooms")

    if facts.beds is None:
        facts.beds = _extract_float_after_label(section, "Bedrooms")

    facts.total_baths = _extract_float_after_label(section, "Baths - Total")


def _parse_sell_score(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(text, "SELL SCORE", ["ESTIMATED VALUE", "LISTING INFORMATION"])

    if not section:
        return

    facts.sell_score_rating = _extract_text_between(
        section,
        "Rating",
        ["Value As Of", "Sell Score"],
    )

    facts.sell_score = _extract_int_after_label(section, "Sell Score")


def _parse_avm_fields(text: str, facts: RealistSubjectFacts) -> None:
    """
    Realist prints values like:
        RealAVM™ $783,200
        RealAVM™ Range $718,100 - $848,400

    The trademark symbol appears between the label and the value, so a simple
    "RealAVM <money>" regex can fail.
    """

    section = _section(
        text,
        "ESTIMATED VALUE",
        ["LISTING INFORMATION", "LAST MARKET SALE", "MORTGAGE HISTORY"],
    )

    if not section:
        section = text

    avm_label = r"Real\s*AVM|RealAVM"
    tm = r"(?:\s*[™®]|(?:\s*\(TM\))|(?:\s*TM))?"

    m = re.search(
        rf"(?:{avm_label}){tm}\s+\$?\s*([0-9][0-9,]*)\b(?!\s*[-–])",
        section,
        flags=re.IGNORECASE,
    )

    if m:
        facts.real_avm = _to_int(m.group(1))

    r = re.search(
        rf"(?:{avm_label}){tm}\s+Range\s+\$?\s*([0-9][0-9,]*)\s*[-–]\s*\$?\s*([0-9][0-9,]*)",
        section,
        flags=re.IGNORECASE,
    )

    if r:
        facts.real_avm_low = _to_int(r.group(1))
        facts.real_avm_high = _to_int(r.group(2))

    facts.real_avm_confidence_score = _extract_int_after_label(
        section,
        "Confidence Score",
    )

    facts.real_avm_forecast_standard_deviation = _extract_int_after_label(
        section,
        "Forecast Standard Deviation",
    )

    facts.real_avm_value_as_of = _extract_date_after_label(
        section,
        "Value As Of",
    )


def _parse_sales_history(text: str, facts: RealistSubjectFacts) -> None:
    section = _section(
        text,
        "LAST MARKET SALE & SALES HISTORY",
        ["MORTGAGE HISTORY", "PROPERTY MAP"],
    )

    if not section:
        return

    m = re.search(
        r"Price per SqFt - Finished\s+\$?([0-9]+(?:\.[0-9]+)?)",
        section,
        flags=re.IGNORECASE,
    )

    if m:
        facts.price_per_sqft_finished = float(m.group(1))


def _reconcile_bath_count(facts: RealistSubjectFacts) -> None:
    """
    Prefer explicit Baths - Total from the characteristics section.
    If it is missing, compute full baths + half baths.
    """

    if facts.total_baths is not None:
        return

    if facts.full_baths is None:
        return

    half_baths = facts.half_baths or 0
    facts.total_baths = float(facts.full_baths) + (float(half_baths) * 0.5)


def _section(text: str, start_label: str, end_labels: List[str]) -> str:
    start = re.search(re.escape(start_label), text, flags=re.IGNORECASE)

    if not start:
        return ""

    tail = text[start.end():]
    end_positions = []

    for label in end_labels:
        m = re.search(re.escape(label), tail, flags=re.IGNORECASE)
        if m:
            end_positions.append(m.start())

    return tail[:min(end_positions)].strip() if end_positions else tail.strip()


def _extract_text_between(
    text: str,
    start_label: str,
    end_labels: List[str],
) -> Optional[str]:
    start = re.search(re.escape(start_label), text, flags=re.IGNORECASE)

    if not start:
        return None

    tail = text[start.end():].strip()
    end_positions = []

    for label in end_labels:
        m = re.search(re.escape(label), tail, flags=re.IGNORECASE)
        if m:
            end_positions.append(m.start())

    value = tail[:min(end_positions)].strip() if end_positions else tail[:100].strip()
    value = _clean_value(value)

    return value or None


def _extract_int_after_label(text: str, label: str) -> Optional[int]:
    m = re.search(
        re.escape(label) + r"\s+([0-9][0-9,]*)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not m:
        return None

    return _to_int(m.group(1))


def _extract_float_after_label(text: str, label: str) -> Optional[float]:
    m = re.search(
        re.escape(label) + r"\s+([0-9]+(?:\.[0-9]+)?)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not m:
        return None

    return float(m.group(1))


def _extract_money_after_label(text: str, label: str) -> Optional[int]:
    m = re.search(
        re.escape(label) + r"\s+\$?\s*([0-9][0-9,]*)",
        text,
        flags=re.IGNORECASE,
    )

    if not m:
        return None

    return _to_int(m.group(1))


def _extract_first_money_in_row(text: str, label: str) -> Optional[int]:
    m = re.search(
        re.escape(label) + r"\s+\$?\s*([0-9][0-9,]*)",
        text,
        flags=re.IGNORECASE,
    )

    if not m:
        return None

    return _to_int(m.group(1))


def _extract_date_after_label(text: str, label: str) -> Optional[str]:
    m = re.search(
        re.escape(label) + r"\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
        text,
        flags=re.IGNORECASE,
    )

    return m.group(1) if m else None


def _extract_year_after_label(text: str, label: str) -> Optional[int]:
    m = re.search(
        re.escape(label) + r"\s+([12][0-9]{3})",
        text,
        flags=re.IGNORECASE,
    )

    return int(m.group(1)) if m else None


def _to_int(value: str) -> Optional[int]:
    if value is None:
        return None

    digits = re.sub(r"[^0-9]", "", str(value))

    return int(digits) if digits else None


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    value = value.strip(" :-")

    if value.upper() in {"N/A", "NA", "NONE"}:
        return ""

    return value


def _score_confidence(facts: RealistSubjectFacts) -> str:
    core_fields = [
        facts.full_address,
        facts.apn,
        facts.building_sqft,
        facts.lot_sqft,
        facts.year_built,
        facts.property_type,
    ]

    found = sum(1 for field in core_fields if field not in (None, ""))

    if found >= 5:
        return "high"

    if found >= 3:
        return "medium"

    return "low"


def _add_missing_core_warnings(facts: RealistSubjectFacts) -> None:
    required = {
        "full_address": facts.full_address,
        "apn": facts.apn,
        "building_sqft": facts.building_sqft,
        "year_built": facts.year_built,
        "property_type": facts.property_type,
    }

    for label, value in required.items():
        if value in (None, ""):
            facts.warnings.append(f"Missing core field: {label}")