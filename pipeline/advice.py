"""Rat button (PR 9): answers only from information that was entered.

Decision B2 (14.11.2026): the device gives no medical advice of its own
(no doses, no diagnoses, no assessment of complaints). Spitex or relatives
enter information (topic + text), for example the Spitex phone number or
"Die weisse Tablette nach dem Frühstück nehmen". The device reads that text
verbatim, the same way as medication reminders. If nothing entered fits,
it says "Fragen Sie Ihre Spitex oder Ihre Ärztin."

T12 (team, 14.11.2026): if the question hints at an emergency (chest
pain, breathlessness, a fall, unconsciousness ...), the device points to
the Help button and 144 first. This is decided by a fixed word list and
spoken before the language model is asked, so it never depends on the
model. An entry that fits is still read afterwards (for example an entered
emergency number). The list is deliberately broad: a needless hint costs
one sentence, a missed emergency a lot.

Why the language model never speaks here: a 1B model cannot be trusted to
stay within a prompt instruction about medical topics. In Rat mode it only
chooses which entered topic fits the question (a number). Every sentence
the senior hears is either a fixed sentence or an entered text. If the
model fails or answers something unusable, a simple word match decides.

The question itself is not stored, not logged and not added to the
conversation history or the notes (B5: Rat questions are conversation
content and are never shown in the portal).
"""

import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone

import appointments
from logging_config import get_logger

log = get_logger("advice")

ASK = "Was möchten Sie wissen? Bitte stellen Sie Ihre Frage."
NOTHING_HEARD = "Ich habe Sie leider nicht verstanden. Drücken Sie Rat nochmals, wenn Sie etwas fragen möchten."
NO_ENTRY = "Dazu ist bei mir nichts hinterlegt. Fragen Sie Ihre Spitex oder Ihre Ärztin."
ANSWER = "Zum Thema {topic} hat {by} hinterlegt: {text}"
# After an entered text, if the question is about medication or complaints:
# the entered text answers what was entered, not necessarily what was asked
HEALTH_HINT = "Bei weiteren Fragen dazu wenden Sie sich an Ihre Spitex oder Ihre Ärztin."
# Narrower than memory.HEALTH_TERMS on purpose: "Wie erreiche ich die
# Spitex?" is a question about contact details, not about health.
HEALTH_QUESTION_TERMS = (
    "medika", "tablett", "pille", "tropfen", "dosis", "insulin", "spritz", "salbe",
    "schmerz", "weh", "blutdruck", "blutzucker", "zucker", "fieber", "krank", "symptom",
    "nebenwirk", "absetzen", "weglassen", "doppelt", "mehr nehmen", "schwindel",
)

EMERGENCY = ("Wenn es ein Notfall ist, drücken Sie sofort den Hilfe-Knopf "
             "oder rufen Sie 144 an.")

# Lower case, umlauts folded (ae, oe, ue, ss). Matched at the start of a
# word: "sturz" finds "Sturz" and "Sturzgefahr", "taub" does not find "Staub".
EMERGENCY_TERMS = (
    # chest, heart
    "brust", "herzinfarkt", "infarkt", "herzrasen", "herzstolpern", "herzschmerz",
    "herzstechen", "herzdruck",
    # breathing
    "atemnot", "luftnot", "keine luft", "kaum luft", "schlecht luft", "wenig luft",
    "nach luft", "luft bekomm", "kann nicht atmen", "kann kaum atmen", "atmet nicht",
    "atme schlecht", "atmen schlecht", "erstick",
    # falls, accidents
    "sturz", "gestuerzt", "hingefallen", "umgefallen", "hinfallen", "bin gefallen",
    "ist gefallen", "ausgerutscht", "unfall", "kann nicht aufstehen",
    "komme nicht hoch", "komme nicht mehr hoch", "nicht mehr aufstehen",
    "liege am boden", "liegt am boden", "liege auf dem boden", "liegt auf dem boden",
    "kann mich nicht bewegen", "kann mich nicht mehr bewegen",
    # consciousness, stroke
    "bewusstlos", "ohnmacht", "ohnmaechtig", "wird schwarz", "schwarz vor augen",
    "reagiert nicht", "wacht nicht auf", "schlaganfall", "hirnschlag", "gelaehmt",
    "laehmung", "kann nicht sprechen", "kann nicht mehr sprechen", "gesicht haengt",
    "taubheit", "verwirrt",
    # bleeding, poisoning, other
    "blutet", "blutung", "viel blut", "erbricht blut", "blut erbrochen",
    "vergift", "zu viele tabletten", "zu viel genommen", "krampfanfall", "anfall",
    "starke schmerzen", "furchtbare schmerzen", "unertraeglich",
    "notfall", "notarzt", "krankenwagen", "ambulanz", "rettungsdienst",
    "144 an", "144 rufen", "144 anrufen", "die 144",
    "brauche hilfe", "hilfe hilfe", "hilf mir", "helfen sie mir", "hilfe bitte",
    "bitte hilfe", "ich sterbe", "nicht mehr leben", "umbringen", "suizid",
)
# Whole words only ("taub" but not "Tauben", "krampf" but not "Krampfadern")
EMERGENCY_WORDS = {"taub", "krampf", "kraempfe", "krampfe"}
# Matched anywhere in a word ("Nasenblutung", "Kreislaufkollaps")
EMERGENCY_PARTS = ("infarkt", "blutung", "atemnot", "luftnot", "bewusstlos", "kollaps")
# Both words in the same question ("Mein Herz schmerzt", "Druck auf der Brust")
EMERGENCY_PAIRS = (("herz", "schmerz"), ("herz", "druck"), ("herz", "stech"),
                   ("herz", "rast"), ("herz", "stolper"), ("herz", "weh"))
_EMERGENCY_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in EMERGENCY_TERMS) + ")")

MAX_TOPIC = 80
MAX_TEXT = 600
MAX_ITEMS = 40          # keeps the selection prompt short on the Pi
SELECT_TIMEOUT = 20     # seconds; afterwards the word match decides

_SCHEMA = """
CREATE TABLE IF NOT EXISTS advice_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic         TEXT NOT NULL,
    text          TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    created_by_id TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


class AdviceError(ValueError):
    pass


_schema_ready: set[str] = set()


@contextmanager
def _conn():
    """Connection that commits on success, rolls back on error, always closes."""
    conn = appointments.connect()
    try:
        conn.row_factory = sqlite3.Row
        from config import MEMORY_DB_PATH
        if str(MEMORY_DB_PATH) not in _schema_ready:     # once per process and database
            conn.executescript(_SCHEMA)
            _schema_ready.add(str(MEMORY_DB_PATH))
        with conn:
            yield conn
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value, limit: int, name: str) -> str:
    if not isinstance(value, str):
        raise AdviceError(f"{name} must be text")
    value = " ".join(value.split())
    if not value:
        raise AdviceError(f"{name} must not be empty")
    if len(value) > limit:
        raise AdviceError(f"{name} longer than {limit} characters")
    return value


def add_item(topic: str, text: str, created_by: str, created_by_id: str | None = None) -> int:
    topic = _clean(topic, MAX_TOPIC, "topic")
    text = _clean(text, MAX_TEXT, "text")
    created_by = _clean(created_by, MAX_TOPIC, "created_by")
    with _conn() as conn:
        # Write lock before counting: two portal requests at once cannot
        # both pass the limit
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) FROM advice_items").fetchone()[0]
        if count >= MAX_ITEMS:
            raise AdviceError(f"at most {MAX_ITEMS} entries")
        now = _now()
        cur = conn.execute(
            "INSERT INTO advice_items (topic, text, created_by, created_by_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)", (topic, text, created_by, created_by_id, now, now))
        return cur.lastrowid


def get_item(item_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM advice_items WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def list_items() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM advice_items ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_item(item_id: int, topic: str | None = None, text: str | None = None) -> bool:
    fields, values = [], []
    if topic is not None:
        fields.append("topic = ?")
        values.append(_clean(topic, MAX_TOPIC, "topic"))
    if text is not None:
        fields.append("text = ?")
        values.append(_clean(text, MAX_TEXT, "text"))
    with _conn() as conn:
        if not fields:
            return conn.execute("SELECT 1 FROM advice_items WHERE id = ?", (item_id,)).fetchone() is not None
        fields.append("updated_at = ?")
        values.extend([_now(), item_id])
        cur = conn.execute(f"UPDATE advice_items SET {', '.join(fields)} WHERE id = ?", values)
        return cur.rowcount == 1


def delete_item(item_id: int) -> bool:
    with _conn() as conn:
        return conn.execute("DELETE FROM advice_items WHERE id = ?", (item_id,)).rowcount == 1


# --- choosing an entry for a question ---

# Words that say nothing about the topic (shorter words are dropped anyway)
_STOPWORDS = {
    "aber", "alle", "also", "auch", "bitte", "dann", "darf", "dass", "dies",
    "diese", "dieser", "doch", "dort", "durch", "eine", "einem", "einen", "einer",
    "eines", "etwas", "fuer", "gibt", "habe", "haben", "heute", "hier", "ihre",
    "ihrem", "ihren", "ihrer", "immer", "jetzt", "kann", "koennen", "koennte",
    "machen", "mein", "meine", "meinem", "meinen", "meiner", "mich", "muss", "nach",
    "nicht", "noch", "oder", "sagen", "sein", "sich", "sind", "soll", "sollte",
    "ueber", "unter", "viel", "wann", "warum", "weiss", "welche", "welcher",
    "welches", "wenn", "werden", "wieder", "wieviel", "wird", "wissen", "woher",
    "wohin",
}
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower()).translate(_FOLD)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _stems(text: str) -> set[str]:
    words = _fold(text).split()
    # Five letters are enough to treat "Tablette" and "Tabletten" alike
    return {w[:5] for w in words if len(w) >= 4 and w not in _STOPWORDS}


def _word_match(question: str, items: list[dict]) -> dict | None:
    """Fallback: the entry whose topic shares the most words with the question.

    Topic words count twice. Only a clear winner is returned; a tie or no
    shared word means "nothing entered fits".
    """
    asked = _stems(question)
    if not asked:
        return None
    scored = []
    for item in items:
        score = 2 * len(asked & _stems(item["topic"])) + len(asked & _stems(item["text"]))
        scored.append((score, item))
    scored.sort(key=lambda s: s[0], reverse=True)
    best = scored[0][0] if scored else 0
    if best < 2 or (len(scored) > 1 and scored[1][0] == best):
        return None
    return scored[0][1]


SELECT_PROMPT = (
    "Du ordnest eine Frage einem Thema aus einer Liste zu. "
    "Antworte nur mit der Nummer des passenden Themas. "
    "Wenn kein Thema wirklich passt, antworte 0. Schreibe sonst nichts."
)


def _select_messages(question: str, items: list[dict]) -> list[dict]:
    lines = [f"{i}. {item['topic']}" for i, item in enumerate(items, start=1)]
    return [
        {"role": "system", "content": SELECT_PROMPT},
        {"role": "user", "content": "Themen:\n" + "\n".join(lines) + f"\n\nFrage: {question}\n\nNummer:"},
    ]


def _parse_choice(reply: str, count: int) -> int | None:
    """Number in the reply: 0..count, else None (unusable).

    The first number counts. Further numbers are ignored unless they are
    another valid choice ("1 oder 2" is unusable; "3. Notruf 144" is 3).
    """
    numbers = [int(n) for n in re.findall(r"-?\d+", reply or "")]
    if not numbers or not 0 <= numbers[0] <= count:
        return None
    if any(n != numbers[0] and 0 <= n <= count for n in numbers[1:]):
        return None
    return numbers[0]


def find_item(question: str, items: list[dict] | None = None, complete=None) -> dict | None:
    """Entry that answers the question, or None. Never logs the question."""
    if items is None:
        items = list_items()
    if not items or not question.strip():
        return None
    if complete is None:
        from llm_backend import complete
    try:
        reply = complete(_select_messages(question, items), timeout_override=SELECT_TIMEOUT)
    except Exception as e:
        log.warning("Rat: selection by the model failed (%s), word match used", type(e).__name__)
        reply = None
    choice = _parse_choice(reply, len(items)) if reply is not None else None
    if choice is None:
        if reply is not None:
            log.warning("Rat: unusable selection from the model, word match used")
        item = _word_match(question, items)
    elif choice == 0:
        item = None
    else:
        item = items[choice - 1]
    # Which entry was chosen would reveal what was asked: not logged
    log.info("Rat: %s", "entry read out" if item else "no entry fits")
    return item


def is_health_question(question: str) -> bool:
    text = _fold(question)
    return any(term in text for term in HEALTH_QUESTION_TERMS)


def is_emergency(question: str) -> bool:
    """T12: word list only, never the model. Deliberately broad."""
    text = _fold(question)
    words = text.split()
    if _EMERGENCY_RE.search(text) or EMERGENCY_WORDS & set(words) or text == "hilfe":
        return True
    if any(part in w for w in words for part in EMERGENCY_PARTS):
        return True
    return any(any(w.startswith(a) for w in words) and any(b in w for w in words)
               for a, b in EMERGENCY_PAIRS)


def decide(question: str, items: list[dict] | None = None, complete=None) -> tuple[bool, dict | None]:
    """(emergency?, entry or None) for a Rat question.

    The emergency hint does not replace an entry that fits: someone who asks
    for the entered emergency number hears the hint and then the number.
    """
    return is_emergency(question), find_item(question, items, complete)


def reply_for(question: str, items: list[dict] | None = None, complete=None) -> list[str]:
    """The sentences the device speaks, in order."""
    emergency, item = decide(question, items, complete)
    if emergency:
        return [EMERGENCY] + ([answer_for(item, question)] if item else [])
    return [answer_for(item, question)]


def answer_for(item: dict | None, question: str = "") -> str:
    """The sentence the device speaks: fixed text or the entered text verbatim."""
    if item is None:
        return NO_ENTRY
    answer = ANSWER.format(topic=item["topic"], by=item["created_by"], text=item["text"])
    if is_health_question(question):
        answer += " " + HEALTH_HINT
    return answer
