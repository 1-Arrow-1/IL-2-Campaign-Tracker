import regex

TRACKER_SECTION_HEADER_PATTERN = (
    r'(?:Mission Debriefings<br>|<[ub]>Mission Debriefings</[ub]>|<[ub]>Events</[ub]>)'
)
TRACKER_SECTION_PATTERN = f"{TRACKER_SECTION_HEADER_PATTERN}[\\s\\S]*$"


def detect_info_locale_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    return "utf-8"


def decode_and_clean_info_locale(raw: bytes) -> tuple[str, str, str]:
    encoding = detect_info_locale_encoding(raw)
    content = raw.decode(encoding)

    cleaned = regex.sub(
        TRACKER_SECTION_PATTERN,
        '',
        content,
        flags=regex.IGNORECASE,
    )

    cleaned = cleaned.rstrip()
    while cleaned.endswith('<br>'):
        cleaned = cleaned[:-4].rstrip()

    return cleaned, encoding, content
