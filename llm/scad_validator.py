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
            elif char == "\n":
                result.append(char)  # block comment 내부의 개행도 보존하여 라인 매핑 유지
        i += 1
    return "".join(result)


class ScadStaticValidator:
    @staticmethod
    def validate(content: str) -> None:
        # Rule 1: Empty SCAD content (checks raw content)
        if not content or not content.strip():
            raise LLMPlanValidationError(
                message="OpenSCAD static validation failed:\n- [SCAD_EMPTY_FILE] OpenSCAD content is empty or only whitespace.",
                status_code=400,
                error_code="VALIDATION_ERROR",
            )

        orig_lines = content.splitlines()
        stripped = strip_comments(content)
        stripped_lines = stripped.splitlines()

        # 라인 수 차이가 생기지 않도록 방어적 패딩 처리
        num_lines = max(len(orig_lines), len(stripped_lines))
        while len(orig_lines) < num_lines:
            orig_lines.append("")
        while len(stripped_lines) < num_lines:
            stripped_lines.append("")

        violations = []

        def get_snippets(violation_indices: list[int]) -> list[str]:
            snippets = []
            for idx in violation_indices[:2]:  # 각 규칙별 대표 snippet은 최대 1~2개
                line_content = orig_lines[idx]
                if len(line_content) > 150:  # snippet 길이는 최대 150자 제한
                    line_content = line_content[:150] + "..."
                snippets.append(f"  * Line {idx + 1}: {line_content}")
            return snippets

        # Rule 2: Markdown code fences (checks raw content)
        r2_indices = [idx for idx, line in enumerate(orig_lines) if "```" in line]
        if r2_indices:
            r2_desc = (
                "- [SCAD_MARKDOWN_FENCE] Markdown code fences are forbidden.\n"
                "  Return raw OpenSCAD code only inside .scad file content."
            )
            snippets = get_snippets(r2_indices)
            violations.append((r2_desc, snippets))

        # Rule 3: Vector property access
        r3_pattern = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*[xyz]\b")
        r3_indices = [idx for idx, line in enumerate(stripped_lines) if r3_pattern.search(line)]
        if r3_indices:
            r3_desc = (
                "- [SCAD_VECTOR_PROPERTY_ACCESS] Forbidden vector property access found.\n"
                "  Use index access instead: point[0], point[1], point[2]. Never use .x, .y, or .z."
            )
            snippets = get_snippets(r3_indices)
            violations.append((r3_desc, snippets))

        # Rule 4: Single quotes
        r4_indices = [idx for idx, line in enumerate(stripped_lines) if "'" in line]
        if r4_indices:
            r4_desc = (
                "- [SCAD_SINGLE_QUOTE] Single quotes are forbidden.\n"
                "  Use double quotes for strings."
            )
            snippets = get_snippets(r4_indices)
            violations.append((r4_desc, snippets))

        # Rule 5: Radian conversion formulas
        r5_pattern = re.compile(r"\b180\s*/\s*PI\b|\bPI\s*/\s*180\b", re.IGNORECASE)
        r5_indices = [idx for idx, line in enumerate(stripped_lines) if r5_pattern.search(line)]
        if r5_indices:
            r5_desc = (
                "- [SCAD_RADIAN_CONVERSION] Radian conversion formulas (180/PI or PI/180) are forbidden.\n"
                "  OpenSCAD trigonometric functions use degrees directly."
            )
            snippets = get_snippets(r5_indices)
            violations.append((r5_desc, snippets))

        # Rule 6: Prose text inside SCAD content
        prose_patterns = [
            r"\bHere\s+is\b",
            r"\bThe\s+following\b",
            r"\bBelow\s+is\b",
            r"아래는",
            r"다음은",
            r"다음\s+코드는",
        ]
        r6_pattern = re.compile("|".join(prose_patterns), re.IGNORECASE)
        r6_indices = [idx for idx, line in enumerate(stripped_lines) if r6_pattern.search(line)]
        if r6_indices:
            r6_desc = "- [SCAD_PROSE] Prose explanations or conversational prefixes are forbidden inside .scad content."
            snippets = get_snippets(r6_indices)
            violations.append((r6_desc, snippets))

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
            r7_desc = (
                "- [SCAD_MISSING_KEYWORD] OpenSCAD structure is missing.\n"
                "  The file must contain valid OpenSCAD keywords (e.g., module, polyhedron, cube, sphere, translate)."
            )
            violations.append((r7_desc, []))

        if violations:
            header = "OpenSCAD static validation failed:\n"
            current_len = len(header)
            final_lines = []
            omitted = False

            for desc, snippets in violations:
                violation_block_lines = [desc]
                if snippets:
                    violation_block_lines.append("  Snippet:")
                    violation_block_lines.extend(snippets)
                block_str = "\n".join(violation_block_lines) + "\n"

                # 1,500자 크기 제한 준수를 위한 방어적 한계 검사 (1,450자 임계점 설정)
                if current_len + len(block_str) > 1450:
                    omitted = True
                    break

                final_lines.append(block_str)
                current_len += len(block_str)

            if omitted:
                final_lines.append("... [additional violations omitted]")

            detailed_msg = header + "".join(final_lines)
            detailed_msg = detailed_msg.strip()

            raise LLMPlanValidationError(
                message=detailed_msg,
                status_code=400,
                error_code="VALIDATION_ERROR",
            )

