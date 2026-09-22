"""Génère un masque d'édition (équivalent d'un dessin au pinceau) pour un test scripté.

Usage :
  python tools/make_mask.py IMAGE.png MASQUE.png [--shape circle|rect] [--cx 0.5 --cy 0.5 --r 0.25]
                            [--overlay APERCU.png] [--annotate IMAGE_ANNOTEE.png]

- MASQUE.png : PNG niveaux de gris, même taille que l'image, blanc (255) = zone à modifier, noir (0) = conservée.
- --overlay  : aperçu (image + zone rouge translucide).
- --annotate : image avec un cercle/rectangle rouge tracé dessus (mode « annotation » : l'image annotée est envoyée
               telle quelle comme référence, sans masque, et le prompt parle de « the area circled in red »).
"""
import argparse
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("mask_out")
    ap.add_argument("--shape", choices=["circle", "rect"], default="circle")
    ap.add_argument("--cx", type=float, default=0.5, help="centre x (fraction de la largeur)")
    ap.add_argument("--cy", type=float, default=0.5, help="centre y (fraction de la hauteur)")
    ap.add_argument("--r", type=float, default=0.25, help="rayon (fraction du plus petit côté)")
    ap.add_argument("--overlay", help="PNG de visualisation (image + zone rouge) optionnel")
    ap.add_argument("--annotate", help="PNG de l'image avec le contour rouge tracé dessus (mode annotation)")
    a = ap.parse_args()

    img = Image.open(a.image).convert("RGB")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    r = a.r * min(w, h)
    box = [a.cx * w - r, a.cy * h - r, a.cx * w + r, a.cy * h + r]
    if a.shape == "circle":
        d.ellipse(box, fill=255)
    else:
        d.rectangle(box, fill=255)
    mask.save(a.mask_out)
    print(f"masque écrit : {a.mask_out} ({w}x{h}, zone blanche = {a.shape} centre=({a.cx},{a.cy}) r={a.r})")

    if a.overlay:
        red = Image.new("RGB", (w, h), (255, 0, 0))
        over = Image.composite(red, img, mask.point(lambda v: int(v * 0.5)))
        over.save(a.overlay)
        print(f"aperçu écrit : {a.overlay}")

    if a.annotate:
        ann = img.copy()
        da = ImageDraw.Draw(ann)
        width = max(4, int(min(w, h) * 0.012))
        if a.shape == "circle":
            da.ellipse(box, outline=(255, 0, 0), width=width)
        else:
            da.rectangle(box, outline=(255, 0, 0), width=width)
        ann.save(a.annotate)
        print(f"image annotée écrite : {a.annotate} (contour rouge, épaisseur {width}px)")


if __name__ == "__main__":
    main()
