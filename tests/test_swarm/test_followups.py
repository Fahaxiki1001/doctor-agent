"""followups 标记块解析、流式过滤与建议回退的单测"""
from mediZJ.swarm.swarm_coordinator import (
    SwarmCoordinator,
    parse_followups,
    split_marker_stream,
)


class TestParseFollowups:
    def test_parse_and_strip(self):
        text = (
            "发热先用对乙酰氨基酚。\n"
            "<!--followups: 我现在38.5℃该吃药吗？|布洛芬和对乙酰氨基酚哪个更适合我？|"
            "什么情况下必须去医院？-->"
        )
        clean, items = parse_followups(text)
        assert "followups" not in clean
        assert clean == "发热先用对乙酰氨基酚。"
        assert items == [
            "我现在38.5℃该吃药吗？",
            "布洛芬和对乙酰氨基酚哪个更适合我？",
            "什么情况下必须去医院？",
        ]

    def test_no_marker_returns_original(self):
        text = "## ✅ 核心建议\n1. 多喝水\n"
        clean, items = parse_followups(text)
        assert clean == text
        assert items == []

    def test_at_most_three_items(self):
        text = "正文<!--followups: A|B|C|D|E-->"
        _, items = parse_followups(text)
        assert items == ["A", "B", "C"]

    def test_empty_input(self):
        assert parse_followups("") == ("", [])


class TestSplitMarkerStream:
    def test_plain_text_passes_through(self):
        assert split_marker_stream("正常正文") == ("正常正文", "")

    def test_holds_partial_open_prefix(self):
        emit, hold = split_marker_stream("正文<!-")
        assert emit == "正文"
        assert hold == "<!-"

    def test_holds_until_close(self):
        emit, hold = split_marker_stream("正文<!--followups: A|B")
        assert emit == "正文"
        assert hold == "<!--followups: A|B"

    def test_drops_complete_marker(self):
        emit, hold = split_marker_stream("正文<!--followups: A|B|C-->尾巴")
        assert emit == "正文尾巴"
        assert hold == ""

    def test_token_by_token_stream_never_leaks_marker(self):
        answer = "先用对乙酰氨基酚。<!--followups: A|B|C-->"
        hold = ""
        emitted = []
        for ch in answer:
            out, hold = split_marker_stream(hold + ch)
            emitted.append(out)
        assert "".join(emitted) == "先用对乙酰氨基酚。"
        assert hold == ""


class TestExtractSuggestions:
    def test_prefers_followups(self):
        answer = "## ✅ 核心建议\n1. 多喝水\n2. 休息\n<!--followups: X？|Y？|Z？-->"
        assert SwarmCoordinator.extract_suggestions(answer) == ["X？", "Y？", "Z？"]

    def test_falls_back_to_core_advice_emoji_header(self):
        answer = "## ✅ 核心建议\n1. 多喝水\n2. 休息\n"
        assert SwarmCoordinator.extract_suggestions(answer) == ["多喝水", "休息"]

    def test_falls_back_to_legacy_header(self):
        answer = "【核心建议】\n1. 多喝水\n"
        assert SwarmCoordinator.extract_suggestions(answer) == ["多喝水"]

    def test_default_when_nothing_matches(self):
        assert SwarmCoordinator.extract_suggestions("无结构文本") == [
            "请遵循医嘱，注意休息和营养"
        ]
