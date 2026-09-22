"""Fabrique une image de test synthétique (scène simple) pour les tests d'édition.
Usage : python tools/make_test_image.py SORTIE.png [--size 512]
"""
import argparse
from PIL import Image, ImageDraw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=512)
    a = ap.parse_args()
    s = a.size
    img = Image.new("RGB", (s, s), (135, 206, 235))          # ciel
    d = ImageDraw.Draw(img)
    d.rectangle([0, int(s * 0.62), s, s], fill=(76, 153, 60))  # herbe
    d.ellipse([int(s*0.70), int(s*0.08), int(s*0.90), int(s*0.28)], fill=(255, 220, 60))  # soleil
    d.rectangle([int(s*0.20), int(s*0.40), int(s*0.50), int(s*0.70)], fill=(200, 70, 60))   # maison
    d.polygon([(int(s*0.17), int(s*0.40)), (int(s*0.35), int(s*0.24)), (int(s*0.53), int(s*0.40))], fill=(120, 60, 40))  # toit
    d.rectangle([int(s*0.31), int(s*0.55), int(s*0.39), int(s*0.70)], fill=(80, 50, 30))     # porte
    img.save(a.out)
    print(f"image de test écrite : {a.out} ({s}x{s})")

if __name__ == "__main__":
    main()
