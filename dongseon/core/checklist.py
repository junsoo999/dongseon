"""The preparation checklist template (``config/checklist.yaml``)."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ChecklistTemplateItem(BaseModel):
    """One template line, with an optional official page to check."""

    text: str = Field(min_length=1, max_length=200)
    url: str | None = None


class ChecklistSection(BaseModel):
    """A named group of template lines."""

    name: str
    items: list[ChecklistTemplateItem]


class ChecklistTemplate(BaseModel):
    """The whole template."""

    as_of: date
    sections: list[ChecklistSection]


def load_checklist(path: Path) -> ChecklistTemplate:
    """Load and validate the checklist template.

    Args:
        path: The template YAML.

    Returns:
        The parsed template.
    """
    return ChecklistTemplate.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
