"""The shared LLM-call seam and prompt building in src/generation/nodes."""

from types import SimpleNamespace

from src.config import get_settings


class TestPromptChunkCap:
    def test_generate_and_verify_prompts_cap_chunk_text(self):
        from src.generation.nodes.core import _build_generate_messages, _build_verify_prompt

        get_settings.cache_clear()
        cap = get_settings().prompt_chunk_char_cap
        chunks = [{"spec_id": "23.501", "clause_id": "1", "content": "y" * (cap * 2)}]
        gen = _build_generate_messages("q", chunks, "")[1]["content"]
        ver = _build_verify_prompt("a", chunks)
        assert "y" * cap in gen and "y" * (cap + 1) not in gen
        assert "y" * cap in ver and "y" * (cap + 1) not in ver


class TestMixedGenerationNote:
    def test_note_lists_both_generations_terms(self):
        from src.generation.nodes.core import _build_generate_messages

        user = _build_generate_messages("q", [], "", generation_terms={"4g": ["MME"], "5g": ["UDM"]})[1]["content"]
        assert "<NOTE>" in user and "MME" in user and "UDM" in user

    def test_no_note_for_single_generation(self):
        from src.generation.nodes.core import _build_generate_messages

        assert "<NOTE>" not in _build_generate_messages("q", [], "")[1]["content"]


class TestReasoningEffort:
    def test_effort_sent_to_openrouter_only(self, monkeypatch):
        from src.generation import nodes as gen_nodes
        from src.generation.nodes import core
        from src.generation.nodes.llm import chat_completion

        seen = []

        def create(**kwargs):
            seen.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

        monkeypatch.setattr(gen_nodes.client.chat.completions, "create", create)
        msgs = [{"role": "user", "content": "q"}]

        monkeypatch.setattr(core, "LLM_PROVIDER", "openrouter")
        chat_completion(msgs, max_tokens=10, reasoning_effort="low")
        assert seen[-1]["extra_body"] == {"reasoning": {"effort": "low"}}

        monkeypatch.setattr(core, "LLM_PROVIDER", "ollama")
        chat_completion(msgs, max_tokens=10, reasoning_effort="low")
        assert "extra_body" not in seen[-1]
