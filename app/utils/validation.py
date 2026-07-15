import re
from typing import Optional


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


def normalize_name(value: Optional[str]) -> str:
    cleaned = clean_text(value).lower()

    return " ".join(
        character if character.isalnum() else " "
        for character in cleaned
    ).split()


def normalized_name_string(value: Optional[str]) -> str:
    return " ".join(normalize_name(value))


def is_valid_email(value: Optional[str]) -> bool:
    cleaned = clean_text(value)

    if not cleaned:
        return True

    return bool(EMAIL_PATTERN.match(cleaned))


def is_valid_website(value: Optional[str]) -> bool:
    cleaned = clean_text(value)

    if not cleaned:
        return True

    return cleaned.startswith(
        (
            "http://",
            "https://",
            "www.",
        )
    )


def required(value: Optional[str], field_name: str) -> None:
    if not clean_text(value):
        raise ValueError(f"{field_name} is required.")


def validate_score(value: int, field_name: str) -> None:
    if value < 0 or value > 100:
        raise ValueError(
            f"{field_name} must be between 0 and 100."
        )


def validate_positive_number(
    value: Optional[str],
    field_name: str,
) -> None:
    cleaned = clean_text(value)

    if not cleaned:
        raise ValueError(f"{field_name} is required.")

    try:
        number = float(cleaned.replace(",", ""))
    except ValueError as error:
        raise ValueError(
            f"{field_name} must be a valid number."
        ) from error

    if number <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )