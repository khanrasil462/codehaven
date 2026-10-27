LANGUAGE_HINTS: dict[str, str] = {
    "python": "Use Python 3.11+, type hints where helpful, PEP 8 style.",
    "javascript": "Use modern ES modules, Node.js compatible unless browser-only.",
    "typescript": "Use strict TypeScript with explicit types.",
    "react": "Use functional components with hooks; include necessary imports.",
    "java": "Use a single public class Main with a main method; no packages.",
    "c": "Use C11 with stdio.h; a single file with int main.",
    "cpp": "Use C++17 with a single file and int main.",
    "powershell": "Use PowerShell 7 compatible script.",
    "bash": "Use portable bash with a shebang.",
}


def build_codegen_messages(
    prompt: str,
    language: str,
    include_explanation: bool,
) -> list[dict[str, str]]:
    explanation_rule = (
        "After the code block, add a brief explanation (2-4 sentences)."
        if include_explanation
        else "Return ONLY a single fenced code block — no prose before or after."
    )
    system = (
        "You are CodeHaven, an offline code generator for students. "
        f"Target language: {language}. {LANGUAGE_HINTS[language]} "
        f"Output one ```{language} ... ``` fenced block with complete, runnable code. "
        f"{explanation_rule} "
        "Do not invent external APIs or packages unless standard library or commonly installed."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
