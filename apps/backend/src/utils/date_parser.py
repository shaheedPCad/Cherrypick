"""Date parsing utilities for resume ingestion.

This module provides robust date parsing for various resume date formats,
handling multiple formats and edge cases like "Present" indicators.
"""

import re
from datetime import date

from dateutil import parser


def parse_resume_date(date_string: str) -> date | None:
    """Parse various resume date formats to Python date objects.

    Supports multiple formats commonly found in resumes:
    - "January 2020", "Jan 2020" (month name + year)
    - "2020-01", "01/2020" (numeric formats)
    - "2020" (year only)
    - "Present", "Current", "Now", "Ongoing" (returns None for current positions)

    Args:
        date_string: Date string from resume text

    Returns:
        date object representing the first day of the month, or None for
        current/present indicators

    Raises:
        ValueError: If the date string cannot be parsed

    Examples:
        >>> parse_resume_date("January 2020")
        date(2020, 1, 1)
        >>> parse_resume_date("Present")
        None
        >>> parse_resume_date("2020-05")
        date(2020, 5, 1)
    """
    if not date_string or not date_string.strip():
        raise ValueError("Date string cannot be empty")

    date_string = date_string.strip()

    # Handle current/present indicators
    present_indicators = ["present", "current", "now", "ongoing", "today"]
    if date_string.lower() in present_indicators:
        return None

    # Strategy 1: Try dateutil parser with fuzzy matching
    # This handles "January 2020", "Jan 2020", etc.
    try:
        parsed = parser.parse(date_string, fuzzy=True)
        return date(parsed.year, parsed.month, 1)
    except (ValueError, parser.ParserError):
        pass

    # Strategy 2: Handle "YYYY-MM" format explicitly
    if re.match(r'^\d{4}-\d{2}$', date_string):
        try:
            year, month = map(int, date_string.split('-'))
            return date(year, month, 1)
        except (ValueError, TypeError):
            pass

    # Strategy 3: Handle "MM/YYYY" format
    mm_yyyy_match = re.match(r'^(\d{1,2})/(\d{4})$', date_string)
    if mm_yyyy_match:
        try:
            month, year = map(int, mm_yyyy_match.groups())
            return date(year, month, 1)
        except (ValueError, TypeError):
            pass

    # Strategy 4: Extract year only as last resort
    year_match = re.search(r'\b(19|20)\d{2}\b', date_string)
    if year_match:
        year = int(year_match.group())
        # Return January 1st of that year
        return date(year, 1, 1)

    # If all strategies fail, raise descriptive error
    raise ValueError(
        f"Cannot parse date: '{date_string}'. Supported formats: "
        f"'Jan 2020', '2020-01', '01/2020', '2020', or 'Present'"
    )
