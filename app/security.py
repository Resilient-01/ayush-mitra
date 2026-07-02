# security.py
"""Security utilities for the AyushMitra ADK agent.

Provides:
- PII scrubbing via regex patterns.
- Simple prompt injection detection (e.g., attempts to hijack the LLM).
- Logging of security events.
"""
import re
import logging
from pathlib import Path

# Configure a dedicated logger
logger = logging.getLogger("security")
logger.setLevel(logging.INFO)
log_file = Path(__file__).parent.parent / "logs" / "security.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
handler = logging.FileHandler(log_file, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Regex patterns for common PII (email, phone, AADHAR, PAN)
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"\b\d{10}\b"),
    "aadhar": re.compile(r"\b\d{12}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}

def scrub_pii(text: str) -> str:
    """Replace detected PII with placeholder tokens.

    Args:
        text: Input string.
    Returns:
        Text with PII masked.
    """
    original = text
    for name, pattern in PII_PATTERNS.items():
        text = pattern.sub(f"<REDACTED_{name.upper()}>", text)
    if text != original:
        logger.info("PII scrubbed in user input.")
    return text

# Simple injection detection – looks for instructions to "ignore" safety or expose internal data
INJECTION_PATTERNS = [
    re.compile(r"ignore safety", re.IGNORECASE),
    re.compile(r"expose internal", re.IGNORECASE),
    re.compile(r"dump.*(environment|variables)", re.IGNORECASE),
]

def detect_injection(text: str) -> bool:
    """Return True if text appears to be a prompt‑injection attempt."""
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            logger.warning("Potential prompt injection detected.")
            return True
    return False

def security_audit(event: str, details: str = "") -> None:
    """Utility to log arbitrary security‑related events."""
    logger.info(f"{event}: {details}")
