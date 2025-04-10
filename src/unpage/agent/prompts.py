from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_yaml import parse_yaml_file_as


class Prompt(BaseModel):
    trigger: str = Field(description="A description of when this prompt should be used")
    runbook: str = Field(description="The runbook for this prompt")


PROMPTS_DIR = Path(__file__).parent
PROMPT_FILES = list(PROMPTS_DIR.glob("**/*.yaml"))
ALL_PROMPTS = {f.stem: parse_yaml_file_as(Prompt, f) for f in PROMPT_FILES}
