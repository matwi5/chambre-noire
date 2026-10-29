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
# (un #hex suivi de « { » est un sélecteur d'id, pas une couleur ; entre guillemets, seulement donné à une couleur)
COLOR_RE = re.compile(r"(?:(?<=[\s:,(])#[0-9a-fA-F]{3,8}\b(?!\s*\{)|\brgba?\((?!\$\{)"
                      r"|(?:color|background\w*|fill\w*|stroke\w*|border\w*)\s*[:=]\s*['\"`]#[0-9a-fA-F]{3,8}\b)",
                      re.I)
MASK_RE = re.compile(r"\bmask(?:-image)?\s*:")         # masque : seule l'opacité de la couleur compte
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
        if TOKEN_RE.search(line) or 'name="theme-color"' in line or MASK_RE.search(line):
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
            if not re.search(rf"animation(?:-name|Name)?\s*[:=][^;}}\n]*(?<![\w-]){name}(?![\w-])", text):
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
# new Promise(… setTimeout(…, N) …) : attente d'un nombre fixe de millisecondes, quelle que soit la forme du rappel
FIXED_WAIT_RE = re.compile(r"new Promise\(.*\bsetTimeout\(.*,\s*[\d_]+\s*\)")
HELPER_RE = re.compile(rf"^(?:async\s+)?function\s*\*?\s*({IDENT})\s*\(|^const\s+({IDENT})\s*=\s*(?:async\s*)?"
                       rf"(?:\([^)]*\)|{IDENT})\s*=>")
WAIT_LITERAL_RE = re.compile(r"waitFor\(\s*(`(?:[^`$]|\$(?!\{))*`|'[^']*'|\"[^\"]*\")")
WAIT_LITERAL_MIN = 30                                 # caractères d'une attente qu'on n'écrit pas deux fois
# appel qui envoie une route privée : son premier argument est l'adresse (« post('/api/…' », « privatePost(…) »,
# « fetch(`${bench.url}/api/…` ») ; une comparaison, includes ou un motif de requêtes retenues n'en est pas un
CALL_TO = r"(?<!\w)(?!includes\b|startsWith\b|endsWith\b|holdRequests\b|holdFetch\b)\w+\(\s*['\"`](?:\$\{[^}]*\})?"
CLOSE_RE = re.compile(CALL_TO + r"/api/private/lock|PageTransitionEvent\(\s*['\"](?:pagehide|pageshow)"
                      r"|new Event\(\s*['\"]page(?:hide|show)|\bclosedByMac\(\)")
ENTRY_RE = re.compile(CALL_TO + r"/api/private/(?:create|unlock)")


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


# tri brut dans un test : clic sur ✓ ✕ ou un bouton de la visionneuse ([data-sort], #vSort), appel de sortTop ou
# sortFromViewer ; flèche ← → envoyée à la main ; verrou de tri lu (le pilote seul les nomme : driver.mjs)
SORT_TARGET = r"""(?:#pileYes|#pileNo|#vSort|data-sort)"""
RAW_SORT_RE = re.compile(rf"""(?:click|tryClick)\(\s*['"`][^'"`]*{SORT_TARGET}"""
                         rf"""|querySelector(?:All)?\(\s*['"`][^'"`]*{SORT_TARGET}[^;]*\.click\("""
                         r"""|(?:\$|getElementById)\(\s*['"`](?:pileYes|pileNo|vSort)['"`]\s*\)[^;]*\.click\("""
                         r"""|\bsort(?:Top|FromViewer)\(|['"`]#pile(?:Yes|No)['"`]""")   # (ou par une variable)
RAW_ARROW_RE = re.compile(r"""['"`]Arrow(?:Left|Right)['"`]""")   # page.press, keyDown, un KeyboardEvent…
# verrou lu : pas une propriété (.sortHeld de LOCKS ou de page.sortState()), ni une clé d'objet (sortHeld: false)
LOCK_READ_RE = re.compile(r"(?<![.\w$])(?:sortHeld|sortBusy|topHeld)\b(?!\s*:)")
TRAILING_COMMENT_RE = re.compile(r"\s//\s.*$")
# une levée de r4 nomme le tri dans sa raison (une levée d'une autre règle sur la même ligne ne vaut pas pour elle)
SORT_WAIVER_RE = re.compile(r"règle levée :.*\b(?:tri|trie|appui|flèche|touche|verrou|pilote)", re.I)


def raw_sorts(lines, added=None):
    """Tri d'un test d'interface qui ne passe pas par le pilote : un changement du moment où une image se trie
    faisait tomber des dizaines de tests, retrouvés à la revue (E3, F4). [(ligne, raison)] ; commentaires exceptés."""
    bad = []
    for k, line in enumerate(lines, 1):
        if (added is not None and k not in added) or line.lstrip().startswith("//"):
            continue
        if SORT_WAIVER_RE.search(line) or (k > 1 and lines[k - 2].strip().startswith(WAIVER)
                                            and SORT_WAIVER_RE.search(lines[k - 2])):
            continue
        code = TRAILING_COMMENT_RE.sub("", line)
        if re.search(r"\{[^}]*\}\s*=\s*await\s+\w+\.sortState\(\)", code):   # const { topHeld } = …
            code = LOCK_READ_RE.sub("", code)
        if RAW_SORT_RE.search(code):
            bad.append((k, "tri par un clic ou un appel brut (✓, ✕, [data-sort], sortTop, sortFromViewer) : "
                           "page.sort(action, { by, ready }) du pilote, ou PRESS et VIEWER_PRESS dans la page (aussi "
                           "keepPile, topShown, made, viewPile)"))
        if RAW_ARROW_RE.search(code):
            bad.append((k, "flèche ← → envoyée sans aide : page.sort(action, { by: 'key' }), ou page.stepViewer(±1) "
                           "dans une visionneuse"))
        if LOCK_READ_RE.search(code):
            bad.append((k, "verrou de tri lu hors du pilote : SORT_IDLE, VIEWER_SEEN, LOCKS ou page.sortState() "
                           "(driver.mjs)"))
    return bad


# page ouverte par un test (« const p = await chrome.newPage(PC) ») : son nom, et le Chrome qui l'a ouverte
OPEN_PAGE_RE = re.compile(rf"\b({IDENT})\s*=\s*await\s+({IDENT})\.(?:phonePage|newPage)\(")
TOP_BLOCK_RE = re.compile(r"^(?:(test|before|after|beforeEach|afterEach|describe)\(|(?:async\s+)?function\b|const\b)")


def _top_block(lines, k):
    """(première, dernière ligne, genre) de l'instruction de premier niveau qui contient la ligne k : genre « test »,
    « before »…, « function » ou « const » ; None hors de toute instruction."""
    start = next((j for j in range(k, 0, -1) if lines[j - 1][:1] not in ("", " ", "\t", "}", ")")), None)
    if start is None:
        return None
    m = TOP_BLOCK_RE.match(lines[start - 1])
    end = next((j for j in range(start + 1, len(lines) + 1) if lines[j - 1][:1] not in ("", " ", "\t", "}", ")")),
               len(lines) + 1) - 1
    return start, end, (m.group(1) or m.group(0).split()[-1].rstrip("(")) if m else "autre"


def unclosed_pages(lines, added=None):
    """Page ouverte dans un test (phonePage, newPage) sans fermeture (page.close, ou le Chrome qui l'a ouverte) dans
    un finally : un test qui échoue la laisse ouverte, avec son espace privé et ses requêtes (groupe D). Les pages de
    before() (fermées par after()) et celles qu'une aide rend (return) sont laissées. [(ligne, raison)]."""
    bad = []
    for k, line in enumerate(lines, 1):
        m = OPEN_PAGE_RE.search(line)
        if not m or (added is not None and k not in added) or waived(lines, k):
            continue
        block = _top_block(lines, k)
        if not block or block[2] in ("before", "after", "beforeEach", "afterEach"):
            continue
        name, chrome = m.groups()
        body = "\n".join(lines[k:block[1]])
        if re.search(rf"\breturn\s+{name}\s*(?:[;)}}\n]|$)", body):    # aide qui rend la page : à l'appelant
            continue
        closing = rf"\b(?:{name}|{chrome})\??\.close\(\)"
        if not any(re.search(closing, body[f.end():matching(body, f.end() - 1, "{", "}") or len(body)])
                   for f in re.finditer(r"\bfinally\s*\{", body)):
            bad.append((k, f"page « {name} » ouverte sans fermeture dans un finally (await {name}.close()) : un "
                           "échec la laisse ouverte"))
    return bad


def unawaited_close(lines, added=None):
    """Fermeture d'une page (nom donné par phonePage ou newPage dans le fichier) sans await : le test suivant démarre
    pendant qu'elle se ferme (pagehide, verrouillage de l'espace) (groupe D). [(ligne, raison)]."""
    names = {m.group(1) for line in lines for m in OPEN_PAGE_RE.finditer(line)}
    bad = []
    for k, line in enumerate(lines, 1):
        if (added is not None and k not in added) or line.lstrip().startswith("//") or waived(lines, k):
            continue
        for m in re.finditer(rf"(?<![\w$.])({IDENT})\??\.close\(\)", line):
            if m.group(1) in names and not re.search(r"\bawait\s+\(?[^;]*$", line[:m.start()]):
                bad.append((k, f"« {m.group(1)}.close() » sans await : la page n'est pas encore fermée à la suite"))
    return bad


DRIVER_EXPORT_RE = re.compile(rf"^export\s+(?:async\s+)?(?:function\s*\*?|const|let)\s+({IDENT})")
DRIVER_METHOD_RE = re.compile(rf"^ {{4}}(?:async\s+)?({IDENT})\s*\([^)]*\)\s*\{{")
TEST_DECL_RE = re.compile(rf"^(?:async\s+)?function\s*\*?\s*({IDENT})\s*\(|^(?:const|let|var)\s+({IDENT})\s*=")


def driver_names(text):
    """Aides du pilote (texte de driver.mjs) : ses exports et les méthodes des objets qu'il rend (page, bench,
    chrome)."""
    names = set()
    for line in text.splitlines():
        m = DRIVER_EXPORT_RE.match(line) or DRIVER_METHOD_RE.match(line)
        if m and m.group(1) not in ("if", "for", "while", "switch", "catch", "function"):
            names.add(m.group(1))
    return names


def driver_redefined(lines, names, added=None):
    """Aide du pilote (driver_names) redéfinie au premier niveau d'un fichier de test, sur le fichier entier : une
    copie ne suit plus le pilote quand il change (settled, TOP, inPile recopiés). [(ligne, raison)]."""
    bad = []
    for k, line in enumerate(lines, 1):
        m = TEST_DECL_RE.match(line)
        name = m and (m.group(1) or m.group(2))
        if name in names and (added is None or k in added) and not waived(lines, k):
            bad.append((k, f"« {name} » redéfinit une aide du pilote : l'importer de driver.mjs, ou la changer là"))
    return bad


# préfixe d'un prompt de test : z, une lettre minuscule, jusqu'à deux autres lettres, puis des chiffres, collé ou non
# à la suite (« zp25 secrete », « HOLD=champ zqC4 … », « zqE4file », « zq5public ») ; sans chiffre, z et une ou deux
# lettres suivis d'une espace ou de la fin de la chaîne (« zt dessus »). Créer une image : un appel dont le nom
# contient made, generate, launch, typePrompt, post (postJson, page.postGenerate, une aide du fichier) ou ask ; son
# test est le bloc test( (test.skip, test.only…) de premier niveau qui le contient
PREFIX_RE = re.compile(r"""(?<![\w$])(z[a-z][A-Za-z]{0,2}\d+|z[a-z]{1,2}(?=[\s'"`]))(?!\d)""")
MAKES_RE = re.compile(r"\b\w*(?:made|[Gg]enerate|[Ll]aunch|typePrompt|[Pp]ost|ask)\w*\(")


def prefix_reuse(lines, added=None):
    """Préfixe de prompt de test repris par un autre test du même fichier pour créer une image (made, generate,
    launch, typePrompt) : une image d'un test répondrait à l'attente d'un autre. Une suite voulue reste permise : le
    test qui reprend le préfixe suit tout de suite un test qui le nomme (la pile d'un test est celle du suivant).
    [(ligne, raison)]."""
    tests, owner, mentions, makes = [], None, {}, []
    for k, line in enumerate(lines, 1):
        if re.match(r"test(?:\.\w+)?\(", line):
            owner = k
            tests.append(k)
        elif line[:1] not in ("", " ", "\t", "}", ")"):
            owner = None
        if owner is None:
            continue
        for p in PREFIX_RE.findall(line):
            mentions.setdefault(p, []).append(owner)
            if MAKES_RE.search(line):
                makes.append((k, p, owner))
    bad = []
    for k, p, owner in makes:
        before = [t for t in mentions[p] if t < owner]
        if not before or (added is not None and k not in added) or waived(lines, k):
            continue
        previous = tests[tests.index(owner) - 1]
        if before[-1] != previous:
            bad.append((k, f"préfixe « {p} » déjà employé par le test de la ligne {before[0]} : un préfixe par "
                           "test (ou la suite immédiate du test qui le nomme)"))
    return bad


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
        at = next((pos for n, pos in _js_decls(line) if n == name), None)   # second nom d'un const a = …, b = …
        if at is None:
            at = line.find(name)
        brace = _body_brace(text, offsets[k - 1] + max(at, 0))
        end = _js_block_end(text, brace) if brace is not None else None
        spans.append((k, text.count("\n", 0, end) + 1 if end is not None else k))
    return spans


def _body_brace(text, start):
    """Position de l'accolade qui ouvre le corps de la déclaration nommée en start : la première hors des
    parenthèses des paramètres (une déstructuration { a } = {} y reste), des chaînes, des gabarits `…${…}…` et des
    commentaires ; None si la déclaration finit avant (« ; », ou fin de ligne hors des parenthèses)."""
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
            if depth == 0:
                return None
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == "{" and depth == 0:
            return i
        elif c in ";\n" and depth == 0:
            return None
        i += 1
    return None


JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "with"}


def _js_decls(line):
    """Noms déclarés par une ligne const, let ou var de premier niveau, avec leur position : le premier, puis chaque
    « , nom = » hors des parenthèses, crochets, accolades et chaînes (« const a = …, b = … »)."""
    m = re.match(rf"^(?:export\s+)?(?:const|let|var)\s+({IDENT})\s*=", line)
    if not m:
        return []
    out, depth, quote, i = [(m.group(1), m.start(1))], 0, "", m.end()
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            n = re.match(rf"\s*({IDENT})\s*=(?![=>])", line[i + 1:])
            if n:
                out.append((n.group(1), i + 1 + n.start(1)))
        i += 1
    return out


def code_index(path, text):
    """Fonctions, classes et constantes de premier niveau d'un fichier Python, des blocs <script> d'un HTML ou d'un
    module JavaScript (export compris ; chaque nom d'un « const a = …, b = … ») ; dans un .mjs, aussi les méthodes des
    objets qu'il rend (page, bench du pilote, en retrait de quatre espaces) : [(ligne, nom)]."""
    if path.endswith(".py"):
        pattern = re.compile(r"^(?:\s*(?:async\s+)?def\s+(\w+)|class\s+(\w+)|([A-Z][A-Z0-9_]+)\s*(?::[^=]+)?=)")
        return [(k, next(g for g in m.groups() if g)) for k, line in enumerate(text.splitlines(), 1)
                if (m := pattern.match(line))]
    function = re.compile(rf"^(?:export\s+)?\s*(?:async\s+)?function\s*\*?\s*({IDENT})")
    method = re.compile(rf"^ {{4}}(?:async\s+)?({IDENT})\s*\([^)]*\)\s*\{{")
    out = []
    for k, line in enumerate(text.splitlines(), 1):
        m = function.match(line) or (path.endswith(".mjs") and method.match(line))
        if m and m.group(1) not in JS_KEYWORDS:
            out.append((k, m.group(1)))
        out += [(k, name) for name, _ in _js_decls(line)]
    return out
