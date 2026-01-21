import re


def safe_campaign_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name)
    return cleaned.strip().replace(" ", "_")
