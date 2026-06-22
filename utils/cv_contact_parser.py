from __future__ import annotations

import re


_EMAIL_RE  = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_PHONE_RE  = re.compile(r"\+?[\d][\d\s\-().]{6,}")
_LI_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+", re.I)

_ADDR_STOP = {"📧", "📞", "📱", "|", "Portfolio", "Linkedin", "LinkedIn", "Github", "GitHub"}
_PHONE_STOP = {"📧", "🏠", "|", "Portfolio", "Linkedin", "LinkedIn"}


def parse_contact(cv_text: str) -> dict[str, str]:
    """
    Extract contact fields from a CV markdown string.

    Returns a dict with keys: name, email, phone, address, linkedin.
    Any field not found is an empty string.
    The CV is the source of truth; callers should use config values only as fallbacks.
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

    # ── Email: first line matching email pattern ──────────────────────────────
    for line in lines:
        m = _EMAIL_RE.search(line)
        if m:
            result["email"] = m.group().strip()
            break

    # ── LinkedIn URL: explicit link in CV ────────────────────────────────────
    for line in lines:
        m = _LI_URL_RE.search(line)
        if m:
            url = m.group().strip()
            if not url.startswith("http"):
                url = "https://" + url
            result["linkedin"] = url
            break

    # ── Address: lines immediately after 🏠 ──────────────────────────────────
    for i, line in enumerate(lines):
        if "🏠" in line:
            parts: list[str] = []
            # address may be on the same line after the emoji, or on the next line(s)
            inline = line.replace("🏠", "").strip()
            if inline:
                parts.append(inline)
            for j in range(i + 1, min(i + 4, len(lines))):
                chunk = lines[j].strip()
                if not chunk or any(stop in chunk for stop in _ADDR_STOP):
                    break
                parts.append(chunk)
            if parts:
                result["address"] = ", ".join(parts)
            break

    # ── Phone: lines immediately after 📞 ────────────────────────────────────
    for i, line in enumerate(lines):
        if "📞" in line or "📱" in line:
            parts = []
            inline = re.sub(r"[📞📱]", "", line).strip()
            if inline:
                parts.append(inline)
            for j in range(i + 1, min(i + 5, len(lines))):
                chunk = lines[j].strip()
                if not chunk or any(stop in chunk for stop in _PHONE_STOP):
                    break
                # only accumulate lines that look like phone fragments
                if re.search(r"[\d\+\-\(\)]", chunk):
                    parts.append(chunk)
                else:
                    break
            if parts:
                # Join and tidy: remove trailing/leading hyphens between fragments
                raw = " ".join(p.rstrip("-").lstrip("-") for p in parts)
                # Collapse multiple spaces and normalise
                result["phone"] = re.sub(r"\s+", " ", raw).strip()
            break

    # ── Phone fallback: regex scan if emoji-based search found nothing ────────
    if not result["phone"]:
        for line in lines:
            m = _PHONE_RE.search(line)
            if m:
                result["phone"] = m.group().strip()
                break

    return result
