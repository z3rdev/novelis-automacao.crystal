"""Render the CT-e access key as a font-independent Code 128 bitmap."""
import re
from pathlib import Path


def encoder_available() -> bool:
    try:
        import zxingcpp
    except ImportError:
        return False
    return callable(getattr(zxingcpp, "create_barcode", None)) and callable(
        getattr(zxingcpp, "write_barcode_to_image", None))


def create_code128_bitmap(access_key: str, path: Path) -> None:
    import zxingcpp
    from PIL import Image

    if not re.fullmatch(r"[0-9]{44}", access_key):
        raise ValueError("Code 128 precisa da chave CT-e de 44 digitos.")
    if not encoder_available():
        raise ImportError("Atualize zxing-cpp para a versao 3 ou superior no backend.")
    barcode = zxingcpp.create_barcode(access_key, zxingcpp.BarcodeFormat.Code128)
    bitmap = zxingcpp.write_barcode_to_image(barcode, scale=4, add_hrt=False, add_quiet_zones=True)
    with Image.fromarray(bitmap) as image:
        image.convert("RGB").save(path, format="BMP")


def validate_code128(symbols: list[dict], access_key: str) -> None:
    values = [item["value"] for item in symbols if item["format"] == "Code 128"]
    if not values:
        raise ValueError("Codigo de barras Code 128 ausente ou ilegivel no PDF.")
    if access_key not in values:
        raise ValueError("Codigo de barras do PDF nao corresponde a chave consultada no banco.")
