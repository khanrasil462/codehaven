from enum import Enum

from pydantic import BaseModel, Field


class CodeLanguage(str, Enum):
    python = "python"
    javascript = "javascript"
    typescript = "typescript"
    react = "react"
    java = "java"
    c = "c"
    cpp = "cpp"
    powershell = "powershell"
    bash = "bash"


class CodegenRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    language: CodeLanguage = CodeLanguage.python
    include_explanation: bool = True
    stream: bool = True
    model: str | None = None


class CodegenResponse(BaseModel):
    code: str
    explanation: str | None = None
    language: str
    model: str
