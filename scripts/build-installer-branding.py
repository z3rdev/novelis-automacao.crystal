"""Package Cargo Hub's native icon and palette into Inno's bitmap resources."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NAVY, TEAL, GRAY = "#0B2545", "#14B8A6", "#6B7280"


def font(size, bold=False):
    windows = Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf")
    return ImageFont.truetype(str(windows), size)


def build(root=ROOT):
    target = root / "runtime/installer-branding"
    target.mkdir(parents=True, exist_ok=True)
    icon = Image.open(root / "FRONTEND-HUB/src-tauri/icons/icon.ico").convert("RGBA")
    panel = Image.new("RGB", (492, 942), NAVY)
    draw = ImageDraw.Draw(panel)
    draw.polygon([(340, 0), (492, 0), (492, 390), (120, 942), (0, 942), (0, 880)], fill="#103756")
    draw.polygon([(468, 0), (492, 0), (492, 942), (368, 942)], fill="#0B6D78")
    draw.rectangle((45, 405, 150, 413), fill=TEAL)
    emblem = icon.resize((132, 132), Image.Resampling.LANCZOS)
    panel.paste(emblem, (43, 75), emblem)
    draw.text((43, 252), "Cargo", font=font(61, True), fill="white")
    draw.text((43, 319), "Hub", font=font(61, True), fill=TEAL)
    for index, line in enumerate(("CT-e e documentos", "Automação e chamados", "Agendamentos e avisos")):
        draw.text((45, 453 + index * 48), line, font=font(23), fill="#D2E5EF")
    draw.text((45, 850), "Desenvolvido por", font=font(20), fill="#A2B6C8")
    draw.text((45, 880), "Z3ro.dev", font=font(25, True), fill="white")
    panel.save(target / "wizard.bmp")
    small = Image.new("RGB", (192, 192), "white")
    small_icon = icon.resize((170, 170), Image.Resampling.LANCZOS)
    small.paste(small_icon, (11, 11), small_icon)
    small.save(target / "wizard-small.bmp")
    return target


if __name__ == "__main__":
    print("Recursos visuais do instalador preparados em", build())
