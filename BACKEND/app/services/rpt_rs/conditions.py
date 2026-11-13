"""Translate Basic conditional Formula assignments into Crystal expressions."""
import re

IF = re.compile(r"if\s+(.+?)\s+then\s*$", re.IGNORECASE)
ASSIGN = re.compile(r"formula\s*=\s*(.+)$", re.IGNORECASE)
ARRAY = re.compile(r"\barray\s*\(([^()]*)\)", re.IGNORECASE)
SHARED = re.compile(r"shared\s+(\w+)\s+as\s+(boolean|string|number)$", re.IGNORECASE)


def normalize_condition(text: str) -> str:
    if not re.search(r"\bformula\s*=", text, re.IGNORECASE):
        return text
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("'")]
    prefix, declarations = [], set()
    while lines:
        declaration = SHARED.fullmatch(lines[0])
        if lines[0].casefold() == "whileprintingrecords":
            prefix.append("WhilePrintingRecords;")
        elif declaration:
            prefix.append(f"Shared {declaration[2].title()}Var {declaration[1]};")
            declarations.add(declaration[1].casefold())
        else:
            break
        lines.pop(0)
    suffix = []
    while lines:
        assignment = re.fullmatch(r"(\w+)\s*=\s*(.+)", lines[-1])
        if not assignment or assignment[1].casefold() not in declarations:
            break
        suffix.insert(0, f"{assignment[1]} := {assignment[2]};")
        lines.pop()

    def block(position: int, initial: str) -> tuple[str, int]:
        value = initial
        while position < len(lines):
            line = lines[position]
            if line.casefold() in {"else", "end if", "endif"}:
                return value, position
            conditional = IF.fullmatch(line)
            assignment = ASSIGN.fullmatch(line)
            if conditional:
                condition = ARRAY.sub(r"[\1]", conditional[1])
                yes, position = block(position + 1, value)
                no = value
                if position < len(lines) and lines[position].casefold() == "else":
                    no, position = block(position + 1, value)
                if position >= len(lines) or lines[position].casefold() not in {"end if", "endif"}:
                    raise ValueError("Condicional Basic sem End If correspondente.")
                value = f"(If ({condition}) Then ({yes}) Else ({no}))"
            elif assignment:
                value = ARRAY.sub(r"[\1]", assignment[1])
            else:
                raise ValueError("Instrucao Basic de visibilidade ainda nao suportada pelo adaptador.")
            position += 1
        return value, position

    expression, consumed = block(0, "False")
    if consumed != len(lines):
        raise ValueError("Bloco Basic de visibilidade incompleto.")
    if suffix:
        prefix.extend(["Local BooleanVar novelisCondition;", f"novelisCondition := {expression};"])
        return "\n".join([*prefix, *suffix, "novelisCondition"])
    return "\n".join([*prefix, expression])
