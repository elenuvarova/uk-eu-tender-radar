"""Common enum values for notice_type, procedure_type, status."""

# notice_type
PLANNING = "PLANNING"
TENDER = "TENDER"
AWARD = "AWARD"
CONTRACT = "CONTRACT"
MODIFICATION = "MODIFICATION"
NOTICE_OTHER = "OTHER"

# procedure_type
OPEN = "OPEN"
SELECTIVE = "SELECTIVE"
LIMITED = "LIMITED"
DIRECT = "DIRECT"
PROC_OTHER = "OTHER"

# status
PLANNED = "PLANNED"
STATUS_OPEN = "OPEN"
CLOSED = "CLOSED"
AWARDED = "AWARDED"
UNSUCCESSFUL = "UNSUCCESSFUL"
CANCELLED = "CANCELLED"
STATUS_OTHER = "OTHER"

# OCDS procurementMethod -> unified procedure_type
_METHOD_MAP = {
    "open": OPEN,
    "selective": SELECTIVE,
    "limited": LIMITED,
    "direct": DIRECT,
}

# OCDS tag -> unified notice_type (first matching tag wins)
_TAG_MAP = {
    "planning": PLANNING,
    "tender": TENDER,
    "tenderUpdate": MODIFICATION,
    "award": AWARD,
    "awardUpdate": MODIFICATION,
    "contract": CONTRACT,
    "contractUpdate": MODIFICATION,
    "implementation": CONTRACT,
    "implementationUpdate": MODIFICATION,
}

# OCDS tenderStatus -> unified status
_TENDER_STATUS_MAP = {
    "planning": PLANNED,
    "planned": PLANNED,
    "active": STATUS_OPEN,
    "cancelled": CANCELLED,
    "unsuccessful": UNSUCCESSFUL,
    "complete": AWARDED,
    "withdrawn": CANCELLED,
}


def map_procedure_type(ocds_method: str | None) -> str:
    return _METHOD_MAP.get((ocds_method or "").lower(), PROC_OTHER)


def map_notice_type(tags: list[str]) -> str:
    for tag in tags or []:
        if tag in _TAG_MAP:
            return _TAG_MAP[tag]
    return NOTICE_OTHER


def map_status(tender_status: str | None) -> str:
    return _TENDER_STATUS_MAP.get((tender_status or "").lower(), STATUS_OTHER)
