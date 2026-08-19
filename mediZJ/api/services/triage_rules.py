"""Deterministic red-flag rules for consumer symptom triage."""

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class RedFlagRule:
    code: str
    label: str
    terms: tuple[str, ...]
    action: str


RED_FLAG_RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule(
        "chest_pain",
        "急性胸痛",
        ("胸痛", "胸口压榨", "胸口剧痛", "胸部压迫"),
        "立即停止活动，呼叫 120 或尽快前往急诊，不要自行驾车。",
    ),
    RedFlagRule(
        "breathing_difficulty",
        "严重呼吸困难",
        ("呼吸困难", "喘不上气", "无法呼吸", "嘴唇发紫"),
        "立即呼叫 120，保持坐位并确保呼吸通畅。",
    ),
    RedFlagRule(
        "altered_consciousness",
        "意识改变",
        ("意识不清", "叫不醒", "失去意识", "神志不清"),
        "立即呼叫 120；若无正常呼吸，按急救人员指导实施心肺复苏。",
    ),
    RedFlagRule(
        "syncope",
        "昏厥",
        ("昏厥", "晕倒", "突然倒地"),
        "立即呼叫 120；让患者平卧并观察呼吸。",
    ),
    RedFlagRule(
        "seizure",
        "抽搐",
        ("抽搐", "癫痫发作", "全身痉挛"),
        "保护头部并移开周围危险物，不要向口中塞东西，立即呼叫 120。",
    ),
    RedFlagRule(
        "major_bleeding",
        "大出血",
        ("大出血", "止不住血", "大量吐血", "大量便血"),
        "用干净敷料持续加压止血并立即呼叫 120。",
    ),
    RedFlagRule(
        "anaphylaxis",
        "严重过敏",
        ("严重过敏", "喉咙肿", "舌头肿", "过敏休克"),
        "立即呼叫 120；如有医生处方的肾上腺素自动注射器，按既往医嘱使用。",
    ),
    RedFlagRule(
        "self_harm",
        "自伤风险",
        ("想自杀", "不想活", "自伤", "结束生命"),
        "不要独处，立即联系 120、110 或可信任的亲友陪同前往急诊。",
    ),
)


def find_red_flags(texts: Iterable[str]) -> List[dict[str, str]]:
    """Return every unique deterministic rule matched by normalized input."""

    text = " ".join(str(value) for value in texts if value).lower()
    matches: List[dict[str, str]] = []
    for rule in RED_FLAG_RULES:
        matched_term = next((term for term in rule.terms if term.lower() in text), None)
        if matched_term:
            matches.append(
                {
                    "code": rule.code,
                    "label": rule.label,
                    "matched_term": matched_term,
                    "action": rule.action,
                }
            )
    return matches
