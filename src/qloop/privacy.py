"""Redaction before anything leaves the process: traces and datasets come from privileged legal material, so client
names, email addresses, IBANs and phone numbers are replaced by stable pseudonyms (the same value always gets the same
token, so traces stay joinable without the value)."""

from __future__ import annotations

import hashlib
import hmac
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[0-9A-Z]{4}){3,7}(?:\s?[0-9A-Z]{1,3})?\b")
PHONE = re.compile(r"(?<!\w)\+?\d{2,4}[\s/-]?\d{3,4}[\s/-]?\d{3,8}(?!\w)")
ENTITY = re.compile(r"\b([A-ZÄÖÜ][\wäöüß]+(?:\s[A-ZÄÖÜ][\wäöüß]+)*\s(?:GmbH|AG|B\.V\.|SE|KG|N\.V\.))")


class Redactor:
    def __init__(self, key: bytes):
        self.key = key

    def _token(self, kind: str, value: str) -> str:
        return f"<{kind}:{hmac.new(self.key, value.encode(), hashlib.sha256).hexdigest()[:8]}>"

    def text(self, s: str) -> str:
        s = EMAIL.sub(lambda m: self._token("EMAIL", m.group(0)), s)
        s = IBAN.sub(lambda m: self._token("IBAN", m.group(0)), s)
        s = ENTITY.sub(lambda m: self._token("PARTY", m.group(1)), s)
        s = PHONE.sub(lambda m: self._token("PHONE", m.group(0)) if sum(c.isdigit() for c in m.group(0)) >= 9 else m.group(0), s)
        return s

    def value(self, v):
        if isinstance(v, str):
            return self.text(v)
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if isinstance(v, dict):
            return {k: self.value(x) for k, x in v.items()}
        return v
