"""
v5 FRED Client — delegates to v4 implementation.
v4 fred_client.py is battle-tested and API-stable.
"""

from ..v4.fred_client import (
    get_msa_economics,
    get_county_demographics,
    _lookup_msa,
    _normalize_city,
)
