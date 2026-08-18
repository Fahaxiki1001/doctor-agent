"""任务分解规则短路

追问轮 + 单点诉求的问题不需要 LLM 参与分解：下游只用得到"几个子任务、交给谁"，
而这类问题的答案恒为"1 个、consultation_agent"。规则命中即跳过一次 4s 级别的
LLM 往返；任一条件不满足则回落 LLM 分解（宁可多花时间，不可降低路由质量）。
"""
from typing import Any, Dict, List, Mapping, Optional

from loguru import logger

# 单点诉求的问题长度上限（超过则认为可能含多个诉求，交给 LLM 判断）
_MAX_SINGLE_POINT_LEN = 60

# 并列连接词：出现即可能是多诉求
_CONJUNCTIONS = frozenset({"还有", "另外", "同时", "以及", "顺便", "除了", "并且"})

# 指南/证据类诉求：应保留给 research_agent
_EVIDENCE_WORDS = frozenset({"指南", "共识", "最新研究", "证据", "文献", "循证", "临床试验"})

# 高危信号：一律回落 LLM 分解，避免规则把危险问题降级成普通咨询
_HIGH_RISK_WORDS = frozenset({
    "胸痛", "胸闷", "呼吸困难", "喘不上气", "昏迷", "抽搐", "大出血", "咯血",
    "自杀", "剧烈头痛", "意识不清", "晕倒", "休克", "中毒", "过敏性",
})

_BLOCKING_WORDS = _CONJUNCTIONS | _EVIDENCE_WORDS | _HIGH_RISK_WORDS


def try_rule_decompose(state: Mapping[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """尝试用规则替代 LLM 分解。

    命中条件（合取，全部满足才短路）：
    1. 是追问轮：存在最近对话（首轮冷启动不短路）
    2. 本轮未做澄清：做过澄清说明 LeadAgent 判定信息不足，交回 LLM 组织子任务
    3. 单点诉求：长度不超过 _MAX_SINGLE_POINT_LEN
    4. 不含并列连接词、指南/证据类词、高危词

    Args:
        state: SupervisorState

    Returns:
        命中时返回单个 consultation_agent 子任务的列表；未命中返回 None。
    """
    question = (state.get("question") or "").strip()
    if not question:
        return None

    if not state.get("recent_history"):
        return None

    if state.get("clarify_rounds"):
        return None

    if len(question) > _MAX_SINGLE_POINT_LEN:
        return None

    hit = next((w for w in _BLOCKING_WORDS if w in question), None)
    if hit:
        logger.debug(f"[decompose_rules] 命中回落词 {hit!r}，交给 LLM 分解")
        return None

    return [{
        "type": "general",
        "description": question,
        "assigned_agent": "consultation_agent",
        "id": "rule",
    }]
