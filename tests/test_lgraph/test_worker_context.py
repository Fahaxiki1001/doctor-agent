"""tests/test_lgraph/test_worker_context.py — Worker 上下文注入与默认 Skill 预激活

覆盖：
- C0：recent_history 由 Supervisor 显式注入 Worker（追问轮指代解析的唯一通道）
- C1：默认 Skill 预激活，首轮即可见 Skill 工具，无需 activate_skill 独立轮
"""

from typing import Any, Dict, List, Optional

import pytest

from mediZJ.core.llm_client import LLMResponse
from mediZJ.core.skill_registry import SkillParameter
from mediZJ.lgraph.agent_subgraph import build_agent_subgraph
from mediZJ.lgraph.tool_registry import ToolRegistry, VisibleTool


class _CapturingLLMClient:
    """记录每轮 messages / tools，并返回无 tool_calls 的终止响应。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def chat_with_tools_retry(self, messages, tools=None, **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, "tools": tools})
        return LLMResponse(content="最终回答", tool_calls=[], finish_reason="stop")


class _FakeWorker:
    def __init__(self, default_skill: Optional[str] = None) -> None:
        self.agent_id = "consultation_agent"
        self.llm_client = _CapturingLLMClient()
        self.config = {"temperature": 0.7, "max_iterations": 5}
        self.default_skill = default_skill
        self.short_term_memory = None
        self.user_context = None
        self.on_thinking = None
        self.on_tool_step = None
        self.on_thinking_done = None
        self.on_content_token = None

    def get_base_system_prompt_stable(self) -> str:
        return "你是问诊助手。"

    def format_user_input(self, input_data: Dict[str, Any]) -> str:
        return input_data.get("question", "")

    async def post_process_result(self, result, final_response):
        return result


def _make_registry() -> ToolRegistry:
    async def _search_knowledge(query: str) -> Dict[str, Any]:
        return {"success": True, "references": []}

    registry = ToolRegistry()
    registry.register(VisibleTool(
        func=_search_knowledge,
        name="search_knowledge",
        description="检索医学知识库",
        parameters=[SkillParameter("query", "string", "检索词", True)],
        visible_in=["search_knowledge"],
        skill_instructions="按症状关键词检索，空结果不重试。",
    ))
    registry.register_base_tool(
        name="activate_skill",
        func=lambda name: {"success": True},
        description="激活技能",
        parameters=[SkillParameter("name", "string", "技能名", True)],
    )
    return registry


async def _run(worker: _FakeWorker, state: Dict[str, Any]) -> Dict[str, Any]:
    graph = build_agent_subgraph(worker=worker, tool_registry=_make_registry())
    base = {
        "agent_id": worker.agent_id,
        "session_id": "s1",
        "sub_session_id": "s1:consultation_agent:rule",
        "question": "那要吃多久",
        "subtask_description": "那要吃多久",
    }
    base.update(state)
    return await graph.ainvoke(base)


def _system_contents(worker: _FakeWorker) -> List[str]:
    first_call = worker.llm_client.calls[0]["messages"]
    return [m["content"] for m in first_call if m.get("role") == "system"]


class TestRecentHistoryInjection:
    """C0：recent_history 注入。"""

    @pytest.mark.asyncio
    async def test_history_injected_as_system_message(self):
        worker = _FakeWorker()
        await _run(worker, {"recent_history": [
            {"role": "user", "content": "布洛芬能治头痛吗"},
            {"role": "assistant", "content": "可以短期缓解"},
        ]})
        joined = "\n".join(_system_contents(worker))
        assert "最近对话" in joined
        assert "布洛芬能治头痛吗" in joined
        assert "可以短期缓解" in joined

    @pytest.mark.asyncio
    async def test_history_truncated_to_last_five(self):
        worker = _FakeWorker()
        await _run(worker, {"recent_history": [
            {"role": "user", "content": f"msg-{i}"} for i in range(8)
        ]})
        joined = "\n".join(_system_contents(worker))
        assert "msg-0" not in joined
        assert "msg-2" not in joined
        assert "msg-3" in joined
        assert "msg-7" in joined

    @pytest.mark.asyncio
    async def test_no_history_no_injection(self):
        worker = _FakeWorker()
        await _run(worker, {})
        assert all("最近对话" not in c for c in _system_contents(worker))

    @pytest.mark.asyncio
    async def test_history_and_collected_info_are_separate_messages(self):
        worker = _FakeWorker()
        await _run(worker, {
            "recent_history": [{"role": "user", "content": "上次说的药"}],
            "collected_info": "已服药 3 天",
        })
        contents = _system_contents(worker)
        assert sum("最近对话" in c for c in contents) == 1
        assert sum("本轮已确认的用户信息" in c for c in contents) == 1

    @pytest.mark.asyncio
    async def test_malformed_history_entries_ignored(self):
        worker = _FakeWorker()
        await _run(worker, {"recent_history": ["not-a-dict", None]})
        assert all("最近对话" not in c for c in _system_contents(worker))


class TestDefaultSkillPreactivation:
    """C1：默认 Skill 预激活。"""

    @pytest.mark.asyncio
    async def test_first_round_sees_skill_tool(self):
        worker = _FakeWorker(default_skill="search_knowledge")
        await _run(worker, {})
        tool_names = {
            t["function"]["name"] for t in (worker.llm_client.calls[0]["tools"] or [])
        }
        assert "search_knowledge" in tool_names

    @pytest.mark.asyncio
    async def test_skill_instructions_injected(self):
        worker = _FakeWorker(default_skill="search_knowledge")
        await _run(worker, {})
        joined = "\n".join(_system_contents(worker))
        assert "技能说明：search_knowledge" in joined
        assert "空结果不重试" in joined

    @pytest.mark.asyncio
    async def test_without_default_skill_only_base_tools(self):
        worker = _FakeWorker(default_skill=None)
        await _run(worker, {})
        tool_names = {
            t["function"]["name"] for t in (worker.llm_client.calls[0]["tools"] or [])
        }
        assert tool_names == {"activate_skill"}

    @pytest.mark.asyncio
    async def test_unknown_default_skill_degrades_silently(self):
        worker = _FakeWorker(default_skill="not_a_skill")
        await _run(worker, {})
        tool_names = {
            t["function"]["name"] for t in (worker.llm_client.calls[0]["tools"] or [])
        }
        assert tool_names == {"activate_skill"}
        assert all("技能说明" not in c for c in _system_contents(worker))
