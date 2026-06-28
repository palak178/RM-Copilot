"""Money helpers. All monetary values in the system are integer paise."""


def to_paise(rupees: float) -> int:
    """Convert a rupee amount to integer paise (banker-safe rounding to nearest paisa)."""
    return round(rupees * 100)


def format_inr(paise: int) -> str:
    """Format paise as a short Indian-currency string (e.g. ₹8.20L, ₹1.50Cr, ₹12.4K)."""
    rupees = paise / 100
    magnitude = abs(rupees)
    if magnitude >= 1_00_00_000:
        return f"₹{rupees / 1_00_00_000:.2f}Cr"
    if magnitude >= 1_00_000:
        return f"₹{rupees / 1_00_000:.2f}L"
    if magnitude >= 1_000:
        return f"₹{rupees / 1_000:.1f}K"
    return f"₹{rupees:.0f}"
