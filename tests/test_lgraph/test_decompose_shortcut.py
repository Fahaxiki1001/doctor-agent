"""tests/test_lgraph/test_decompose_shortcut.py — 分解节点规则短路接线

验证命中时不调用 LeadAgent、事件仍然发出；未命中时照常调 LLM 分解。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mediZJ.swarm.events import EventType
from mediZJ.swarm.intent_classifier import IntentResult


def _make_coordinator():
    coordinator = type("Coordinator", (), {})()
    coordinator.short_term_memory = type("STM", (), {
        "get_recent_messages": AsyncMock(return_value=[
            {"role": "user", "content": "布洛芬能治头痛吗"},
        ]),
        "add_message": AsyncMock(return_value=None),
        "merge_sub_session": lambda *a, **k: None,
    })()
    coordinator.long_term_memory = type("LTM", (), {
        "search_similar_sessions": AsyncMock(return_value=[]),
    })()
    coordinator.personal_profile = type("PP", (), {"to_text": lambda self: "暂无"})()
    coordinator.questionnaire_manager = None
    coordinator._refresh_worker_profiles = lambda *a, **k: None
    coordinator._save_long_term_memory = AsyncMock(return_value=None)
    coordinator._save_session_summary = lambda *a, **k: None
    coordinator.format_references_section = lambda refs: ""
    coordinator.extract_suggestions = lambda text: []
    coordinator.get_worker = lambda agent_id: MagicMock()
    coordinator.lead_agent = type("LA", (), {
        "chat_reply": AsyncMock(return_value={"answer": ""}),
        "assess_and_decompose": AsyncMock(return_value={
            "subtasks": [{"description": "回答用户问题",
                          "assigned_agent": "consultation_agent"}],
        }),
        "set_on_thinking": lambda *a, **k: None,
        "set_on_thinking_done": lambda *a, **k: None,
    })()
    coordinator.intent_classifier = type("IC", (), {
        "classify": AsyncMock(return_value=IntentResult(
            intent="medical", confidence=0.9, source="llm", reason="test",
        )),
    })()
    return coordinator


async def _run_decompose(question: str, events: list):
    """只跑到 assess_decompose 节点，取其返回的 subtasks。"""
    from mediZJ.lgraph import supervisor_graph as sg

    coordinator = _make_coordinator()
    captured = {}

    original = sg.build_agent_subgraph

    def _fake_subgraph(*args, **kwargs):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={
            "final_answer": "回答", "references": [], "usage": {},
            "message_count": 1, "iterations": 1,
        })
        return graph

    sg.build_agent_subgraph = _fake_subgraph
    try:
        graph = sg.build_supervisor_graph(
            coordinator,
            tool_registry=None,
            event_callback=events.append,
        )
        state = await graph.ainvoke(
            {"question": question, "session_id": "d1"},
            config={"configurable": {"thread_id": "d1"}},
        )
    finally:
        sg.build_agent_subgraph = original

    captured["subtasks"] = state.get("subtasks", [])
    captured["coordinator"] = coordinator
    return captured


class TestDecomposeShortcut:
    @pytest.mark.asyncio
    async def test_rule_hit_skips_lead_agent(self):
        events = []
        out = await _run_decompose("那要吃多久", events)
        out["coordinator"].lead_agent.assess_and_decompose.assert_not_awaited()
        assert out["subtasks"][0]["id"] == "rule"
        assert out["subtasks"][0]["assigned_agent"] == "consultation_agent"

    @pytest.mark.asyncio
    async def test_rule_hit_still_emits_decompose_events(self):
        events = []
        await _run_decompose("那要吃多久", events)
        decompose_events = [
            e for e in events
            if e.data.get("phase") == "decompose"
        ]
        types = {e.type for e in decompose_events}
        assert EventType.AGENT_THINKING in types
        assert EventType.AGENT_THINKING_DONE in types
        assert all(e.data.get("status") == "skipped" for e in decompose_events)

    @pytest.mark.asyncio
    async def test_high_risk_still_calls_lead_agent(self):
        events = []
        out = await _run_decompose("我现在胸痛怎么办", events)
        out["coordinator"].lead_agent.assess_and_decompose.assert_awaited_once()
