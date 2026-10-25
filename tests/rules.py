"""Règles mécaniques de CODING_STANDARDS.md vérifiées par tests/check.py (bibliothèque standard seulement), et index
des fonctions de la carte du code. Chaque fonction est pure : elle reçoit un texte et les numéros de ses lignes
ajoutées depuis la base (added : ensemble, ou None pour toutes), et rend les numéros de ligne fautifs avec leur
raison ; check.py lit les fichiers, calcule les lignes ajoutées et affiche.
"""
import ast, re

IDENT = r"[A-Za-z_$][\w$]*"
DECL_RE = re.compile(rf"\b(?:let|const|var)\s+({IDENT})|\bfunction\s*\*?\s*({IDENT})\s*\(")
ID_RE = re.compile(r"""\bid\s*=\s*["']([\w-]+)["']""")
HOLD_RE = re.compile(r"\bHOLD=([\w-]+)")
# noms cités par la carte du code qui ne sont pas dans le code du dépôt : modules tiers
MAP_EXTERNAL = {"http_ece"}
# extensions : un texte cité qui finit ainsi est un nom de fichier, pas un nom du code
FILE_EXTENSIONS = {"py", "mjs", "js", "html", "json", "jsonl", "md", "txt", "png", "pem", "log", "yml", "cmd",
                   "command", "lnk", "webmanifest", "css", "svg", "gguf", "safetensors", "installed"}


def added_only(numbers, added):
    return [k for k in numbers if added is None or k in added]


def matching(text, start, opening, closing):
    """Position du caractère qui ferme celui ouvert en start (parenthèse ou crochet), ou None."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def matching_back(text, end, opening, closing):
    """Position du caractère qui ouvre celui fermé en end, en remontant, ou None."""
    depth = 0
    for i in range(end, -1, -1):
        if text[i] == closing:
            depth += 1
        elif text[i] == opening:
            depth -= 1
            if depth == 0:
                return i
    return None


def id_shadows(html, added=None):
    """Variables ou fonctions JavaScript de html qui portent l'id d'un élément (chaque id est aussi une globale de
    window : la variable la masque) : [(ligne, raison)]."""
    ids = set(ID_RE.findall(html))
    bad = []
    for k, line in enumerate(html.splitlines(), 1):
        if added is not None and k not in added:
            continue
        for m in DECL_RE.finditer(line):
            name = m.group(1) or m.group(2)
            if name in ids:
                bad.append((k, f"variable « {name} » du même nom que l'élément id=\"{name}\""))
    return bad


def receiver(line, dot):
    """Expression sur laquelle porte la méthode appelée en line[dot:] (« .every(… ») : texte, ou None si illisible."""
    i = dot - 1
    while i >= 0:
        c = line[i]
        if c in ")]":
            j = matching_back(line, i, "([" [")]".index(c)], c)
            if j is None:
                return None
            i = j - 1
        elif re.match(r"[\w$.]", c):
            i -= 1
        else:
            break
    return line[i + 1:dot] or None


def unchecked_every(lines, added=None):
    """Assertions JavaScript « .every( » sur une liste dont aucune longueur n'est vérifiée sur la ligne ou la précédente
    ([].every(…) est toujours vrai) : [(ligne, raison)]. Un tableau littéral sans « ... » n'est jamais vide."""
    bad = []
    for k, line in enumerate(lines, 1):
        if added is not None and k not in added:
            continue
        window = (lines[k - 2] if k > 1 else "") + "\n" + line
        for m in re.finditer(r"\.every\(", line):
            r = receiver(line, m.start())
            # seul un tableau littéral entier ([a, b].every) est sûr ; [a, b].filter(…).every peut être vide
            if r and r.startswith("[") and matching(r, 0, "[", "]") == len(r) - 1 and "..." not in r:
                continue
            base = re.match(IDENT, r or "")
            names = [r] + ([base.group(0)] if base else []) if r else []
            if not any(f"{n}.length" in window for n in names) and not (r is None and "length" in window):
                bad.append((k, f"« {r or '…'}.every( » sans test de la longueur de la liste ({r or 'liste'}.length)"))
    return bad


def unchecked_all(lines, added=None):
    """Assertions Python « all( » sur un itérable dont aucune longueur n'est vérifiée sur la ligne ou la précédente
    (all([]) est vrai) : [(ligne, raison)]. Un tuple ou une liste littérale ne sont jamais vides."""
    bad = []
    for k, line in enumerate(lines, 1):
        if added is not None and k not in added:
            continue
        window = (lines[k - 2] if k > 1 else "") + "\n" + line
        for m in re.finditer(r"\ball\(", line):
            end = matching(line, m.end() - 1, "(", ")")
            inner = line[m.end():end] if end else line[m.end():]
            loop = list(re.finditer(r"\bfor\b.+?\bin\s+", inner))
            if not loop:
                continue
            source = re.split(r"\s+if\s+", inner[loop[-1].end():])[0].strip()
            if source[:1] in "([" and "*" not in source:
                continue
            base = re.match(r"(?:self\.)?[\w.]+", source)
            name = base.group(0) if base else source
            if not re.search(rf"len\({re.escape(name)}|{re.escape(name)}\s+and\s+all\(|assertTrue\({re.escape(name)}\)",
                             window):
                bad.append((k, f"« all(… in {source}) » sans test de la longueur de {name} (len({name}))"))
    return bad


def unawaited_then(lines, added=None):
    """Promesse prise pour un booléen : « .then(…) && » ou « .then(…) || » (une promesse est toujours vraie) :
    [(ligne, raison)]."""
    bad = []
    for k, line in enumerate(lines, 1):
        if added is not None and k not in added:
            continue
        for m in re.finditer(r"\.then\(", line):
            end = matching(line, m.end() - 1, "(", ")")
            if end is not None and re.match(r"\s*(&&|\|\|)", line[end + 1:]):
                bad.append((k, "« .then(…) && » ou « || » : la promesse, pas sa valeur (await, ou dans le .then)"))
    return bad


def hold_reuse(texts, added):
    """Noms HOLD=<nom> repris d'un fichier de test à l'autre (une libération vaut jusqu'à la fin du banc) ; texts :
    {fichier : texte}, added : {fichier : lignes ajoutées ou None}. Renvoie [(fichier, ligne, raison)] pour les
    lignes ajoutées seulement."""
    where = {}
    for f, text in texts.items():
        for k, line in enumerate(text.splitlines(), 1):
            for name in HOLD_RE.findall(line):
                where.setdefault(name, {}).setdefault(f, []).append(k)
    bad = []
    for name, files in where.items():
        if len(files) < 2:
            continue
        for f, numbers in files.items():
            others = ", ".join(sorted(set(files) - {f}))
            bad += [(f, k, f"HOLD={name} déjà employé dans {others}") for k in added_only(numbers, added.get(f))]
    return sorted(bad)


def _names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for t in target.elts for n in _names(t)]
    return []


def _base(node):
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _callee(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _prompt_of(value):
    """Expression du prompt de la génération demandée dans value : premier argument ou prompt= d'un appel *generate*,
    ou valeur de la clé "prompt" d'un dict ; (trouvé, expression ou None pour le prompt par défaut)."""
    for node in ast.walk(value):
        if isinstance(node, ast.Call) and "generate" in _callee(node):
            kw = [k.value for k in node.keywords if k.arg == "prompt"]
            return True, (node.args[0] if node.args else kw[0] if kw else None)
        if isinstance(node, ast.Dict):
            for key, v in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "prompt":
                    return True, v
    return False, None


def _slow(expr, src, assigned, before, depth=0):
    """Vrai si le prompt expr porte HOLD ou SLOW, faux s'il ne les porte pas, None si on ne peut pas le savoir."""
    if expr is None:                                  # prompt par défaut des aides du banc : ni HOLD ni SLOW
        return False
    if isinstance(expr, (ast.Constant, ast.JoinedStr, ast.BinOp)):
        text = ast.get_source_segment(src, expr) or ""
        if "HOLD" in text or "SLOW" in text:
            return True
        # une f-string qui interpole une valeur (f"{p} chat") peut porter HOLD par cette valeur : inconnu
        interpolated = isinstance(expr, ast.JoinedStr) and any(isinstance(v, ast.FormattedValue) for v in expr.values)
        return False if isinstance(expr, ast.Constant) or (isinstance(expr, ast.JoinedStr) and not interpolated) \
            else None
    if isinstance(expr, ast.Name) and depth < 2:
        values = [v for line, v in assigned.get(expr.id, []) if line < before]
        return _slow(values[-1], src, assigned, before, depth + 1) if values else None
    return None


def running_without_hold(src, added=None):
    """wait_job(…, ("running",)) sur une génération dont le prompt n'a ni HOLD ni SLOW : elle peut finir avant d'être
    vue en cours (CI rouge du 21/10/2026) : [(ligne, raison)]. Une génération dont le prompt ne se lit pas est
    laissée."""
    tree = ast.parse(src)
    bad = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assigned = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    for name in _names(t):
                        assigned.setdefault(name, []).append((node.lineno, node.value))
        for line in assigned.values():
            line.sort(key=lambda x: x[0])
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and _callee(node) == "wait_job" and node.args):
                continue
            until = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords
                                                                  if k.arg == "until"), None)
            if not (isinstance(until, ast.Tuple) and [getattr(e, "value", None) for e in until.elts] == ["running"]):
                continue
            if added is not None and node.lineno not in added:
                continue
            name = _base(node.args[0])
            values = [v for line, v in assigned.get(name, []) if line < node.lineno]
            if not values:
                continue
            found, prompt = _prompt_of(values[-1])
            if found and _slow(prompt, src, assigned, node.lineno) is False:
                bad.add((node.lineno, "wait_job(…, (\"running\",)) sur une génération sans HOLD ni SLOW : elle peut "
                                      "finir avant d'être vue en cours"))
    return sorted(bad)


def map_names(text):
    """Noms cités entre accents graves par la carte du code (identifiant, a.b, nom() ou nom(arguments)) :
    [(ligne, texte cité, nom à trouver dans le code)]."""
    out = []
    for m in re.finditer(r"`([^`\n]+)`", text):
        n = re.fullmatch(rf"((?:{IDENT}\.)*)({IDENT})(\(.*\))?", m.group(1))
        if n and not (n.group(1) and not n.group(3) and n.group(2) in FILE_EXTENSIONS):   # driver.mjs : un fichier
            out.append((text.count("\n", 0, m.start()) + 1, m.group(1), n.group(2)))
    return out


def missing_map_names(text, code):
    """Noms de la carte (map_names) absents du code (texte de tous les fichiers de code du dépôt) : [(ligne,
    raison)]."""
    words = set(re.findall(IDENT, code)) | MAP_EXTERNAL
    return [(k, f"« {quoted} » : {name} introuvable dans le code") for k, quoted, name in map_names(text)
            if name not in words]


ROUTE_RE = re.compile(r"[\"'](/api/[\w/<>.-]*)[\"']")


def _py_scopes(text):
    """Fonctions et classes d'un source Python : [(première ligne, dernière ligne, nom qualifié « Classe.méthode »)] ;
    [] s'il ne se lit pas."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                out.append((child.lineno, child.end_lineno, name))
                visit(child, name + ".")
            else:
                visit(child, prefix)
    visit(tree, "")
    return out


def enclosing_name(path, text, k):
    """Où se trouve la ligne k de text (fichier path) : nom de la fonction qui la contient (la plus intérieure,
    « Classe.méthode » en Python ; dernière fonction de premier niveau d'avant pour un HTML ou un JavaScript), suivi
    entre crochets des routes de la condition qui l'entoure (« H.do_POST [/api/keep, /api/discard] ») ; « premier
    niveau » hors de toute fonction."""
    lines = text.splitlines()
    if path.endswith(".py"):
        scopes = [s for s in _py_scopes(text) if s[0] <= k <= s[1]]
        if not scopes:
            return "premier niveau"
        start, _, name = max(scopes)
        indent = len(lines[k - 1]) - len(lines[k - 1].lstrip()) if k <= len(lines) else 0
        for j in range(k - 1, start - 1, -1):        # condition englobante (moins en retrait) qui nomme des routes
            line = lines[j - 1]
            if line.strip() and len(line) - len(line.lstrip()) < indent:
                routes = ROUTE_RE.findall(line)
                if routes:
                    return f"{name} [{', '.join(routes)}]"
                indent = len(line) - len(line.lstrip())
        return name
    before = [name for line, name in code_index(path, text) if line <= k]
    return before[-1] if before else "premier niveau"


def code_index(path, text):
    """Fonctions, classes et constantes de premier niveau d'un fichier Python ou des blocs <script> d'un HTML :
    [(ligne, nom)]."""
    if path.endswith(".py"):
        pattern = re.compile(r"^(?:\s*(?:async\s+)?def\s+(\w+)|class\s+(\w+)|([A-Z][A-Z0-9_]+)\s*(?::[^=]+)?=)")
    else:
        pattern = re.compile(rf"^(?:\s*(?:async\s+)?function\s*\*?\s*({IDENT})|(?:const|let|var)\s+({IDENT})\s*=)")
    out = []
    for k, line in enumerate(text.splitlines(), 1):
        m = pattern.match(line)
        if m:
            out.append((k, next(g for g in m.groups() if g)))
    return out
