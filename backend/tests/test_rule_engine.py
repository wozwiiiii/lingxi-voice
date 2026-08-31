"""TDD tests for rule engine — polyphone detection and symbol detection."""

from app.preprocess.rule_engine import rule_fallback, rule_preprocess


class TestPolyphoneDetection:
    def test_detects_bank(self):
        result = rule_preprocess("我去银行办事")
        assert result.needs_llm is True
        assert any("polyphone:银行" in i for i in result.detected_issues)

    def test_detects_walking(self):
        result = rule_preprocess("我在路上行走")
        assert result.needs_llm is True
        assert any("polyphone:行走" in i for i in result.detected_issues)

    def test_detects_music(self):
        result = rule_preprocess("我喜欢听音乐")
        assert result.needs_llm is True

    def test_detects_multiple_polyphones(self):
        result = rule_preprocess("去银行办事然后再去听音乐")
        assert result.needs_llm is True
        assert len([i for i in result.detected_issues if i.startswith("polyphone:")]) >= 2


class TestMathSymbolDetection:
    def test_detects_partial_derivative(self):
        result = rule_preprocess("∂f/∂x 表示偏导数")
        assert result.needs_llm is True
        assert any("partial_differential" in i for i in result.detected_issues)

    def test_detects_integral(self):
        result = rule_preprocess("∫₀¹ f(x)dx")
        assert result.needs_llm is True
        assert any("integral" in i for i in result.detected_issues)

    def test_detects_summation(self):
        result = rule_preprocess("∑ᵢ₌₁ⁿ xᵢ")
        assert result.needs_llm is True

    def test_detects_square_root(self):
        result = rule_preprocess("√(a² + b²)")
        assert result.needs_llm is True

    def test_detects_infinity(self):
        result = rule_preprocess("x → ∞")
        assert result.needs_llm is True


class TestPlainTextPassthrough:
    def test_plain_text_no_llm_needed(self):
        result = rule_preprocess("今天天气真好，我们去公园散步吧")
        assert result.needs_llm is False
        assert len(result.detected_issues) == 0

    def test_simple_english_no_llm_needed(self):
        result = rule_preprocess("Hello world, how are you today?")
        assert result.needs_llm is False

    def test_empty_text_no_llm_needed(self):
        result = rule_preprocess("")
        assert result.needs_llm is False


class TestChemicalSymbolDetection:
    def test_detects_chemical_formula(self):
        result = rule_preprocess("硫酸的化学式是 H₂SO₄")
        assert result.needs_llm is True
        assert any("chemical" in i for i in result.detected_issues)

    def test_detects_nacl(self):
        result = rule_preprocess("食盐的主要成分是 NaCl")
        assert result.needs_llm is True


class TestRuleFallback:
    """P2-9：LLM 失败后的确定性兜底必须做真实替换。"""

    def test_math_symbols_replaced_with_readings(self):
        assert rule_fallback("∂f/∂x 趋近于 ∞") == "偏导数f/偏导数x 趋近于 无穷大"

    def test_common_chemical_formulas_replaced(self):
        assert rule_fallback("水的化学式是 H₂O") == "水的化学式是 水"
        assert rule_fallback("H₂SO₄ 是硫酸") == "硫酸 是硫酸"

    def test_plain_text_unchanged(self):
        assert rule_fallback("今天天气真好") == "今天天气真好"

    def test_polyphone_kept_as_is(self):
        # 多音字需要上下文语义，兜底时保留原文而非替换成固定读音
        assert rule_fallback("我去银行办事") == "我去银行办事"

    def test_unknown_chemical_formula_kept(self):
        # 不在常见表内的化学式无法本地确定名称，保留原文
        assert rule_fallback("Fe₂O₃ 是氧化铁") == "Fe₂O₃ 是氧化铁"
