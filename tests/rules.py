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


# ------------------------------------------------------------ interface (tools/ui/index.html, lignes ajoutées)

# couleur écrite en dur dans du CSS (après « : », « , », « ( » ou une espace) : #hex, rgb(…), rgba(…) ; une valeur
# rgba(${…}) faite de jetons lus par cssRgb est permise
COLOR_RE = re.compile(r"(?:(?<=[\s:,(])#[0-9a-fA-F]{3,8}\b|\brgba?\((?!\$\{))")
TOKEN_RE = re.compile(r"--[\w-]+\s*:")                # ligne qui déclare un jeton (:root, html.priv)
# fonctions qui donnent l'adresse d'une image peut-être privée, et fonctions qui seules la posent sur une image ;
# PRIVATE_SRC_KNOWN : listes dessinées d'un coup depuis les images de l'espace, vidées par changedSpace à la sortie
PRIVATE_URL_RE = re.compile(r"\b(?:privImage|privThumb|thumbOf|srcOf)\(|['\"`]/api/private/")
IMAGE_SET_RE = re.compile(r"\.src\s*=(?!=)|\bsrc=[\"']?\$\{")
PRIVATE_SRC_OK = {"showImage", "preload"}
PRIVATE_SRC_KNOWN = {"renderGallery", "lotCases", "openLot"}


def hardcoded_colors(lines, added=None):
    """Couleurs écrites en dur hors des jetons (ligne qui déclare un --jeton, métadonnée theme-color, masque dont
    seule l'opacité compte) : [(ligne, raison)]."""
    bad = []
    for k, line in enumerate(lines, 1):
        if added is not None and k not in added:
            continue
        if TOKEN_RE.search(line) or 'name="theme-color"' in line or "mask" in line:
            continue
        found = COLOR_RE.search(line)
        if found:
            bad.append((k, f"couleur « {found.group(0)} » écrite en dur : un jeton (var(--…)) du bloc :root"))
    return bad


def unused_keyframes(lines, added=None):
    """@keyframes qu'aucune « animation » ni « animation-name » ne nomme : [(ligne, raison)]."""
    text = "\n".join(lines)
    bad = []
    for k, line in enumerate(lines, 1):
        if added is not None and k not in added:
            continue
        for m in re.finditer(r"@keyframes\s+([\w-]+)", line):
            name = re.escape(m.group(1))
            if not re.search(rf"animation(?:-name)?\s*:[^;}}]*(?<![\w-]){name}(?![\w-])", text):
                bad.append((k, f"@keyframes {m.group(1)} : aucune animation ne la nomme"))
    return bad


def private_src(html, added=None):
    """Adresse d'image peut-être privée (privImage, privThumb, thumbOf, srcOf, /api/private/) posée sur une image
    hors de showImage et preload (seules à refuser une image privée pendant « Sortir ») : [(ligne, raison)]."""
    bad = []
    for k, line in enumerate(html.splitlines(), 1):
        if added is not None and k not in added:
            continue
        if not (IMAGE_SET_RE.search(line) and PRIVATE_URL_RE.search(line)):
            continue
        where = enclosing_name("index.html", html, k)
        if where not in PRIVATE_SRC_OK | PRIVATE_SRC_KNOWN:
            bad.append((k, f"adresse peut-être privée posée sur une image dans {where} : passer par showImage "
                           "(ou preload), qui la refusent pendant « Sortir »"))
    return bad


# ------------------------------------------------------------ tests d'interface (tests/ui/*.test.mjs)

WAIVER = "// règle levée :"                           # sur la ligne ou celle d'avant, avec la raison
FIXED_WAIT_RE = re.compile(r"new Promise\(\s*\(?\s*(\w+)\s*\)?\s*=>\s*setTimeout\(\s*\1\s*,")
HELPER_RE = re.compile(rf"^(?:async\s+)?function\s*\*?\s*({IDENT})\s*\(|^const\s+({IDENT})\s*=\s*(?:async\s*)?"
                       rf"(?:\([^)]*\)|{IDENT})\s*=>")
WAIT_LITERAL_RE = re.compile(r"waitFor\(\s*(`(?:[^`$]|\$(?!\{))*`|'[^']*'|\"[^\"]*\")")
WAIT_LITERAL_MIN = 30                                 # caractères d'une attente qu'on n'écrit pas deux fois
CLOSE_RE = re.compile(r"(?:\bpost|postJson|fetch)\(\s*['\"`]/api/private/lock|PageTransitionEvent\(\s*['\"](?:pagehide"
                      r"|pageshow)|new Event\(\s*['\"]page(?:hide|show)|\bclosedByMac\(\)")
ENTRY_RE = re.compile(r"(?:\bpost|postJson|fetch)\(\s*(?:\$\{)?[^)]*['\"`]/api/private/(?:create|unlock)")


def waived(lines, k):
    """Vrai si la ligne k (ou celle d'avant) lève les règles des tests par « // règle levée : <raison> »."""
    return WAIVER in lines[k - 1] or (k > 1 and lines[k - 2].strip().startswith(WAIVER))


def fixed_waits(lines, added=None):
    """Attente fixe (new Promise(r => setTimeout(r, N))) dans un test : [(ligne, raison)]."""
    return [(k, "attente fixe : attendre une condition (page.waitFor), ou elapse(ms) pour un délai voulu")
            for k, line in enumerate(lines, 1)
            if (added is None or k in added) and FIXED_WAIT_RE.search(line) and not waived(lines, k)]


def _per_file(texts, added, find):
    """Ce que find(ligne) trouve dans chaque fichier ; renvoie les lignes ajoutées dont la trouvaille est aussi dans un
    autre fichier : [(fichier, ligne, trouvaille, autres fichiers)]."""
    where = {}
    for f, text in texts.items():
        for k, line in enumerate(text.splitlines(), 1):
            for found in find(line):
                where.setdefault(found, {}).setdefault(f, []).append(k)
    out = []
    for found, files in where.items():
        for f, numbers in files.items():
            others = sorted(set(files) - {f})
            if others:
                lines = texts[f].splitlines()
                out += [(f, k, found, others) for k in added_only(numbers, added.get(f))
                        if not waived(lines, k)]
    return sorted(out)


def copied_helpers(texts, added):
    """Aide de premier niveau (function, ou const … = (…) =>) déclarée sous le même nom dans deux fichiers de test ou
    plus : [(fichier, ligne, raison)] pour les lignes ajoutées."""
    def find(line):
        m = HELPER_RE.match(line)
        return [m.group(1) or m.group(2)] if m else []
    return [(f, k, f"aide « {name} » déjà déclarée dans {', '.join(others)} : la mettre dans driver.mjs")
            for f, k, name, others in _per_file(texts, added, find)]


def copied_waits(texts, added):
    """Même attente page.waitFor(`…`) (WAIT_LITERAL_MIN caractères au moins, sans ${…}) dans deux fichiers de test ou
    plus : [(fichier, ligne, raison)] pour les lignes ajoutées."""
    def find(line):
        return [m.group(1) for m in WAIT_LITERAL_RE.finditer(line) if len(m.group(1)) - 2 >= WAIT_LITERAL_MIN]
    return [(f, k, f"attente {lit[:40]}… déjà écrite dans {', '.join(others)} : une aide de driver.mjs")
            for f, k, lit, others in _per_file(texts, added, find)]


def unsettled_private_close(lines, added=None):
    """Espace privé fermé sans l'avoir attendu au repos : /api/private/lock envoyé, pagehide ou pageshow simulés,
    closedByMac() appelé sans page.privateIdle() sur la ligne de code juste avant (une requête privée servie après la
    fermeture répondrait 403). closedByMac est permis s'il attend lui-même le repos. [(ligne, raison)]."""
    text = "\n".join(lines)
    own = re.search(r"function closedByMac\(\)\s*\{(.*?)\n\}", text, re.S)
    settles = bool(own and "privateIdle(" in own.group(1))
    bad = []
    for k, line in enumerate(lines, 1):
        if (added is not None and k not in added) or not CLOSE_RE.search(line) or waived(lines, k):
            continue
        if "privateIdle(" in line or (settles and "closedByMac()" in line and not re.search(r"lock|Event", line)):
            continue
        before = next((l for l in reversed(lines[:k - 1]) if l.strip() and not l.strip().startswith("//")), "")
        if "privateIdle(" not in before:
            bad.append((k, "espace privé fermé sans await page.privateIdle() juste avant (403 sous charge)"))
    return bad


def private_entry_by_hand(lines, added=None):
    """/api/private/create ou /unlock appelé par un test au lieu de page.enterPrivate(code) : [(ligne, raison)]."""
    return [(k, "entrée dans l'espace privé écrite à la main : page.enterPrivate(code)")
            for k, line in enumerate(lines, 1)
            if (added is None or k in added) and ENTRY_RE.search(line) and not waived(lines, k)]


# ------------------------------------------------------------ serveur (tools/launch.py) et code Python

def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and _callee(n) == name]


def secret_prints(src):
    """print dont le texte dépend de secret(…) : dans un if ou une expression conditionnelle qui le teste, ou en
    argument (aucun print ne parle de l'espace privé) : [(ligne, raison)]."""
    tree, bad = ast.parse(src), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _calls(node.test, "secret"):
            bad.update(c.lineno for c in _calls(node, "print"))
        if isinstance(node, ast.Call) and _callee(node) == "print" and any(_calls(a, "secret") for a in node.args):
            bad.add(node.lineno)
    return [(k, "print qui dépend de secret(…) : rien ne distingue une génération privée") for k in sorted(bad)]


def undocumented_routes(src):
    """Routes (chaîne "/api/…" du code, préfixes en « / » exceptés) absentes de la docstring du module, où
    « /api/private/image|thumb » vaut pour chacune : [(ligne, raison)]."""
    tree = ast.parse(src)
    doc = ast.get_docstring(tree) or ""
    documented = set()
    for m in re.finditer(r"(/api/(?:[\w-]+/)*)([\w-]+(?:\|[\w-]+)*)", doc):
        documented.update(m.group(1) + part for part in m.group(2).split("|"))
    doc_node = tree.body[0] if tree.body and isinstance(tree.body[0], ast.Expr) else None
    bad = {}
    for node in ast.walk(tree):
        if (node is not getattr(doc_node, "value", None) and isinstance(node, ast.Constant)
                and isinstance(node.value, str) and re.fullmatch(r"/api/[\w/-]*[\w-]", node.value)
                and node.value not in documented):
            bad.setdefault(node.value, node.lineno)
    return sorted((k, f"route {route} absente de la docstring") for route, k in bad.items())


def private_lock_without_rekey(src):
    """Bloc « with PRIVATE_LOCK: » qui appelle quelque chose (une écriture possible de private/) sans finish_rekey()
    dans le bloc ou avant lui dans la fonction. Exceptions : store_private (suit les clés remplacées, S.rekeyed) et
    la suppression de tout l'espace (shutil.rmtree(PRIVATE)). [(ligne, raison)]."""
    tree, bad = ast.parse(src), []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name == "store_private":
            continue
        for node in ast.walk(fn):
            if not (isinstance(node, ast.With) and any(isinstance(i.context_expr, ast.Name)
                                                       and i.context_expr.id == "PRIVATE_LOCK" for i in node.items)):
                continue
            calls = [c for c in ast.walk(node) if isinstance(c, ast.Call)]
            if not calls or _calls(node, "finish_rekey"):
                continue
            if any(c.lineno < node.lineno for c in _calls(fn, "finish_rekey")):
                continue
            if any(_callee(c) == "rmtree" and c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == "PRIVATE"
                   for c in calls):
                continue
            bad.append((node.lineno, "écriture sous PRIVATE_LOCK sans finish_rekey() avant"))
    return bad


def _top_names(src):
    """Noms définis au premier niveau d'un module (fonctions, classes, affectations, imports, aussi sous if/try) et
    par « global »."""
    tree, names = ast.parse(src), {"__file__", "__name__", "__doc__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            names.update(node.names)
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for t in node.targets if isinstance(node, ast.Assign) else [node.target]:
                names.update(_names(t) or [n.id for n in ast.walk(t) if isinstance(n, ast.Name)])
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For)):
            stack += [n for n in ast.iter_child_nodes(node) if isinstance(n, ast.stmt)]
            if isinstance(node, ast.Try):
                stack += [n for h in node.handlers for n in h.body]
    return names


def broken_imports(sources):
    """Imports internes cassés : « from x import nom » ou « x.nom » (lecture) d'un module du dépôt (sources :
    {chemin : texte} des .py) où nom n'est pas défini : [(fichier, ligne, raison)]."""
    paths = {p.rsplit("/", 1)[-1][:-3]: p for p in sources}
    names, bad = {}, []
    defined = lambda m: names.setdefault(m, _top_names(sources[paths[m]]))
    for f, src in sorted(sources.items()):
        try:
            tree = ast.parse(src)
        except SyntaxError:                         # déjà signalé par le contrôle Python
            continue
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                aliases.update({a.asname or a.name: a.name for a in node.names if a.name in paths})
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in paths:
                bad += [(f, node.lineno, f"{a.name} introuvable dans {paths[node.module]}") for a in node.names
                        if a.name != "*" and a.name not in defined(node.module)]
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name)
                    and node.value.id in aliases and node.attr not in defined(aliases[node.value.id])):
                bad.append((f, node.lineno, f"{node.value.id}.{node.attr} introuvable dans "
                                            f"{paths[aliases[node.value.id]]}"))
    return sorted(set(bad))


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


def _js_block_end(text, start):
    """Position de l'accolade qui ferme celle ouverte en start, chaînes ('…', "…", `…`) et commentaires sautés ;
    None si elle manque."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            i += 1
            while i < n and text[i] != c and not (c != "`" and text[i] == "\n"):
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                return None
        elif text.startswith("/*", i):
            i = text.find("*/", i) + 1
            if i <= 0:
                return None
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def function_spans(path, text, name):
    """Lignes (première, dernière) de chaque fonction ou classe appelée name : Python (méthodes comprises), ou
    JavaScript des blocs <script> d'un HTML (déclarations de code_index : function, ou const/let/var de premier
    niveau, jusqu'à l'accolade fermante ; sans accolade, la seule ligne de la déclaration)."""
    if path.endswith(".py"):
        return [(start, end) for start, end, qual in _py_scopes(text) if qual.split(".")[-1] == name]
    spans, lines = [], text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    for k, found in code_index(path, text):
        if found != name:
            continue
        line = lines[k - 1]
        brace = line.find("{")
        end = _js_block_end(text, offsets[k - 1] + brace) if brace >= 0 else None
        spans.append((k, text.count("\n", 0, end) + 1 if end is not None else k))
    return spans


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
