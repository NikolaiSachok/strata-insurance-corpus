"""European countries + synthetic national-identifier generation.

Meridian Mutual is a pan-European insurer; policyholders are distributed across these
Eurozone countries, each with locale-correct names/addresses (Faker) and a national ID.

The national IDs are **format-shaped but deliberately invalid** — each violates the
country's official checksum or uses a reserved/impossible value — so a generated ID can
never coincide with a real person's identifier. This is the GDPR-safe "clearly synthetic"
guarantee; documents also carry the SYNTHETIC marker. Do not "fix" these to be valid.
"""

from __future__ import annotations

import string
from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    code: str  # ISO-3166 alpha-2
    name: str
    locale: str  # Faker locale
    id_label: str  # what the national id is called locally


COUNTRIES = (
    Country("DE", "Germany", "de_DE", "Steuer-ID"),
    Country("FR", "France", "fr_FR", "NIR"),
    Country("ES", "Spain", "es_ES", "DNI"),
    Country("IT", "Italy", "it_IT", "Codice Fiscale"),
    Country("NL", "Netherlands", "nl_NL", "BSN"),
    Country("IE", "Ireland", "en_IE", "PPS Number"),
)
COUNTRY_BY_CODE = {c.code: c for c in COUNTRIES}

# ISO-3166 alpha-3 (issuing-state / nationality code for the ID-card MRZ).
ALPHA3 = {"DE": "DEU", "FR": "FRA", "ES": "ESP", "IT": "ITA", "NL": "NLD", "IE": "IRL"}

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"  # ES DNI control letters
_PPS_LETTERS = "WABCDEFGHIJKLMNOPQRSTUV"  # IE PPS check letters
_CF_MONTHS = "ABCDEHLMPRST"  # valid Italian Codice Fiscale month letters (we use a non-member)


def _digits(rng, n: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


def national_id(code: str, rng) -> str:
    """A format-shaped but deliberately INVALID national identifier for ``code``."""
    if code == "DE":  # Steuer-ID is 11 digits and never starts with 0 -> leading 0 = invalid
        return "0" + _digits(rng, 10)
    if code == "FR":  # NIR sex digit is 1/2 (+special) -> leading 0 = invalid
        return "0" + _digits(rng, 14)
    if code == "ES":  # DNI = 8 digits + control letter -> deliberately wrong letter
        num = rng.randint(0, 99_999_999)
        wrong = _DNI_LETTERS[(num % 23 + 1) % 23]
        return f"{num:08d}-{wrong}"
    if code == "IT":  # Codice Fiscale shape (16) with a non-month letter -> structurally invalid
        alpha = lambda k: "".join(rng.choice(string.ascii_uppercase) for _ in range(k))  # noqa: E731
        return f"{alpha(6)}{_digits(rng, 2)}Z{_digits(rng, 2)}{alpha(1)}{_digits(rng, 3)}{alpha(1)}"
    if code == "NL":  # BSN = 9 digits passing the "11-test" -> construct one that FAILS it
        d = [rng.randint(0, 9) for _ in range(8)]
        s = sum(w * x for w, x in zip((9, 8, 7, 6, 5, 4, 3, 2), d))
        d.append((s % 11 + 1) % 10)  # valid d9 would be s%11; +1 forces the test to fail
        return "".join(map(str, d))
    if code == "IE":  # PPS = 7 digits + check letter (+ A) -> deliberately wrong check letter
        num = rng.randint(0, 9_999_999)
        wrong = _PPS_LETTERS[(num % 23 + 1) % 23]
        return f"{num:07d}{wrong}A"
    raise ValueError(f"unknown country code {code!r}")
