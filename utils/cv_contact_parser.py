from __future__ import annotations

import re

# ── Compiled patterns ─────────────────────────────────────────────────────────

_EMAIL_RE  = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_LI_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+", re.I)

# Matches a phone number that is either:
#   - An international number: starts with + and has 10–15 digits total
#   - A local 10-digit number (e.g. 0416982187 or 04 1698 2187)
#   - A number with extension, e.g. +1 800 555 0100 ext. 42
_PHONE_RE = re.compile(
    r"(?:"
    r"\+\d[\d\s\-().]{8,14}"   # international: + then 9–14 more digit/space/dash chars
    r"|"
    r"\b0\d[\d\s\-]{7,11}"     # local starting with 0 (e.g. Australian mobiles 04xxxxxxxx)
    r"|"
    r"\b\d{3}[\s\-.]?\d{3}[\s\-.]?\d{4}\b"   # 10-digit: 555-867-5309 / (555) 867 5309
    r")"
    r"(?:\s*(?:ext|x|ext\.)\s*\d{1,5})?"   # optional extension
)

# Labels that introduce a field value (case-insensitive, colon optional)
_PHONE_LABELS   = re.compile(r"^(?:phone|tel|telephone|mobile|mob|cell)\s*:?\s*", re.I)
_EMAIL_LABELS   = re.compile(r"^(?:email|e-mail|mail)\s*:?\s*", re.I)
_ADDR_LABELS    = re.compile(r"^(?:address|location|loc|city)\s*:?\s*", re.I)
_LI_LABELS      = re.compile(r"^(?:linkedin|linked-in|li)\s*:?\s*", re.I)

# Emojis used as field markers
_PHONE_EMOJIS   = {"📞", "📱", "☎"}
_EMAIL_EMOJIS   = {"📧", "✉"}
_ADDR_EMOJIS    = {"🏠", "🏡", "📍", "📌", "🌍", "🌏"}

# Lines that signal the end of a multi-line value
_STOP_PATTERNS  = re.compile(
    r"(?:📞|📱|☎|📧|✉|🏠|🏡|📍|📌|Portfolio|Github|GitHub|#\s|\-{4,}|={4,})",
    re.I,
)

# City/country patterns for address fallback (e.g. "Melbourne, VIC" or "Sydney, NSW, Australia")
_ADDR_RE = re.compile(
    r"^[A-Z][a-zA-Z\s\-]+,\s*[A-Z]{2,}(?:,\s*[A-Z][a-zA-Z\s]+)?$"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_after(lines: list[str], start: int, max_lines: int = 4) -> list[str]:
    """Collect non-empty, non-stop continuation lines after index start."""
    parts: list[str] = []
    for j in range(start, min(start + max_lines, len(lines))):
        chunk = lines[j].strip()
        if not chunk or _STOP_PATTERNS.search(chunk):
            break
        parts.append(chunk)
    return parts


def _strip_emojis(text: str) -> str:
    return re.sub(r"[^\x00-\x7F📞📱☎📧✉🏠🏡📍📌]", "", text)   # keep ASCII + our markers


def _clean_phone(raw: str) -> str:
    """Join multi-part phone string and normalise."""
    # Remove trailing/leading hyphens from each fragment before joining
    cleaned = " ".join(p.strip().strip("-") for p in raw.split())
    return re.sub(r"\s+", " ", cleaned).strip()


# ── Main parser ────────────────────────────────────────────────────────────────

def parse_contact(cv_text: str) -> dict[str, str]:
    """
    Extract contact fields from a CV markdown string.

    Handles three CV styles in priority order:
      1. Emoji markers  (📞 +61... , 📧 email@..., 🏠 City)
      2. Labelled rows  (Phone: ..., Email: ..., Address: ..., LinkedIn: ...)
      3. Regex fallback (email pattern, phone pattern, city/state pattern)

    Returns a dict with keys: name, email, phone, address, linkedin.
    Any field not found returns an empty string.
    """
    lines = [ln.rstrip() for ln in cv_text.splitlines()]

    result: dict[str, str] = {
        "name":     "",
        "email":    "",
        "phone":    "",
        "address":  "",
        "linkedin": "",
    }

    # ── Name: first level-1 heading ──────────────────────────────────────────
    for line in lines:
        if line.startswith("# "):
            result["name"] = line[2:].strip()
            break

    # ── Single-pass: scan each line for emoji markers OR labels ───────────────
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # ── LinkedIn URL anywhere ─────────────────────────────────────────────
        if not result["linkedin"]:
            m = _LI_URL_RE.search(stripped)
            if m:
                url = m.group().strip()
                result["linkedin"] = url if url.startswith("http") else "https://" + url

        # ── Email ─────────────────────────────────────────────────────────────
        if not result["email"]:
            # Emoji marker
            if any(e in stripped for e in _EMAIL_EMOJIS):
                inline = re.sub(r"[📧✉]", "", stripped).strip()
                candidates = [inline] if inline else _collect_after(lines, i + 1)
                for c in candidates:
                    m = _EMAIL_RE.search(c)
                    if m:
                        result["email"] = m.group()
                        break
            # Label: "Email: foo@bar.com"
            elif _EMAIL_LABELS.match(stripped):
                value = _EMAIL_LABELS.sub("", stripped).strip()
                if not value:
                    value = lines[i + 1].strip() if i + 1 < len(lines) else ""
                m = _EMAIL_RE.search(value)
                if m:
                    result["email"] = m.group()
            # Raw email on the line
            else:
                m = _EMAIL_RE.search(stripped)
                if m:
                    result["email"] = m.group()

        # ── Phone ─────────────────────────────────────────────────────────────
        if not result["phone"]:
            if any(e in stripped for e in _PHONE_EMOJIS):
                inline = re.sub(r"[📞📱☎]", "", stripped).strip()
                parts = [inline] if inline else []
                # Collect continuation lines that look like phone fragments
                for j in range(i + 1, min(i + 5, len(lines))):
                    chunk = lines[j].strip()
                    if not chunk or _STOP_PATTERNS.search(chunk):
                        break
                    if re.search(r"[\d\+]", chunk):
                        parts.append(chunk)
                    else:
                        break
                if parts:
                    result["phone"] = _clean_phone(" ".join(parts))
            elif _PHONE_LABELS.match(stripped):
                value = _PHONE_LABELS.sub("", stripped).strip()
                if not value:
                    value = lines[i + 1].strip() if i + 1 < len(lines) else ""
                result["phone"] = value.strip()

        # ── Address ───────────────────────────────────────────────────────────
        if not result["address"]:
            if any(e in stripped for e in _ADDR_EMOJIS):
                inline = re.sub(r"[🏠🏡📍📌🌍🌏]", "", stripped).strip()
                parts = [inline] if inline else _collect_after(lines, i + 1, max_lines=3)
                if parts:
                    result["address"] = ", ".join(parts)
            elif _ADDR_LABELS.match(stripped):
                value = _ADDR_LABELS.sub("", stripped).strip()
                if not value:
                    value = lines[i + 1].strip() if i + 1 < len(lines) else ""
                result["address"] = value.strip()

        # ── LinkedIn label ────────────────────────────────────────────────────
        if not result["linkedin"] and _LI_LABELS.match(stripped):
            value = _LI_LABELS.sub("", stripped).strip()
            if not value:
                value = lines[i + 1].strip() if i + 1 < len(lines) else ""
            m = _LI_URL_RE.search(value)
            if m:
                url = m.group()
                result["linkedin"] = url if url.startswith("http") else "https://" + url

        i += 1

    # ── Regex fallbacks for anything still missing ────────────────────────────

    if not result["email"]:
        for line in lines:
            m = _EMAIL_RE.search(line)
            if m:
                result["email"] = m.group()
                break

    if not result["phone"]:
        # Find the longest phone-like string to avoid short fragments
        candidates: list[str] = []
        for line in lines:
            for m in _PHONE_RE.finditer(line):
                candidates.append(m.group().strip())
        if candidates:
            result["phone"] = max(candidates, key=len)

    if not result["address"]:
        # Pass 1: whole line matches "City, STATE" or "City, Country"
        for line in lines[:30]:
            if _ADDR_RE.match(line.strip()):
                result["address"] = line.strip()
                break

    if not result["address"]:
        # Pass 2: pipe-separated header lines — split on | and check each segment
        for line in lines[:30]:
            if "|" in line:
                for segment in line.split("|"):
                    seg = segment.strip()
                    if _ADDR_RE.match(seg):
                        result["address"] = seg
                        break
            if result["address"]:
                break

    return result
