PERMISSIONS = {
    "customer_ai": {
        "read": ["users", "orders", "tickets"],
        "write": ["tickets.status", "users.email"],
    },
    "agent_assist": {
        "read": ["users", "orders", "tickets"],
        "write": ["tickets.status", "tickets.assigned_to", "orders.status", "users.email"],
    },
}


def get_write_permissions(role: str) -> list[str]:
    """Return the list of writable table.column paths for a given role."""
    return PERMISSIONS.get(role, {}).get("write", [])


def can_write(role: str, table: str, column: str) -> bool:
    """Check if a role has write access to a specific table.column."""
    allowed = get_write_permissions(role)
    return f"{table}.{column}" in allowed


def can_read(role: str, table: str) -> bool:
    """Check if a role has read access to a specific table."""
    allowed = PERMISSIONS.get(role, {}).get("read", [])
    return table in allowed
