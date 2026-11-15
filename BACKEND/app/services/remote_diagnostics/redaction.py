"""Redact before any result leaves the target computer."""

import re

SENSITIVE = re.compile(
    r"pass(?:word)?|pwd|senha|secret|token|pidkey|serial|authorization|cookie|api[_-]?key|private[_-]?key|credentials?|connection[_-]?string",
    re.IGNORECASE,
)


class Redactor:
    def __init__(self, config):
        self.secrets = sorted(
            {
                str(value)
                for key, value in config.values.items()
                if SENSITIVE.search(key) and value and len(str(value)) >= 4
            },
            key=len,
            reverse=True,
        )

    def text(self, value):
        value = str(value)
        for secret in self.secrets:
            value = value.replace(secret, "[oculto]")
        value = re.sub(
            r"-----BEGIN[^-]*PRIVATE KEY-----.*?-----END[^-]*PRIVATE KEY-----",
            "[chave privada omitida]",
            value,
            flags=re.DOTALL,
        )
        value = re.sub(r"(\w+://)[^\s/@:]+:[^\s/@]+@", r"\1[oculto]@", value)
        value = re.sub(r"(?i)\b(?:bearer|basic)\s+[a-z0-9+/_.=-]+", "[autorização omitida]", value)
        value = re.sub(
            r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "[token omitido]", value
        )
        value = re.sub(
            r"(?i)\b(password|pass|pwd|senha|pidkey|token|secret|serial|access[_-]?key|authorization|cookie)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)",
            r"\1=[oculto]",
            value,
        )
        return value[:2000]

    def clean(self, value, key="", depth=0):
        if SENSITIVE.search(key) and not isinstance(value, bool):
            return "[oculto]"
        if depth > 10:
            return "[limite de detalhes]"
        if isinstance(value, dict):
            return {
                str(name): self.clean(item, str(name), depth + 1)
                for name, item in list(value.items())[:100]
            }
        if isinstance(value, list):
            return [self.clean(item, depth=depth + 1) for item in value[:1000]]
        return self.text(value) if isinstance(value, str) else value
