"""Tests for service modules."""
import pytest
from app.services.persona_manager import get_persona, list_personas, get_default_personas
from app.services.prompt_manager import render_prompt
from app.services.distillation import select_stills_for_content_type, group_stills_by_type
from app.services.ai_client import calculate_openrouter_cost


class TestPersonaManager:
    """Tests for persona manager."""

    @pytest.mark.asyncio
    async def test_get_default_personas(self):
        """Test getting default personas."""
        personas = get_default_personas()
        assert "personas" in personas
        assert len(personas["personas"]) == 3

    @pytest.mark.asyncio
    async def test_list_personas(self):
        """Test listing all personas."""
        personas = await list_personas()
        assert len(personas) >= 3

    @pytest.mark.asyncio
    async def test_get_persona_by_id(self):
        """Test getting specific persona."""
        persona = await get_persona("ceo_longterm_care")
        assert persona is not None
        assert persona["title"] == "CEO of Long-Term Care Facility"
        assert "pain_points" in persona
        assert "priorities" in persona

    @pytest.mark.asyncio
    async def test_get_nonexistent_persona(self):
        """Test getting non-existent persona."""
        persona = await get_persona("nonexistent_persona")
        assert persona is None


class TestPromptManager:
    """Tests for prompt manager."""

    def test_render_prompt_simple(self):
        """Test simple prompt rendering."""
        template = "Hello {name}, welcome to {place}!"
        result = render_prompt(template, {"name": "User", "place": "ContentMultiplier"})
        assert result == "Hello User, welcome to ContentMultiplier!"

    def test_render_prompt_missing_variable(self):
        """Test rendering with missing variable."""
        template = "Hello {name}, your role is {role}."
        with pytest.raises(ValueError):
            render_prompt(template, {"name": "User"})

    def test_render_prompt_multiline(self):
        """Test multiline prompt rendering."""
        template = """
        Target: {persona}
        Pain points: {pain_points}
        Task: Generate content
        """
        result = render_prompt(template, {
            "persona": "CEO",
            "pain_points": "staffing, costs",
        })
        assert "Target: CEO" in result
        assert "Pain points: staffing, costs" in result


class TestDistillation:
    """Tests for distillation helpers."""

    def test_select_stills_for_linkedin(self, sample_stills):
        """Test selecting stills for LinkedIn."""
        selected = select_stills_for_content_type(
            sample_stills, "linkedin", "ceo_longterm_care", count=2
        )
        assert len(selected) <= 2
        # Data stills should be preferred for LinkedIn
        types = [a["still_type"] for a in selected]
        assert "data" in types or "insight" in types

    def test_select_stills_for_blog(self, sample_stills):
        """Test selecting stills for blog."""
        selected = select_stills_for_content_type(
            sample_stills, "blog", "ceo_longterm_care", count=3
        )
        assert len(selected) <= 3

    def test_group_stills_by_type(self, sample_stills):
        """Test grouping stills by type."""
        grouped = group_stills_by_type(sample_stills)

        assert "data" in grouped
        assert "story" in grouped
        assert "insight" in grouped
        assert "problem" in grouped
        assert "solution" in grouped

        assert len(grouped["data"]) == 1
        assert len(grouped["story"]) == 1
        assert len(grouped["insight"]) == 1

    def test_empty_stills(self):
        """Test with empty stills list."""
        selected = select_stills_for_content_type([], "linkedin", "ceo_longterm_care")
        assert len(selected) == 0

        grouped = group_stills_by_type([])
        assert all(len(v) == 0 for v in grouped.values())


class TestCostCalculation:
    """Tests for cost calculation."""

    def test_calculate_cost_gemini_flash(self):
        """Test cost calculation for Gemini Flash."""
        cost = calculate_openrouter_cost("google/gemini-2.0-flash", 1000000, 500000)
        expected = (1000000 / 1000000) * 0.10 + (500000 / 1000000) * 0.40
        assert cost == pytest.approx(expected)

    def test_calculate_cost_claude_sonnet(self):
        """Test cost calculation for Claude Sonnet."""
        cost = calculate_openrouter_cost("anthropic/claude-3.5-sonnet", 10000, 5000)
        expected = (10000 / 1000000) * 3.00 + (5000 / 1000000) * 15.00
        assert cost == pytest.approx(expected)

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model uses default."""
        cost = calculate_openrouter_cost("unknown-model", 1000, 1000)
        # Uses default pricing: input=0.50, output=2.00 per 1M tokens
        expected = (1000 / 1000000) * 0.50 + (1000 / 1000000) * 2.00
        assert cost == pytest.approx(expected)

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        cost = calculate_openrouter_cost("google/gemini-2.0-flash", 0, 0)
        assert cost == 0.0
