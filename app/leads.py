import re
from dataclasses import dataclass


PHONE_RE = re.compile(r"(?:(?:\+|8)?\d[\d\s().-]{7,}\d)")
NAME_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ]+")

ORDER_WORDS = {
    "заказать",
    "заявка",
    "заявку",
    "заявки",
    "заявкой",
    "оформить",
    "оформляю",
    "оформлю",
    "купить",
    "хочу",
    "оставить",
    "оставлю",
    "тапсырыс",
    "алғым",
    "керек",
    "өтінім",
    "отиним",
    "қалдырам",
    "калдырам",
    "қалдыру",
    "калдыру",
    "қалдырғым",
    "калдыргым",
}

QUESTION_OR_SERVICE_WORDS = {
    "сколько",
    "цена",
    "стоит",
    "стоимость",
    "демо",
    "бот",
    "что",
    "как",
    "когда",
    "где",
    "почему",
    "можно",
    "бағасы",
    "қанша",
    "қалай",
    "қайда",
    "не",
    "иә",
    "да",
    "нет",
    "жоқ",
    "привет",
    "салем",
    "салам",
    "сәлем",
    "hello",
    "hi",
    "узнать",
    "инфо",
    "информация",
    "подробнее",
}


@dataclass(frozen=True)
class LeadUpdate:
    name: str | None = None
    phone: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.name or self.phone)


def looks_like_order_intent(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ORDER_WORDS)


def extract_lead_update(
    text: str,
    current_name: str | None,
    current_phone: str | None,
    draft_exists: bool,
    forced_name: str | None = None,
    forced_phone: str | None = None,
) -> LeadUpdate:
    phone = _normalize_phone(forced_phone) if forced_phone else _extract_phone(text)
    name = _clean_name(forced_name) if forced_name else None

    if not name:
        name = _extract_name(text, phone=phone, allow_standalone=draft_exists)

    if current_phone:
        phone = None
    if current_name:
        name = None

    return LeadUpdate(name=name, phone=phone)


def _extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    return _normalize_phone(match.group(0))


def _normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None

    raw = raw.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8:
        return None

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
        has_plus = True
    elif len(digits) == 10:
        digits = "7" + digits
        has_plus = True

    return f"+{digits}" if has_plus or len(digits) >= 10 else digits


def _extract_name(text: str, phone: str | None, allow_standalone: bool) -> str | None:
    cleaned = PHONE_RE.sub(" ", text)
    cleaned = re.sub(
        r"(?i)\b(меня зовут|мое имя|моё имя|имя|номер|телефон|whatsapp|telegram|"
        r"ватсап|мой|менің атым|атым|есімім)\b",
        " ",
        cleaned,
    )

    words = [_clean_name(word) for word in NAME_WORD_RE.findall(cleaned)]
    words = [
        word
        for word in words
        if word
        and word.lower() not in QUESTION_OR_SERVICE_WORDS
        and word.lower() not in ORDER_WORDS
    ]

    if phone and words:
        return " ".join(words[:3])

    if allow_standalone and 1 <= len(words) <= 3 and "?" not in text:
        lowered_words = {word.lower() for word in words}
        if not lowered_words.intersection(QUESTION_OR_SERVICE_WORDS):
            return " ".join(words)

    return None


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    words = NAME_WORD_RE.findall(value.strip())
    if not words:
        return None
    return " ".join(word[:1].upper() + word[1:].lower() for word in words[:3])
