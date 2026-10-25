"""Genera icon.png/.ico/.icns da zero (nessun file grafico da mantenere). Uso: python tools/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "src" / "nameforge" / "assets"
ACCENT, DARK = "#4f6bed", "#2f3fb0"


def draw(size: int) -> Image.Image:
    s = size * 4  # supercampionamento per i bordi lisci
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((s * 0.05, s * 0.05, s * 0.95, s * 0.95), radius=s * 0.22, fill=ACCENT)
    d.rounded_rectangle((s * 0.05, s * 0.55, s * 0.95, s * 0.95), radius=s * 0.22, fill=DARK)
    d.rectangle((s * 0.05, s * 0.55, s * 0.95, s * 0.72), fill=DARK)
    d.rounded_rectangle((s * 0.05, s * 0.05, s * 0.95, s * 0.72), radius=s * 0.22, fill=ACCENT)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(s * 0.38))
    except OSError:
        font = ImageFont.load_default(int(s * 0.38))
    d.text((s / 2, s * 0.47), "NR", fill="white", font=font, anchor="mm")
    d.rounded_rectangle((s * 0.2, s * 0.8, s * 0.55, s * 0.86), radius=s * 0.03, fill="white")  # "nome" vecchio
    d.rounded_rectangle((s * 0.6, s * 0.8, s * 0.8, s * 0.86), radius=s * 0.03, fill="#9fb0ff")  # "nome" nuovo
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw(1024)
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    big.save(OUT / "icon.icns")
    print("ok", [p.name for p in OUT.iterdir()])
