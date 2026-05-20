from pathlib import Path
from typing import Any

import json


def load_prompt(prompt_file_path: Path, prompt_number: int) -> str:
    text = prompt_file_path.read_text(encoding="utf-8")
    marker = f"# Prompt {prompt_number}"
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"Prompt {prompt_number} not found in {prompt_file_path}")

    next_marker = text.find("# Prompt ", start + len(marker))
    if next_marker == -1:
        return text[start:].strip()
    return text[start:next_marker].strip()


def render_prompt(prompt_template: str, variables: dict[str, Any]) -> str:
    rendered = prompt_template
    for key, value in variables.items():
        if isinstance(value, str):
            replacement = value
        else:
            replacement = json.dumps(value, ensure_ascii=False, default=str)
        rendered = rendered.replace("{{" + key + "}}", replacement)
    return rendered
