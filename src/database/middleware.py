import re

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Patterns that indicate SQL injection attempts
DANGEROUS_PATTERNS = [
    r";\s*(DROP|DELETE|ALTER|TRUNCATE|INSERT|UPDATE)\s",
    r"--\s*$",
    r"/\*.*\*/",
    r"'\s*OR\s+'1'\s*=\s*'1",
    r"UNION\s+SELECT",
]


def sanitize_input(value: str) -> str:
    """Sanitize user input to prevent SQL injection in dynamic queries."""
    if not isinstance(value, str):
        return value
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(f"Blocked potentially dangerous input: {value[:50]}...")
            raise ValueError("Input contains potentially dangerous SQL patterns.")
    return value.strip()


def validate_column_access(table: str, column: str, allowed_writes: list[str]) -> bool:
    """Check if a write operation is permitted on the given table.column."""
    access_key = f"{table}.{column}"
    return access_key in allowed_writes
