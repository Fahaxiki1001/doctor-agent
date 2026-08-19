"""SafetyGate decision-table tests."""

import pytest

from mediZJ.api.services.safety_service import (
    SafetyDecision,
    SafetyGate,
    SafetyInput,
)


@pytest.mark.parametrize(
    ("payload", "decision"),
    [
        (SafetyInput(user_text="轻微鼻塞"), SafetyDecision.ALLOW),
        (
            SafetyInput(llm_result={"risk_level": "medium"}),
            SafetyDecision.ALLOW_WITH_NOTICE,
        ),
        (
            SafetyInput(rule_result={"risk_level": "high"}),
            SafetyDecision.MEDICAL_ATTENTION,
        ),
        (
            SafetyInput(vision_confidence=0.4, user_confirmed=False),
            SafetyDecision.MANUAL_REVIEW,
        ),
        (
            SafetyInput(rule_result={"risk_level": "emergency"}),
            SafetyDecision.EMERGENCY_STOP,
        ),
    ],
)
def test_safety_decision_table(payload, decision):
    assert SafetyGate().evaluate(payload).decision == decision


def test_emergency_rule_cannot_be_downgraded_by_model():
    result = SafetyGate().evaluate(
        SafetyInput(
            rule_result={"risk_level": "emergency"},
            llm_result={"risk_level": "low"},
        )
    )
    assert result.decision == SafetyDecision.EMERGENCY_STOP
    assert result.risk_level == "emergency"


def test_deterministic_emergency_text_is_stopped():
    result = SafetyGate().evaluate(
        SafetyInput(user_text="突然喘不上气，而且意识不清")
    )
    assert result.decision == SafetyDecision.EMERGENCY_STOP
