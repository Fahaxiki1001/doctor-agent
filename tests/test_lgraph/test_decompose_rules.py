"""tests/test_lgraph/test_decompose_rules.py — 任务分解规则短路

规则的错误方向必须偏保守：漏判只是多花一次 LLM 分解，误判会降低回答质量。
"""

import pytest

from mediZJ.lgraph.decompose_rules import try_rule_decompose


def _state(question: str, **kwargs):
    base = {"question": question, "recent_history": [{"role": "user", "content": "上一轮"}]}
    base.update(kwargs)
    return base


class TestRuleHit:
    """命中：追问轮 + 单点诉求。"""

    def test_followup_single_point_hits(self):
        subtasks = try_rule_decompose(_state("那要吃多久"))
        assert subtasks == [{
            "type": "general",
            "description": "那要吃多久",
            "assigned_agent": "consultation_agent",
            "id": "rule",
        }]

    def test_question_is_stripped(self):
        subtasks = try_rule_decompose(_state("  需要忌口吗  "))
        assert subtasks[0]["description"] == "需要忌口吗"


class TestRuleFallback:
    """回落：任一条件不满足即交给 LLM。"""

    def test_first_turn_without_context_falls_back(self):
        assert try_rule_decompose({"question": "那要吃多久"}) is None

    def test_clarify_round_falls_back_to_llm(self):
        # 做过澄清说明 LeadAgent 判定信息不足，交回 LLM 组织子任务
        state = {
            "question": "需要复查吗",
            "recent_history": [{"role": "user", "content": "上一轮"}],
            "clarify_rounds": [{"round": 1}],
        }
        assert try_rule_decompose(state) is None

    def test_empty_question_falls_back(self):
        assert try_rule_decompose(_state("   ")) is None

    def test_long_question_falls_back(self):
        assert try_rule_decompose(_state("头痛" * 40)) is None

    @pytest.mark.parametrize("word", ["还有", "另外", "同时", "以及", "顺便", "除了", "并且"])
    def test_conjunction_falls_back(self, word):
        assert try_rule_decompose(_state(f"要吃多久，{word}需要忌口吗")) is None

    @pytest.mark.parametrize("word", ["指南", "共识", "最新研究", "证据", "文献", "循证"])
    def test_evidence_request_falls_back(self, word):
        assert try_rule_decompose(_state(f"有没有相关{word}")) is None

    @pytest.mark.parametrize("word", ["胸痛", "呼吸困难", "昏迷", "抽搐", "大出血", "自杀", "剧烈头痛"])
    def test_high_risk_falls_back(self, word):
        assert try_rule_decompose(_state(f"我现在{word}怎么办")) is None
