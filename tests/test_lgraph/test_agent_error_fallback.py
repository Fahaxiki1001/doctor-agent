"""tests/test_lgraph/test_agent_error_fallback.py — LLM 异常兜底文案保真

覆盖：
- 工具执行后 LLM 报错：兜底文案不被 ToolMessage 内容覆盖
- 首轮即报错：消息尾部非 assistant，兜底文案同样保留
- 正常结束：final_answer 仍取 assistant 正文，守卫不过度拦截
"""

from typing import Any, Dict, List

import pytest

from mediZJ.core.llm_client import LLMResponse, ToolCall
from mediZJ.core.skill_registry import SkillParameter
from mediZJ.lgraph.agent_subgraph import build_agent_subgraph
from mediZJ.lgraph.tool_registry import ToolRegistry, VisibleTool

_FALLBACK = "抱歉，系统在处理您的问题时遇到了问题。请稍后重试。"
_TOOL_JSON = (
    "{'answer': \"未找到关于'发热 退烧药'的相关医学知识\", "
    "'total_found': 0, 'references': []}"
)


class _ScriptedLLMClient:
    """按脚本逐轮返回响应；脚本项为 Exception 时抛出。"""

    def __init__(self, script: List[Any]) -> None:
        self.script = script
        self.call_count = 0

    async def chat_with_tools_retry(self, messages, tools=None, **kwargs) -> LLMResponse:
        item = self.script[self.call_count]
        self.call_count += 1
        if isinstance(item, Exception):
            raise item
        return item


class _FakeWorker:
    def __init__(self, script: List[Any]) -> None:
        self.agent_id = "consultation_agent"
        self.llm_client = _ScriptedLLMClient(script)
        self.config = {"temperature": 0.7, "max_iterations": 5}
        self.default_skill = "search_knowledge"
        self.short_term_memory = None
        self.user_context = None
        self.on_thinking = None
        self.on_tool_step = None
        self.on_thinking_done = None
        self.on_content_token = None
        self.post_processed: List[str] = []

    def get_base_system_prompt_stable(self) -> str:
        return "你是问诊助手。"

    def format_user_input(self, input_data: Dict[str, Any]) -> str:
        return input_data.get("question", "")

    async def post_process_result(self, result, final_response):
        self.post_processed.append(final_response)
        return result


def _make_registry() -> ToolRegistry:
    async def _search_knowledge(query: str, max_results: int = 3) -> str:
        return _TOOL_JSON

    registry = ToolRegistry()
    registry.register(VisibleTool(
        func=_search_knowledge,
        name="search_knowledge",
        description="检索医学知识库",
        parameters=[SkillParameter("query", "string", "检索词", True)],
        visible_in=["search_knowledge"],
    ))
    return registry


async def _run(worker: _FakeWorker) -> Dict[str, Any]:
    graph = build_agent_subgraph(worker=worker, tool_registry=_make_registry())
    return await graph.ainvoke({
        "agent_id": worker.agent_id,
        "session_id": "s1",
        "sub_session_id": "s1:consultation_agent:rule",
        "question": "如果我想要吃药的话吃什么",
        "subtask_description": "如果我想要吃药的话吃什么",
    })


def _tool_call_response() -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(
            id="c1", name="search_knowledge",
            arguments={"query": "发热 退烧药", "max_results": 3},
        )],
        finish_reason="tool_calls",
    )


@pytest.mark.asyncio
async def test_error_after_tool_keeps_fallback_text():
    """工具执行后 LLM 报错：不得把工具 JSON 当正文返回"""
    worker = _FakeWorker([
        _tool_call_response(),
        RuntimeError("Upstream service temporarily unavailable"),
    ])

    result = await _run(worker)

    assert result["final_answer"] == _FALLBACK
    assert "total_found" not in result["final_answer"]
    assert result["error"] == "Upstream service temporarily unavailable"
    # 异常路径不进 finalize，不应把工具结果送进后处理
    assert worker.post_processed == []


@pytest.mark.asyncio
async def test_error_on_first_round_keeps_fallback_text():
    """首轮即报错：消息尾部是 user/system，兜底文案同样保留"""
    worker = _FakeWorker([RuntimeError("connection reset")])

    result = await _run(worker)

    assert result["final_answer"] == _FALLBACK
    assert worker.llm_client.call_count == 1


@pytest.mark.asyncio
async def test_normal_completion_uses_assistant_content():
    """正常结束：final_answer 仍取 assistant 正文"""
    worker = _FakeWorker([
        LLMResponse(content="建议对症使用对乙酰氨基酚。", tool_calls=[], finish_reason="stop"),
    ])

    result = await _run(worker)

    assert result["final_answer"] == "建议对症使用对乙酰氨基酚。"
    assert worker.post_processed == ["建议对症使用对乙酰氨基酚。"]
