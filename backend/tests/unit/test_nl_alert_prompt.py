from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "app" / "templates" / "prompts"


def test_nl_alert_prompt_template_exists():
    template_path = TEMPLATE_DIR / "nl_alert.j2"
    assert template_path.exists(), f"Prompt template not found: {template_path}"


def test_nl_alert_prompt_contains_required_placeholders():
    template_path = TEMPLATE_DIR / "nl_alert.j2"
    content = template_path.read_text(encoding="utf-8")
    assert "{{ query }}" in content
    assert "condition_type" in content
    assert "threshold" in content
    assert "confidence" in content


def test_nl_alert_prompt_renders_with_sample_query():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("nl_alert.j2")
    rendered = template.render(query="茅台跌破 1500 提醒我")
    assert "茅台跌破 1500 提醒我" in rendered
    assert "JSON" in rendered
