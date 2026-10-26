from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    code: str = Field(..., description="Source code to compile and execute")
    language: str = Field("python", description="Programming language: python, javascript, typescript, java, c, cpp, powershell")
    stdin: str = Field("", description="Simulated standard input passed to program")
    timeout_seconds: float = Field(10.0, ge=1.0, le=30.0, description="Maximum execution timeout in seconds")


class RuntimeInfo(BaseModel):
    id: str
    name: str
    version: str
    available: bool
    extension: str
    example_code: str


class ExecuteResponse(BaseModel):
    status: str = Field(..., description="'success', 'error', or 'timeout'")
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    language: str
    runtime_version: str = ""
