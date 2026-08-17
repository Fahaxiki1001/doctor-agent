"""test_swarm/test_clarify_context_and_format.py

覆盖本次修复的两个缺陷：
- `_build_clarify_context` 写入近期对话正文（非仅计数），供 clarify 判断已知信息
- 单 Agent 直出与综合层共用 `_output_format.j2`，均含固定核心建议标题
- `extract_suggestions` 能解析带 emoji 的核心建议标题
"""

from mediZJ.lgraph.supervisor_graph import _build_clarify_context


class TestBuildClarifyContext:
    def test_includes_recent_history_content(self):
        state = {
            "recent_history": [
                {"role": "user", "content": "我今天有点发烧，不知道是不是阳了"},
                {"role": "assistant", "content": "建议先做抗原检测"},
            ],
        }
        ctx = _build_clarify_context(state)
        assert "发烧" in ctx
        assert "抗原检测" in ctx
        # 不再是仅计数
        assert "条消息" not in ctx

    def test_truncates_long_message(self):
        long_text = "症" * 500
        state = {"recent_history": [{"role": "user", "content": long_text}]}
        ctx = _build_clarify_context(state)
        assert "…" in ctx
        assert len(ctx) < 500

    def test_keeps_only_last_six_messages(self):
        history = [
            {"role": "user", "content": f"消息{i}"} for i in range(10)
        ]
        state = {"recent_history": history}
        ctx = _build_clarify_context(state)
        assert "消息9" in ctx
        assert "消息3" not in ctx  # 第 4 条之前被裁掉

    def test_empty_history_returns_none_marker(self):
        assert _build_clarify_context({}) == "无"

    def test_similar_memories_only_counted(self):
        state = {"similar_memories": [{"a": 1}, {"b": 2}]}
        ctx = _build_clarify_context(state)
        assert "历史相似案例: 2 个" in ctx


class TestOutputFormatShared:
    def test_consultation_and_synthesis_share_headings(self):
        from mediZJ.core.prompt_loader import PromptLoader

        consultation = PromptLoader.render("agents/consultation_system.j2")
        synthesis = PromptLoader.render(
            "swarm/synthesis.j2",
            question="q",
            contributions_text=["c"],
            timeout_note="",
            timeout_occurred=False,
        )
        for text in (consultation, synthesis):
            assert "## ✅ 核心建议" in text
            assert "## ⚠️ 风险评估" in text
            assert "## 🔍 诊断分析" in text
            assert "## 📚 医学证据" in text


class TestExtractSuggestionsWithEmoji:
    def test_parses_emoji_heading(self):
        from mediZJ.swarm.swarm_coordinator import SwarmCoordinator

        answer = "结论先行。\n\n## ✅ 核心建议\n1. 多喝水\n2. 充分休息\n"
        assert SwarmCoordinator.extract_suggestions(answer) == ["多喝水", "充分休息"]

    def test_backward_compatible_plain_heading(self):
        from mediZJ.swarm.swarm_coordinator import SwarmCoordinator

        answer = "## 核心建议\n1. 旧格式\n"
        assert SwarmCoordinator.extract_suggestions(answer) == ["旧格式"]
