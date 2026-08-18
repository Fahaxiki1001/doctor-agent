"""tests/test_api/test_latency_metrics.py — 延迟指标不含问卷等待时间

问卷挂起期间是用户填写时间，不属于系统耗时。指标一旦把它算进去，
后续所有性能判断都会跑偏（首 token 29.6s 里曾有 12.4s 是用户打字）。
"""
import asyncio
import json

import mediZJ.api.services.chat_service as cs
from mediZJ.api.models.chat import ChatRequest
from mediZJ.swarm.events import Event, EventType

# 模拟的问卷填写时长；断言时以此为下界判断是否被扣除
WAIT_SECONDS = 0.3


class _FakeRequest:
    """模拟永不主动断开的 HTTP 请求"""

    async def is_disconnected(self) -> bool:
        return False


class _BaseCoordinator:
    """产出一个最终 token 后结束的最小协调器"""

    def __init__(self, **kwargs):
        del kwargs
        self.ltm_save_task = None
        self.event_callback = None
        self.composed_wait = None

    def build_graph(self, event_callback=None, hitl_enabled=False):
        del hitl_enabled
        self.event_callback = event_callback
        return object()

    def _init_trace(self, _trace_id):
        return object()

    async def _flush_trace(self, *_args):
        return None

    def build_initial_state(self, question, context, session_id, start_time):
        del context, start_time
        return {"question": question, "session_id": session_id}

    def _emit_final_token(self):
        self.event_callback(Event(
            type=EventType.AGENT_CONTENT_DELTA,
            source_agent="consultation_agent",
            data={"token": "最终回答", "is_final": True},
        ))

    def compose_result(self, question, result_state, start_time, session_id,
                       trace_id=None, excluded_wait_seconds=0.0):
        del question, start_time, session_id, trace_id
        self.composed_wait = excluded_wait_seconds
        result_state["_ltm_save_task"] = None
        return result_state

    @staticmethod
    def _done_state(session_id):
        return {
            "answer": "最终回答",
            "final_answer": "最终回答",
            "session_id": session_id,
            "suggestions": [],
            "usage": {},
            "agents_involved": ["consultation_agent"],
            "swarm_enabled": False,
        }


def _ttft(chunks):
    done = json.loads(chunks[-1])
    assert done["event"] == "done"
    return done["data"]["time_to_first_token"]


async def _drain(session_id, question="q"):
    return [
        chunk
        async for chunk in cs.chat_stream(
            ChatRequest(question=question, session_id=session_id),
            _FakeRequest(),
        )
    ]


async def test_ttft_excludes_questionnaire_wait(monkeypatch):
    """单轮问卷：等待时长不计入首 token"""

    class OneRoundCoordinator(_BaseCoordinator):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._resumed = False

        async def run_graph(self, graph, initial_state, config, resume=None):
            del graph, config
            if resume is None:
                return {"_interrupted": True}
            self._resumed = True
            self._emit_final_token()
            await asyncio.sleep(0)
            return self._done_state(initial_state["session_id"])

    holder = {}

    def _factory(**kwargs):
        holder["coordinator"] = OneRoundCoordinator(**kwargs)
        return holder["coordinator"]

    monkeypatch.setattr(cs, "SwarmCoordinator", _factory)
    monkeypatch.setattr(cs, "_persist_session_turn", lambda *a, **k: None)

    from mediZJ.api.services.session_runtime import put_answer

    async def _feed():
        await asyncio.sleep(WAIT_SECONDS)
        put_answer("s-ttft-wait", {"q0": "35"})

    feed = asyncio.create_task(_feed())
    chunks = await _drain("s-ttft-wait")
    await feed

    ttft = _ttft(chunks)
    assert ttft is not None
    # 等待时长已扣除：净耗时远小于等待时长本身
    assert ttft < WAIT_SECONDS
    # 扣除量传给了 compose_result，用于同步修正 total_time
    assert holder["coordinator"].composed_wait >= WAIT_SECONDS


async def test_ttft_unchanged_without_questionnaire(monkeypatch):
    """无问卷路径：指标口径不变，仍为真实净耗时"""

    class DirectCoordinator(_BaseCoordinator):
        async def run_graph(self, graph, initial_state, config, resume=None):
            del graph, config, resume
            self._emit_final_token()
            await asyncio.sleep(0)
            return self._done_state(initial_state["session_id"])

    holder = {}

    def _factory(**kwargs):
        holder["coordinator"] = DirectCoordinator(**kwargs)
        return holder["coordinator"]

    monkeypatch.setattr(cs, "SwarmCoordinator", _factory)
    monkeypatch.setattr(cs, "_persist_session_turn", lambda *a, **k: None)

    chunks = await _drain("s-ttft-direct")

    ttft = _ttft(chunks)
    assert ttft is not None
    assert ttft >= 0
    assert holder["coordinator"].composed_wait == 0.0


async def test_ttft_accumulates_multiple_questionnaire_rounds(monkeypatch):
    """多轮问卷：每轮等待都被扣除"""

    class TwoRoundCoordinator(_BaseCoordinator):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._resume_count = 0

        async def run_graph(self, graph, initial_state, config, resume=None):
            del graph, config
            if resume is None or self._resume_count < 2:
                self._resume_count += 1
                return {"_interrupted": True}
            self._emit_final_token()
            await asyncio.sleep(0)
            return self._done_state(initial_state["session_id"])

    holder = {}

    def _factory(**kwargs):
        holder["coordinator"] = TwoRoundCoordinator(**kwargs)
        return holder["coordinator"]

    monkeypatch.setattr(cs, "SwarmCoordinator", _factory)
    monkeypatch.setattr(cs, "_persist_session_turn", lambda *a, **k: None)

    from mediZJ.api.services.session_runtime import put_answer

    async def _feed():
        await asyncio.sleep(WAIT_SECONDS)
        put_answer("s-ttft-multi", {"q0": "35"})
        await asyncio.sleep(WAIT_SECONDS)
        put_answer("s-ttft-multi", {"q0": "头痛一天"})

    feed = asyncio.create_task(_feed())
    chunks = await _drain("s-ttft-multi")
    await feed

    ttft = _ttft(chunks)
    assert ttft is not None
    # 两轮等待共 2*WAIT_SECONDS，全部扣除后净耗时应小于单轮等待
    assert ttft < WAIT_SECONDS
    assert holder["coordinator"].composed_wait >= 2 * WAIT_SECONDS


async def test_compose_result_excludes_wait_and_never_negative():
    """compose_result 扣除等待且不返回负数；默认值行为不变"""
    from datetime import datetime, timedelta
    from mediZJ.swarm.swarm_coordinator import SwarmCoordinator

    start = datetime.now() - timedelta(seconds=10)
    state = {"total_time": 10.0, "final_answer": "a", "suggestions": []}

    def _compose(session_id, **kwargs):
        result = SwarmCoordinator.compose_result(
            object.__new__(SwarmCoordinator), "q", dict(state), start, session_id,
            **kwargs,
        )
        # LTM 是 fire-and-forget，测试里取消掉避免悬挂协程
        task = result.get("_ltm_save_task")
        if task is not None:
            task.cancel()
        return result

    assert _compose("s1")["total_time"] == 10.0
    assert _compose("s2", excluded_wait_seconds=4.0)["total_time"] == 6.0
    assert _compose("s3", excluded_wait_seconds=999.0)["total_time"] == 0.0
    await asyncio.sleep(0)
