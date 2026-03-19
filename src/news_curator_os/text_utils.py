from __future__ import annotations

import re

OFFICIAL_KEYWORD_DOMAINS: dict[str, list[str]] = {
    "banco central": ["bcb.gov.br", "fazenda.gov.br", "gov.br"],
    "credito": ["bcb.gov.br", "fazenda.gov.br", "gov.br"],
    "selic": ["bcb.gov.br", "fazenda.gov.br"],
    "pix": ["bcb.gov.br"],
    "ministerio": ["gov.br", "planalto.gov.br", "in.gov.br"],
    "governo": ["gov.br", "planalto.gov.br", "in.gov.br"],
    "decreto": ["planalto.gov.br", "in.gov.br", "gov.br"],
    "portaria": ["in.gov.br", "gov.br"],
    "lei": ["planalto.gov.br", "camara.leg.br", "senado.leg.br"],
    "saude": ["saude.gov.br", "gov.br", "who.int"],
    "vacina": ["saude.gov.br", "gov.br", "who.int", "fda.gov", "cdc.gov"],
    "inflacao": ["ibge.gov.br", "bcb.gov.br"],
    "inflação": ["ibge.gov.br", "bcb.gov.br"],
    "desemprego": ["ibge.gov.br"],
    "eleicao": ["tse.jus.br", "camara.leg.br", "senado.leg.br"],
    "eleição": ["tse.jus.br", "camara.leg.br", "senado.leg.br"],
    "stf": ["stf.jus.br"],
    "cvm": ["cvm.gov.br", "sec.gov"],
    "bitcoin": ["bcb.gov.br", "cvm.gov.br", "sec.gov"],
    "crypto": ["bcb.gov.br", "cvm.gov.br", "sec.gov"],
}

_ENTITY_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ-]{2,}\b")
_TOKEN_PATTERN = re.compile(r"\w+")


def extract_entities(text: str) -> list[str]:
    matches = _ENTITY_PATTERN.findall(text)
    unique: list[str] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
    return unique


def derive_official_domains(headline: str) -> list[str]:
    lowered = headline.casefold()
    domains: list[str] = []
    for keyword, candidates in OFFICIAL_KEYWORD_DOMAINS.items():
        if keyword in lowered:
            for domain in candidates:
                if domain not in domains:
                    domains.append(domain)
    return domains


def tokenize(headline: str, *, min_length: int = 4) -> list[str]:
    return [token for token in _TOKEN_PATTERN.findall(headline) if len(token) >= min_length]
