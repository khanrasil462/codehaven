from fastapi import APIRouter
from app.modules.runner.schemas import ExecuteRequest, ExecuteResponse, RuntimeInfo
from app.modules.runner.service import runner_service

router = APIRouter(prefix="/runner", tags=["Code Runner & Compiler"])


@router.get("/runtimes", response_model=list[RuntimeInfo])
async def list_runtimes() -> list[RuntimeInfo]:
    """Returns all installed and supported compiler/interpreter runtimes."""
    return runner_service.get_available_runtimes()


@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(request: ExecuteRequest) -> ExecuteResponse:
    """Safely executes code in the requested language and captures output, errors, and timing."""
    return await runner_service.execute(request)
