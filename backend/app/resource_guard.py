import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx


URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)

TRUSTED_FREE_DOMAINS = {
    "developer.mozilla.org",
    "docs.python.org",
    "fastapi.tiangolo.com",
    "habr.com",
    "learn.javascript.ru",
    "metanit.com",
    "postgrespro.ru",
    "ru.hexlet.io",
    "ru.wikipedia.org",
    "sql-academy.org",
    "sqlbolt.com",
}

PAID_OR_FREEMIUM_DOMAINS = {
    "coursera.org",
    "edx.org",
    "geekbrains.ru",
    "netology.ru",
    "practicum.yandex.ru",
    "skillbox.ru",
    "sky.pro",
    "udemy.com",
}

PAID_KEYWORDS = {
    "paid",
    "premium",
    "subscription",
    "subscribe",
    "trial",
    "buy",
    "purchase",
    "pricing",
    "checkout",
    "оплата",
    "оплатить",
    "платный",
    "премиум",
    "подписка",
    "купить",
    "цена",
    "тариф",
    "доступ после оплаты",
}

FREE_KEYWORDS = {
    "free",
    "open access",
    "бесплатно",
    "бесплатный",
    "открытый доступ",
    "свободный доступ",
}

LOGIN_OR_PAYMENT_PATH_MARKERS = {
    "login",
    "signin",
    "auth",
    "payment",
    "pay",
    "checkout",
    "pricing",
    "subscription",
    "subscribe",
}


class TextExtractingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.lang: str | None = None
        self.title_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag == "html":
            attrs_dict = dict(attrs)
            self.lang = attrs_dict.get("lang") or self.lang
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._skip_depth:
            return
        self.text_parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts)


@dataclass
class ResourceGuardResult:
    decision: str
    classifier: str
    url: str | None
    domain: str | None
    free_score: float
    ru_score: float
    quality_score: float
    http_status: int | None
    reasons: list[str]
    warnings: list[str]


def _normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def _domain_matches(domain: str | None, domains: set[str]) -> bool:
    if not domain:
        return False
    return any(domain == item or domain.endswith("." + item) for item in domains)


def _extract_url(item: dict[str, Any]) -> str | None:
    for key in ("Resource_url", "URL", "Url", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
            return value.strip()

    resources = str(item.get("Resources") or "")
    match = URL_RE.search(resources)
    if not match:
        return None
    return match.group(0).rstrip(".,;")


def _as_text_blob(item: dict[str, Any]) -> str:
    values = [
        item.get("Name"),
        item.get("Description"),
        item.get("Resources"),
        item.get("Source_name"),
        item.get("Why_this_material"),
        item.get("Language_evidence"),
        item.get("Free_evidence"),
        item.get("Access_type"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _is_self_contained(item: dict[str, Any]) -> bool:
    source_type = str(item.get("Source_type") or "").lower()
    resources = str(item.get("Resources") or "")
    return source_type in {"project", "practice"} and not URL_RE.search(resources)


def _has_paid_markers(text: str) -> bool:
    return any(marker in text for marker in PAID_KEYWORDS)


def _has_free_markers(text: str) -> bool:
    return any(marker in text for marker in FREE_KEYWORDS)


def _cyrillic_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    cyrillic = [char for char in letters if "а" <= char.lower() <= "я" or char.lower() == "ё"]
    return len(cyrillic) / len(letters)


def _keyword_overlap(item: dict[str, Any], page_text: str) -> float:
    topic_words = set(
        re.findall(
            r"[a-zа-яё0-9]{4,}",
            " ".join(
                str(item.get(key) or "")
                for key in ("Skill_name", "Topic_name", "Name", "Description")
            ).lower(),
        )
    )
    if not topic_words:
        return 0.5

    page_words = set(re.findall(r"[a-zа-яё0-9]{4,}", page_text.lower()))
    if not page_words:
        return 0.0

    overlap = len(topic_words & page_words) / len(topic_words)
    return min(1.0, overlap * 2)


async def _fetch_page_sample(url: str, timeout_seconds: float, max_bytes: int) -> tuple[int | None, str, str | None]:
    headers = {
        "User-Agent": "ProgressorsResourceGuard/1.0",
        "Accept": "text/html,text/plain,application/xhtml+xml,*/*;q=0.8",
        "Range": f"bytes=0-{max_bytes - 1}",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=headers) as response:
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                remaining = max_bytes - total
                chunks.append(chunk[:remaining])
                total += len(chunk[:remaining])
                if total >= max_bytes:
                    break
            content = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            return response.status_code, content.decode(encoding, errors="ignore"), str(response.url)


def _base_scores(item: dict[str, Any], classifier_name: str) -> ResourceGuardResult:
    url = _extract_url(item)
    domain = _normalize_domain(url)
    text = _as_text_blob(item)
    reasons: list[str] = []
    warnings: list[str] = []
    free_score = 0.5
    ru_score = 0.5
    quality_score = 0.5

    if _is_self_contained(item):
        reasons.append("self_contained_practice_or_project")
        return ResourceGuardResult(
            decision="accepted",
            classifier=classifier_name,
            url=url,
            domain=domain,
            free_score=0.8,
            ru_score=0.8,
            quality_score=0.7,
            http_status=None,
            reasons=reasons,
            warnings=warnings,
        )

    if not url:
        warnings.append("missing_url")
        free_score -= 0.2
        ru_score -= 0.1
        quality_score -= 0.2
    else:
        reasons.append("url_present")

    if _domain_matches(domain, TRUSTED_FREE_DOMAINS):
        reasons.append("trusted_free_domain")
        free_score += 0.35
        ru_score += 0.2
        quality_score += 0.2

    if _domain_matches(domain, PAID_OR_FREEMIUM_DOMAINS):
        warnings.append("paid_or_freemium_domain")
        free_score -= 0.6
        quality_score -= 0.2

    if _has_paid_markers(text):
        warnings.append("paid_keyword_in_metadata")
        free_score -= 0.35

    if _has_free_markers(text):
        reasons.append("free_keyword_in_metadata")
        free_score += 0.15

    language = str(item.get("Language") or "").strip().lower()
    if language == "ru":
        reasons.append("llm_language_ru")
        ru_score += 0.2
    elif language and language != "ru":
        warnings.append("llm_language_not_ru")
        ru_score -= 0.5

    if item.get("Is_free") is True:
        reasons.append("llm_claims_free")
        free_score += 0.1
    elif item.get("Is_free") is False:
        warnings.append("llm_claims_not_free")
        free_score -= 0.5

    final_free = max(0.0, min(1.0, free_score))
    final_ru = max(0.0, min(1.0, ru_score))
    final_quality = max(0.0, min(1.0, quality_score))
    decision = "accepted" if final_free >= 0.55 and final_ru >= 0.55 else "rejected"

    return ResourceGuardResult(
        decision=decision,
        classifier=classifier_name,
        url=url,
        domain=domain,
        free_score=round(final_free, 3),
        ru_score=round(final_ru, 3),
        quality_score=round(final_quality, 3),
        http_status=None,
        reasons=reasons,
        warnings=warnings,
    )


class ResourceQualityClassifier:
    name = "resource_quality_v1"

    def __init__(self, *, timeout_seconds: float = 6.0, max_html_bytes: int = 50000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_html_bytes = max_html_bytes

    async def classify(self, item: dict[str, Any]) -> ResourceGuardResult:
        result = _base_scores(item, self.name)
        if result.url is None:
            return result

        try:
            status_code, html, final_url = await _fetch_page_sample(
                result.url,
                self.timeout_seconds,
                self.max_html_bytes,
            )
        except Exception as exc:
            result.warnings.append(f"http_check_failed:{type(exc).__name__}")
            if not _domain_matches(result.domain, TRUSTED_FREE_DOMAINS):
                result.decision = "rejected"
            return result

        result.http_status = status_code
        if not status_code or status_code >= 400:
            result.warnings.append("http_status_not_ok")
            result.decision = "rejected"
            return result

        final_domain = _normalize_domain(final_url)
        if final_domain and final_domain != result.domain:
            result.domain = final_domain

        path = urlparse(final_url or result.url).path.lower()
        if any(marker in path for marker in LOGIN_OR_PAYMENT_PATH_MARKERS):
            result.warnings.append("redirected_to_login_or_payment_path")
            result.free_score = max(0.0, round(result.free_score - 0.5, 3))

        parser = TextExtractingParser()
        parser.feed(html)
        page_text = " ".join([parser.title, parser.text])[: self.max_html_bytes]
        page_text_lower = page_text.lower()

        if parser.lang and parser.lang.lower().startswith("ru"):
            result.reasons.append("html_lang_ru")
            result.ru_score = min(1.0, round(result.ru_score + 0.25, 3))
        elif _cyrillic_ratio(page_text) >= 0.25:
            result.reasons.append("cyrillic_ratio_ru")
            result.ru_score = min(1.0, round(result.ru_score + 0.25, 3))
        else:
            result.warnings.append("ru_language_not_confirmed_by_html")
            result.ru_score = max(0.0, round(result.ru_score - 0.45, 3))

        if _has_paid_markers(page_text_lower):
            result.warnings.append("paid_keyword_in_html")
            result.free_score = max(0.0, round(result.free_score - 0.35, 3))
        else:
            result.reasons.append("no_paid_keyword_in_html_sample")
            result.free_score = min(1.0, round(result.free_score + 0.1, 3))

        relevance = _keyword_overlap(item, page_text)
        result.quality_score = round((result.quality_score + relevance) / 2, 3)
        if relevance >= 0.35:
            result.reasons.append("topic_overlap_confirmed")
        else:
            result.warnings.append("low_topic_overlap")

        if result.free_score >= 0.65 and result.ru_score >= 0.65 and result.quality_score >= 0.35:
            result.decision = "accepted"
        else:
            result.decision = "rejected"
        return result


async def guard_roadmap_items(
    items: list[dict[str, Any]],
    *,
    timeout_seconds: float = 6.0,
    max_html_bytes: int = 50000,
) -> dict[str, Any]:
    classifier = ResourceQualityClassifier(
        timeout_seconds=timeout_seconds,
        max_html_bytes=max_html_bytes,
    )
    accepted_items: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for item in items:
        result = await classifier.classify(item)
        result_dict = asdict(result)
        results.append(result_dict)
        if result.decision != "accepted":
            continue

        enriched = dict(item)
        item_json = enriched.get("Item_json") if isinstance(enriched.get("Item_json"), dict) else {}
        enriched["Item_json"] = {
            **item_json,
            "resource_guard": result_dict,
        }
        accepted_items.append(enriched)

    return {
        "classifier": classifier.name,
        "items": accepted_items,
        "accepted_count": len(accepted_items),
        "rejected_count": len(items) - len(accepted_items),
        "results": results,
    }
