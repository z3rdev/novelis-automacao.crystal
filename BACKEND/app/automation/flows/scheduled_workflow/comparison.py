from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
    NovelisRelatorioCteXmlFlow,
)


def compare_report(cwd, emit, rows, report_rows):
    report = NovelisRelatorioCteXmlFlow(cwd, emit)
    by_key = {row["key"]: row for row in report_rows if row.get("key")}
    by_number = {
        f"{report._part(row.get('serie'))}|{report._part(row.get('nCT') or row.get('documento'))}": row
        for row in report_rows
        if row.get("serie") or row.get("nCT") or row.get("documento")
    }
    return report._split_existing(rows, by_key, by_number)
