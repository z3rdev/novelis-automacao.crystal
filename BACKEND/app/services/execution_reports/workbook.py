from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

NAVY, TEAL = "0B2545", "14B8A6"
ZONE = ZoneInfo("America/Sao_Paulo")


def local_date(value):
    return (
        datetime.fromisoformat(value).astimezone(ZONE).strftime("%d/%m/%Y %H:%M:%S")
        if value
        else ""
    )


def text(cell, value):
    cell.value = str(value or "")
    cell.data_type = "s"  # Portal/operator values cannot become spreadsheet formulas.


def build(value, output: Path):
    book = Workbook()
    summary = book.active
    summary.title = "Resumo"
    daily = value.get("kind") == "daily"
    summary.append(
        ["CARGO HUB", "Relatório diário de chamados" if daily else "Relatório de execução"]
    )
    states = {"completed": "Concluída", "failed": "Falhou", "cancelled": "Cancelada"}
    summary_rows = (
        ("Execução", value["id"]),
        ("Operador", value["operator"]),
        ("Computador", value["computer"]),
        ("Início", local_date(value["started_at"])),
        ("Fim", local_date(value["finished_at"])),
        ("Situação", states.get(value["status"], value["status"])),
        ("Chamados abertos nesta execução", value["opened_count"]),
        ("Já existentes, não abertos nesta execução", value["existing_count"]),
    )
    if daily:
        summary_rows = (
            ("Data", datetime.fromisoformat(value["report_date"]).strftime("%d/%m/%Y")),
            ("Chamados abertos", value["opened_count"]),
            ("Operadores", value["operator"]),
            ("Computadores", value["computer"]),
            ("Execuções com aberturas", value["run_count"]),
            ("Atualizado em", local_date(value["generated_at"])),
        )
    for label, content in summary_rows:
        summary.append([label, content])
        if isinstance(content, str):
            text(summary.cell(summary.max_row, 2), content)
    summary.column_dimensions["A"].width = 44
    summary.column_dimensions["B"].width = 55
    columns = [
        ("CT-e", "cte", 18),
        ("Chamado", "numero", 23),
        ("Confirmação", "confirmado_em", 23),
        ("Origem", "origem", 30),
        ("Destino", "destino", 30),
        ("TON", "ton", 12),
        ("ID tarifa", "id_tarifa", 16),
        ("Frete SQL", "frete", 19),
        ("Total CT-e", "valor", 19),
        ("Conferência", "conferencia", 20),
        ("Link Novelis", "link", 65),
    ]
    if daily:
        columns += [
            ("Operador", "operator", 25),
            ("Computador", "computer", 25),
            ("Execução", "run_id", 40),
        ]
    sheets = [("Chamados abertos", "opened")]
    if not daily:
        sheets.append(("Já existentes", "existing"))
    for name, key in sheets:
        sheet = book.create_sheet(name)
        sheet.append([item[0] for item in columns])
        for item in value[key]:
            sheet.append([None] * len(columns))
            for index, (_, field, _) in enumerate(columns, 1):
                cell = sheet.cell(sheet.max_row, index)
                raw = item.get(field)
                if field in {"frete", "valor"} and raw is not None:
                    cell.value, cell.number_format = float(raw), '"R$" #,##0.00'
                else:
                    text(cell, local_date(raw) if field == "confirmado_em" and raw else raw)
                if field == "link" and raw:
                    cell.hyperlink, cell.style = raw, "Hyperlink"
        for index, (_, _, width) in enumerate(columns, 1):
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
        sheet.freeze_panes = "C2"
        if value[key]:
            table = Table(
                displayName="Abertos" if key == "opened" else "Existentes", ref=sheet.dimensions
            )
            table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
            sheet.add_table(table)
        sheet.auto_filter.ref = sheet.dimensions
    for sheet in book:
        sheet.sheet_view.showGridLines = False
        sheet.row_dimensions[1].height = 28
        for cell in sheet[1]:
            cell.fill, cell.font = (
                PatternFill("solid", fgColor=NAVY),
                Font(color="FFFFFF", bold=True),
            )
            cell.alignment = Alignment(vertical="center")
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation, sheet.page_setup.paperSize = "landscape", sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
        sheet.print_title_rows = "1:1"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.{uuid4().hex}.tmp")
    try:
        book.save(temporary)
        temporary.replace(output)
    finally:
        book.close()
        temporary.unlink(missing_ok=True)
