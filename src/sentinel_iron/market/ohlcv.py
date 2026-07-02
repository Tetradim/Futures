from __future__ import annotations

from decimal import Decimal, InvalidOperation


def decode_optional_integral_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None

    try:
        decimal_value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc

    if not decimal_value.is_finite() or decimal_value != decimal_value.to_integral_value():
        raise ValueError(f"{field_name} must be an integer")

    return int(decimal_value)
