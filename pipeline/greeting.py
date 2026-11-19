"""Opening of a call, spoken by the device when the handset is lifted.

Built from building blocks in prompts/begruessung.txt (time of day, the
senior's name, today's next appointment, a small concrete question), so the
team changes the wording without touching code. No LLM is involved: the
opening is instant and never "Wie kann ich Ihnen helfen?".
"""

import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from logging_config import get_logger

log = get_logger("greeting")

_SECTION = re.compile(r"^\[([a-z_]+)\]\s*$")
# Fallback if the file is missing or a section is empty: the device still greets
_FALLBACK = {
    "morgen": ["Guten Morgen{anrede}."], "mittag": ["Guten Tag{anrede}."],
    "nachmittag": ["Guten Tag{anrede}."], "abend": ["Guten Abend{anrede}."],
    "nacht": ["Guten Abend{anrede}."], "termin": ["Heute um {zeit} steht noch etwas an: {titel}."],
    "frage": ["Wie geht es Ihnen heute?"],
}


def time_of_day(hour: int) -> str:
    if 5 <= hour < 11:
        return "morgen"
    if 11 <= hour < 14:
        return "mittag"
    if 14 <= hour < 18:
        return "nachmittag"
    if 18 <= hour < 22:
        return "abend"
    return "nacht"


def parse(text: str) -> dict[str, list[str]]:
    """Sections of the building-block file: {name: [variant, ...]}."""
    sections: dict[str, list[str]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _SECTION.match(line)
        if m:
            current = sections.setdefault(m.group(1), [])
        elif current is not None:
            current.append(line)
    return sections


class Greeter:
    """Composes the opening; remembers the last variant per section so the
    same sentence never comes twice in a row (RAM only)."""

    def __init__(self, path: Path, rng: random.Random | None = None):
        self.path = Path(path)
        self.rng = rng or random.Random()
        self._last: dict[str, str] = {}
        self._cache: tuple[float, dict[str, list[str]]] | None = None

    def blocks(self) -> dict[str, list[str]]:
        try:
            mtime = self.path.stat().st_mtime
            if self._cache is None or self._cache[0] != mtime:
                self._cache = (mtime, parse(self.path.read_text(encoding="utf-8")))
            return self._cache[1]
        except OSError as e:
            log.warning("Greeting file not readable (%s), using fallback", type(e).__name__)
            return {}

    def _pick(self, key: str, variants: list[str]) -> str:
        options = [v for v in variants if v != self._last.get(key)] or variants
        choice = self.rng.choice(options)
        self._last[key] = choice
        return choice

    def compose(self, now: datetime, name: str = "",
                next_appointment: tuple[datetime, str] | None = None) -> str:
        blocks = self.blocks()
        tod = time_of_day(now.hour)

        def variants(section: str) -> list[str]:
            lines = blocks.get(section) or []
            if not name:
                lines = [v for v in lines if "{name}" not in v]
            return lines

        fields = {"anrede": f", {name}" if name else "", "name": name}
        hello = variants(tod) or _FALLBACK[tod]
        parts = [self._fill(self._pick(tod, hello), fields)]
        if next_appointment:
            when, title = next_appointment
            zeit = f"{when.hour}:{when.minute:02d} Uhr" if when.minute else f"{when.hour} Uhr"
            lines = variants("termin") or _FALLBACK["termin"]
            parts.append(self._fill(self._pick("termin", lines), dict(fields, zeit=zeit, titel=title)))
        questions = variants("frage") + variants(f"frage_{tod}")
        parts.append(self._fill(self._pick("frage", questions or _FALLBACK["frage"]), fields))
        return " ".join(p for p in parts if p)

    @staticmethod
    def _fill(template: str, fields: dict[str, str]) -> str:
        # Unknown placeholders are left out rather than read aloud
        return re.sub(r"\{([a-z]+)\}", lambda m: fields.get(m.group(1), ""), template).strip()


def next_appointment_today(now: datetime) -> tuple[datetime, str] | None:
    """The next appointment (not medication) later today, from the local DB."""
    import appointments
    local = now.astimezone(appointments.LOCAL_TZ)
    end = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    try:
        items = appointments._between(local, end, ("termin",))
    except Exception as e:
        log.warning("Appointments not readable for greeting (%s)", type(e).__name__)
        return None
    return (items[0][0], items[0][2]) if items else None


_greeter: Greeter | None = None


def opening(now: datetime | None = None) -> str:
    """The sentence the device says when the handset is lifted."""
    global _greeter
    import appointments
    from config import PROMPTS_DIR, SENIOR_NAME
    if _greeter is None or _greeter.path != PROMPTS_DIR / "begruessung.txt":
        _greeter = Greeter(PROMPTS_DIR / "begruessung.txt")
    now = now or datetime.now(appointments.LOCAL_TZ)
    return _greeter.compose(now.astimezone(appointments.LOCAL_TZ), SENIOR_NAME,
                            next_appointment_today(now))
