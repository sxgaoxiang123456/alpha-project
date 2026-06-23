import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class PromptLoader:
    """加载并渲染 Jinja2 Prompt 模板。"""

    DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "prompts"
    TEMPLATE_NAME = "briefing.j2"

    def __init__(self, template_dir: Path | str | None = None):
        self.template_dir = Path(
            template_dir or os.environ.get("PROMPT_TEMPLATE_DIR", self.DEFAULT_TEMPLATE_DIR)
        )
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=False,
        )

    def render(
        self,
        *,
        today: str = "",
        market_indices: dict | None = None,
        top_movers: list[dict] | None = None,
        alert_history: list[str] | None = None,
    ) -> str:
        """渲染简报 Prompt。"""
        try:
            template = self._env.get_template(self.TEMPLATE_NAME)
        except TemplateNotFound as exc:
            raise RuntimeError(
                f"Prompt 模板未找到: {self.template_dir / self.TEMPLATE_NAME}"
            ) from exc

        return template.render(
            today=today,
            market_indices=market_indices or {},
            top_movers=top_movers or [],
            alert_history=alert_history or [],
        )
