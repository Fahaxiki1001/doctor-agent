"""引用与正文对齐：只保留正文真正引用过的来源"""
from mediZJ.swarm.swarm_coordinator import (
    filter_used_citations,
    used_citation_indexes,
)


def _cites(*indexes):
    return [{"index": i, "filename": f"doc{i}.txt"} for i in indexes]


class TestUsedCitationIndexes:
    def test_single_index(self):
        assert used_citation_indexes("低盐饮食[1]。") == {1}

    def test_multiple_in_one_marker(self):
        assert used_citation_indexes("研究表明有效[1,2]。") == {1, 2}

    def test_fullwidth_comma(self):
        assert used_citation_indexes("研究表明有效[1，2]。") == {1, 2}

    def test_spaces_inside_marker(self):
        assert used_citation_indexes("有效[1, 3]。") == {1, 3}

    def test_multiple_markers(self):
        assert used_citation_indexes("A[1]。B[3]。") == {1, 3}

    def test_no_citation(self):
        assert used_citation_indexes("先用对乙酰氨基酚，注意别叠加。") == set()

    def test_empty_text(self):
        assert used_citation_indexes("") == set()
        assert used_citation_indexes(None) == set()

    def test_range_not_supported(self):
        """区间写法当前不支持（prompt 只要求 [N] / [N,M]）"""
        assert used_citation_indexes("有效[1-3]。") == set()


class TestFilterUsedCitations:
    def test_no_citation_in_text_returns_empty(self):
        assert filter_used_citations("正文没有任何引用标注", _cites(1, 2, 3)) == []

    def test_keeps_only_used(self):
        kept = filter_used_citations("低盐饮食[1]。", _cites(1, 2, 3))
        assert [c["index"] for c in kept] == [1]

    def test_index_not_renumbered(self):
        """正文里的 [3] 必须保留编号 3，不能被重排成 1"""
        kept = filter_used_citations("参考建议[3]。", _cites(1, 2, 3))
        assert [c["index"] for c in kept] == [3]
        assert kept[0]["filename"] == "doc3.txt"

    def test_multi_index_marker(self):
        kept = filter_used_citations("有效[1,3]。", _cites(1, 2, 3))
        assert [c["index"] for c in kept] == [1, 3]

    def test_out_of_range_index_adds_nothing(self):
        """模型凭空写 [9] 时不新增条目，也不报错"""
        assert filter_used_citations("有效[9]。", _cites(1, 2)) == []

    def test_empty_citations(self):
        assert filter_used_citations("有效[1]。", []) == []
        assert filter_used_citations("有效[1]。", None) == []

    def test_all_used_keeps_all(self):
        kept = filter_used_citations("A[1]。B[2]。C[3]。", _cites(1, 2, 3))
        assert [c["index"] for c in kept] == [1, 2, 3]
