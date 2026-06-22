import re
from llm.parser import LLMPlanValidationError


def strip_comments(content: str) -> str:
    """
    OpenSCAD 주석(// 및 /* */)을 제거하는 경량 상태 머신입니다.
    double-quoted string 내부의 주석형 문자(예: "http://...")나 이스케이프 문자(\")는 문자열로 취급하여 보호합니다.
    """
    result = []
    i = 0
    n = len(content)
    state = "normal"  # normal, in_string, in_line_comment, in_block_comment

    while i < n:
        char = content[i]
        if state == "normal":
            if char == '"':
                state = "in_string"
                result.append(char)
            elif char == "/" and i + 1 < n and content[i + 1] == "/":
                state = "in_line_comment"
                i += 1  # '/' skip
            elif char == "/" and i + 1 < n and content[i + 1] == "*":
                state = "in_block_comment"
                i += 1  # '*' skip
            else:
                result.append(char)
        elif state == "in_string":
            if char == '"':
                # check for backslash escapes before the quote
                backslash_count = 0
                k = len(result) - 1
                while k >= 0 and result[k] == "\\":
                    backslash_count += 1
                    k -= 1
                if backslash_count % 2 == 0:
                    state = "normal"
            result.append(char)
        elif state == "in_line_comment":
            if char == "\n":
                state = "normal"
                result.append(char)  # 개행을 보존하여 라인 기반 분석의 깨짐 방지
        elif state == "in_block_comment":
            if char == "*" and i + 1 < n and content[i + 1] == "/":
                state = "normal"
                i += 1  # '/' skip
        i += 1
    return "".join(result)


class ScadStaticValidator:
    @staticmethod
    def validate(content: str) -> None:
        violations = []

        # Rule 1: Empty SCAD content (checks raw content)
        if not content or not content.strip():
            raise LLMPlanValidationError(
                message="OpenSCAD static validation failed:\n- [SCAD_EMPTY_FILE] OpenSCAD content is empty or only whitespace.",
                status_code=400,
                error_code="VALIDATION_ERROR",
            )

        # Rule 2: Markdown code fences (checks raw content)
        if "```" in content:
            violations.append(
                "- [SCAD_MARKDOWN_FENCE] Markdown code fences are forbidden.\n"
                "  Return raw OpenSCAD code only inside .scad file content."
            )

        # Comment stripping for other rules
        stripped = strip_comments(content)

        # Rule 3: Vector property access
        # Regex: r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*[xyz]\b"
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*[xyz]\b", stripped):
            violations.append(
                "- [SCAD_VECTOR_PROPERTY_ACCESS] Forbidden vector property access found.\n"
                "  Use index access instead: point[0], point[1], point[2]. Never use .x, .y, or .z."
            )

        # Rule 4: Single quotes
        if "'" in stripped:
            violations.append(
                "- [SCAD_SINGLE_QUOTE] Single quotes are forbidden.\n"
                "  Use double quotes for strings."
            )

        # Rule 5: Radian conversion formulas
        if re.search(r"\b180\s*/\s*PI\b", stripped, re.IGNORECASE) or re.search(
            r"\bPI\s*/\s*180\b", stripped, re.IGNORECASE
        ):
            violations.append(
                "- [SCAD_RADIAN_CONVERSION] Radian conversion formulas (180/PI or PI/180) are forbidden.\n"
                "  OpenSCAD trigonometric functions use degrees directly."
            )

        # Rule 6: Prose text inside SCAD content
        prose_patterns = [
            r"\bHere\s+is\b",
            r"\bThe\s+following\b",
            r"\bBelow\s+is\b",
            r"아래는",
            r"다음은",
            r"다음\s+코드는",
        ]
        found_prose = False
        for pattern in prose_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                found_prose = True
                break
        if found_prose:
            violations.append(
                "- [SCAD_PROSE] Prose explanations or conversational prefixes are forbidden inside .scad content."
            )

        # Rule 7: Missing OpenSCAD structure
        keywords = [
            "module",
            "polyhedron",
            "cube",
            "sphere",
            "cylinder",
            "difference",
            "union",
            "intersection",
            "translate",
            "rotate",
            "scale",
            "linear_extrude",
            "rotate_extrude",
            "hull",
            "minkowski",
            "text",
            "import",
        ]
        has_keyword = False
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", stripped):
                has_keyword = True
                break
        if not has_keyword:
            violations.append(
                "- [SCAD_MISSING_KEYWORD] OpenSCAD structure is missing.\n"
                "  The file must contain valid OpenSCAD keywords (e.g., module, polyhedron, cube, sphere, translate)."
            )

        if violations:
            detailed_msg = "OpenSCAD static validation failed:\n" + "\n".join(
                violations
            )
            raise LLMPlanValidationError(
                message=detailed_msg,
                status_code=400,
                error_code="VALIDATION_ERROR",
            )
