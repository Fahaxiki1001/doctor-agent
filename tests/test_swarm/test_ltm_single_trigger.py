"""tests/test_swarm/test_ltm_single_trigger.py — 长期记忆抽取只触发一次

覆盖：
- 图内 _finalize 节点不再触发 LTM（去掉重复的第二次抽取）
- compose_result 触发且仅触发一次
- 闲聊模式（chat_mode）不触发，且不写 _ltm_save_task
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mediZJ.swarm.intent_classifier import IntentResult
from mediZJ.swarm.swarm_coordinator import SwarmCoordinator


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


async def _run_graph(question: str):
    from mediZJ.lgraph import supervisor_graph as sg

    coordinator = _make_coordinator()
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
            coordinator, tool_registry=None, event_callback=lambda e: None,
        )
        state = await graph.ainvoke(
            {"question": question, "session_id": "ltm1"},
            config={"configurable": {"thread_id": "ltm1"}},
        )
    finally:
        sg.build_agent_subgraph = original

    return coordinator, state


def _compose(save_mock, result_state):
    stub = SimpleNamespace(_save_long_term_memory=save_mock)
    return SwarmCoordinator.compose_result(
        stub,
        question="布洛芬能治头痛吗",
        result_state=result_state,
        start_time=datetime.now(),
        session_id="ltm1",
    )


class TestLTMSingleTrigger:
    @pytest.mark.asyncio
    async def test_graph_finalize_does_not_trigger_ltm(self):
        """图内 _finalize 不再触发抽取，避免与 compose_result 重复"""
        coordinator, state = await _run_graph("布洛芬能治头痛吗")
        coordinator._save_long_term_memory.assert_not_awaited()
        assert state["_swarm_finalized"] is True

    @pytest.mark.asyncio
    async def test_compose_result_triggers_once(self):
        """compose_result 是唯一触发点，且任务句柄交给调用方"""
        save_mock = AsyncMock(return_value=None)
        result = _compose(save_mock, {
            "final_answer": "回答", "total_time": 1.0, "usage": {},
        })

        task = result["_ltm_save_task"]
        await asyncio.wait_for(task, timeout=1.0)
        assert save_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_chat_mode_skips_ltm(self):
        """闲聊模式不触发抽取，也不写 _ltm_save_task"""
        save_mock = AsyncMock(return_value=None)
        result = _compose(save_mock, {
            "final_answer": "你好呀", "total_time": 0.5, "usage": {},
            "chat_mode": True,
        })

        await asyncio.sleep(0)
        assert "_ltm_save_task" not in result
        save_mock.assert_not_awaited()
