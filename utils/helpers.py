"""
Helper utilities for common operations.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string."""
    if not dt:
        return ""
    return dt.strftime(format_str)


def parse_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """Parse string to datetime."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, format_str)
    except ValueError:
        return None


def format_number(number: int or float, decimals: int = 2) -> str:
    """Format number with thousands separator."""
    if isinstance(number, float):
        return f"{number:,.{decimals}f}"
    return f"{number:,}"


def format_currency(amount: float, currency: str = "$") -> str:
    """Format number as currency."""
    return f"{currency}{amount:,.2f}"


def calculate_percentage(value: int, total: int) -> float:
    """Calculate percentage."""
    if total == 0:
        return 0.0
    return round((value / total) * 100, 2)


def days_between(date1: datetime, date2: datetime = None) -> int:
    """Calculate days between two dates."""
    if date2 is None:
        date2 = datetime.utcnow()
    return abs((date2 - date1).days)


def get_date_range_last_n_days(n: int) -> tuple:
    """Get date range for last N days."""
    end = datetime.utcnow()
    start = end - timedelta(days=n)
    return start, end


def get_date_range_current_month() -> tuple:
    """Get date range for current month."""
    now = datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def get_date_range_current_year() -> tuple:
    """Get date range for current year."""
    now = datetime.utcnow()
    start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def chunk_list(items: List, chunk_size: int) -> List[List]:
    """Split list into chunks."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """Flatten nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely load JSON string."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely dump object to JSON string."""
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return default


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length."""
    if not s:
        return ""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def generate_id() -> str:
    """Generate unique ID."""
    import uuid
    return str(uuid.uuid4())


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def is_valid_json(json_str: str) -> bool:
    """Check if string is valid JSON."""
    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def remove_none_values(d: Dict) -> Dict:
    """Remove None values from dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def batch_process(items: List, process_func: callable, batch_size: int = 100) -> List:
    """Process items in batches."""
    results = []
    for batch in chunk_list(items, batch_size):
        results.extend(process_func(batch))
    return results


def retry_on_failure(func: callable, max_retries: int = 3, delay: float = 1.0) -> Any:
    """Retry function on failure."""
    import time
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(delay)

    raise last_exception
