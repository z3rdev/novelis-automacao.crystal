"""Prepare the decoded model for bitmap symbols and Basic visibility formulas."""
from copy import deepcopy

from app.services.rpt_rs.conditions import normalize_condition


def prepare_model(model: dict, qr: bytes, code128: bytes) -> tuple[dict, dict]:
    report = deepcopy(model)
    counts = {"qr_pictures": 0, "code128_pictures": 0, "normalized_conditions": 0}
    images = {"{@f_qrcode}": (qr, "qr_pictures"), "{@f_codbar}": (code128, "code128_pictures")}

    def conditions(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "condition_formula_bodies":
                    for index, text in enumerate(item):
                        normalized = normalize_condition(text)
                        counts["normalized_conditions"] += normalized != text
                        item[index] = normalized
                elif key == "condition_formulas":
                    for formula in item:
                        normalized = normalize_condition(formula[1])
                        counts["normalized_conditions"] += normalized != formula[1]
                        formula[1] = normalized
                else:
                    conditions(item)
        elif isinstance(value, list):
            for item in value:
                conditions(item)

    conditions(report)
    for area in report["report_definition"]["areas"]:
        for section in area["sections"]:
            for obj in section["objects"]:
                field = obj["kind"].get("Field", {})
                source = field.get("data_source", "").casefold()
                if source not in images:
                    continue
                image, counter = images[source]
                obj["kind"] = {"Picture": {
                    "picture_type": "Bitmap", "data": image.hex(), "ole_ordinal": None,
                    "location_formula": None, "crop_top": 0, "crop_bottom": 0,
                    "crop_left": 0, "crop_right": 0,
                }}
                if counter == "qr_pictures":
                    size = min(obj["bounds"]["width"], obj["bounds"]["height"])
                    obj["bounds"].update(width=size, height=size)
                counts[counter] += 1
    for field in report["data_definition"]["field_definitions"]:
        if field["name"].casefold() in {"f_qrcode", "qrcode", "f_codbar"}:
            formula = field["kind"].get("Formula")
            if formula:
                formula.update(text='""', syntax="Crystal")
    if not counts["qr_pictures"] or not counts["code128_pictures"]:
        raise ValueError("Campos F_QRCODE e F_CODBAR obrigatorios no layout DACTE.")
    return report, counts
