import re
from langsmith import traceable
from typing import Optional


class InputSanitizer:
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions\s*:",
        r"system\s*prompt",
        r"developer\s*prompt",
        r"hidden\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
        r"override\s+(all\s+)?instructions",
        r"disregard\s+(all\s+)?instructions",
        r"reveal\s+(your|the)\s+(system|instructions|prompt)",
        r"show\s+(me\s+)?(your|the)\s+(prompt|instructions)",
        r"print\s+(your|the)\s+(prompt|instructions)",
        r"you\s+are\s+now\s+(DAN|jailbroken)",
        r"simulate\s+developer\s+mode",
        r"enable\s+developer\s+mode",
        r"ignore\s+safety",
        r"disable\s+safety",
        r"remove\s+guardrails",
    ]
    
    def __init__(self, query: str):
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]

    def check_for_injection(self, query: str) -> tuple[bool, Optional[str]]:
        for pattern in self.patterns:
            if pattern.search(query):
                return True, f"Potential prompt injection detected: '{pattern.pattern}'"
        return False, None

    def clean_input(self, query: str) -> str:
        query = re.sub(r"[-]{3,}", "", query)  # Remove sequences of 3 or more dashes
        query = re.sub(r"[=]{3,}", "", query)  # Remove sequences of 3 or more dashes
        query = query.replace(r"{{", "{ {").replace(r"}}", "} }")  # Add space between double curly braces
        return query.strip()


class PIIDetector:
    PATTERNS = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    }

    MASK_MAP = {
        "email": "[REDACTED_EMAIL]",
        "phone": "[REDACTED_PHONE]",
        "ssn": "[REDACTED_SSN]",
        "credit_card": "[REDACTED_CREDIT_CARD]",
    }

    def __init__(self):
        self.patterns = {key: re.compile(pattern, re.IGNORECASE) for key, pattern in self.PATTERNS.items()}

    def detect_pii(self, query: str) -> dict[str, list[str]]:
        detected = {}
        for key, pattern in self.patterns.items():
            matches = pattern.findall(query)
            if matches:
                detected[key] = matches
        return detected

    def clean_input(self, query: str) -> str:
        for key, pattern in self.patterns.items():
            query = pattern.sub(self.MASK_MAP.get(key, "[REDACTED]"), query)
        return query.strip()


class OutputValidator:
    """Validates and sanitizes model outputs to prevent harmful content and protect PII."""

    HARMFUL_PATTERNS = [
        re.compile(r"here('s| is) (how|the way) to (hack|steal|attack)", re.I),
        re.compile(r"password\s+is\s+", re.I),
        re.compile(r"api[_\s]?key\s*[:=]", re.I),
    ]

    def __init__(self):
        self.patterns = self.HARMFUL_PATTERNS
        self.pii_detector = PIIDetector()

    def clean_output(self, response: str) -> tuple[str, list[str]]:
        warnings = []

        # check for PII in the response and mask it if found
        pii_found = self.pii_detector.detect_pii(response)
        if pii_found:
            response = self.pii_detector.clean_input(response)
            warnings.append(f"PII detected: {', '.join(pii_found.keys())}")

        # if response contains harmful content, block the entire response
        for pattern in self.patterns:
            if pattern.search(response):
                response = "[Response blocked due to harmful content]"
                warnings.append("Harmful content detected")
                break

        return response, warnings
