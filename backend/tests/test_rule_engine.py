"""TDD tests for rule engine — polyphone detection and symbol detection."""

from app.preprocess.rule_engine import rule_preprocess


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
