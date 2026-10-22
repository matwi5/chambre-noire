"""Recoupe les lignes trop longues d'un fichier Markdown, sans toucher au reste (bibliothèque standard seulement) :

  python3 tests/rewrap.py README.md [autre.md …]   # les lignes ajoutées depuis la base, celles que check.py refuse
  python3 tests/rewrap.py --all README.md          # toutes les lignes de plus de 120 caractères

Seule la ligne fautive change : elle est coupée à un espace en lignes de 120 caractères au plus, la suite reprenant
son retrait (sous le texte d'une puce, « > » d'une citation) ; le paragraphe n'est pas remis en forme. Titres,
tableaux, blocs de code, HTML, lignes vides et toutes les autres lignes restent tels quels. Une coupure évite
l'intérieur d'un `code` et ne fait jamais commencer une ligne par une marque de bloc (« - », « 1. », « # », « > »,
« | », « ``` », soulignement « --- » ou « === ») ; une ligne sans espace où couper reste telle quelle et est signalée.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)")
QUOTE_RE = re.compile(r"^\s*(?:>\s?)+")
# début de ligne que Markdown lirait comme un bloc : une suite de ligne ne commence jamais ainsi
BLOCK_RE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|#|>|\||```|~~~|<|=+\s*$|-+\s*$)")
SKIPPED_RE = re.compile(r"^\s*(?:#|\||<|\[[^\]]+\]:)")   # titres, tableaux, HTML, définitions de liens


def parts(line):
    """(début de la première ligne, retrait des suivantes, texte à couper)."""
    m = QUOTE_RE.match(line)
    if m:
        return m.group(0), m.group(0), line[m.end():]
    m = LIST_RE.match(line)
    if m:
        return m.group(0), " " * len(m.group(0)), line[m.end():]
    indent = line[:len(line) - len(line.lstrip())]
    return indent, indent, line[len(indent):]


def cut_at(text, room):
    """Position de l'espace où couper text pour que sa première partie tienne en room caractères : la plus tardive
    hors d'un `code`, sinon dedans ; jamais devant une marque de bloc ; None s'il n'y en a pas."""
    outside, inside, quoted = [], [], False
    for i, c in enumerate(text[:room + 1]):
        if c == "`":
            quoted = not quoted
        elif c == " " and text[:i].strip() and not BLOCK_RE.match(text[i:].lstrip()):
            (inside if quoted else outside).append(i)
    return (outside or inside or [None])[-1]


def cut(line, width=check.LINE_MAX):
    """Lignes qui remplacent line (elle seule si elle tient, ou ne peut pas être coupée)."""
    head, indent, text = parts(line)
    body = text.rstrip()
    trail = text[len(body):]                        # espaces finaux (saut de ligne Markdown) : sur la dernière ligne
    out, lead = [], head
    while len(lead) + len(body) > width:
        pos = cut_at(body, width - len(lead))
        if pos is None:
            break
        out.append(lead + body[:pos].rstrip())
        body, lead = body[pos:].lstrip(" "), indent
    return out + [lead + body + trail]


def rewrap(text, numbers=None, width=check.LINE_MAX):
    """Texte recoupé : (nouveau texte, nombre de lignes coupées, numéros des lignes trop longues laissées telles
    quelles). numbers : seuls numéros de ligne (à partir de 1) à recouper, toutes les lignes si None."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    out, cuts, left, fenced = [], 0, [], False
    for k, line in enumerate(lines, 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif (len(line) > width and not fenced and not SKIPPED_RE.match(line)
              and (numbers is None or k in numbers)):
            pieces = cut(line, width)
            out += pieces
            if len(pieces) > 1:
                cuts += 1
            else:
                left.append(k)
            continue
        out.append(line)
    return newline.join(out), cuts, left


def main():
    ap = argparse.ArgumentParser(description="Recoupe les lignes trop longues d'un fichier Markdown")
    ap.add_argument("files", nargs="+", metavar="FICHIER")
    ap.add_argument("--all", action="store_true", help="toutes les lignes trop longues, pas seulement les ajoutées")
    args = ap.parse_args()
    base = None if args.all else check.merge_base()
    if not args.all and not base:
        print("base introuvable (git merge-base HEAD origin/main) : préciser --all", file=sys.stderr)
        return 1
    status = 0
    for name in args.files:
        with open(name, encoding="utf-8", newline="") as f:
            text = f.read()
        numbers = None
        if not args.all:
            rel = os.path.relpath(os.path.abspath(name), check.ROOT).replace(os.sep, "/")
            numbers = check.added_lines(base, rel).get(rel, set())
        new, cuts, left = rewrap(text, numbers)
        if new != text:
            with open(name, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        print(f"{name} : {cuts} ligne(s) recoupée(s)")
        for k in left:
            print(f"  {name}:{k} : rien où couper, laissée telle quelle")
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
