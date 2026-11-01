#!/usr/bin/env python3
"""
Outil de montage automatique de la chaîne.

    python3 outils/monter.py nouvelle "001-abandonner-au-bout-de-3-jours"
    python3 outils/monter.py lecture  videos/001-...   # texte à lire + liste des images
    python3 outils/monter.py video    videos/001-...   # vidéo longue 16:9
    python3 outils/monter.py shorts   videos/001-...   # Shorts 9:16
    python3 outils/monter.py tout     videos/001-...   # vidéo + shorts

Dossier d'une vidéo :
    script.md          le script (format décrit dans docs/format-script.md)
    audio/voix.*       ton enregistrement (wav, m4a, mp3...)
    images/NN.jpg|png|mp4   un visuel par scène (NN = numéro de scène, 01, 02...)
    rendu/             ce que l'outil produit
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import multiprocessing as mp
import random
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parent.parent
POLICES = RACINE / "polices"
FPS = 30
FORMATS = {"long": (1920, 1080), "short": (1080, 1920)}
EXT_IMAGES = (".jpg", ".jpeg", ".png", ".webp")
EXT_VIDEOS = (".mp4", ".mov", ".webm", ".mkv")
EFFETS = ("zoom_in", "zoom_out", "pan_gauche", "pan_droite", "monte", "descend", "fixe")
# Étalonnage « cinéma sombre » appliqué à tous les plans
ETALONNAGE = "eq=contrast=1.08:saturation=1.12:brightness=-0.02,vignette=angle=PI/4.5,noise=alls=5:allf=t"


# ---------------------------------------------------------------- utilitaires
def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write("\n".join(r.stderr.splitlines()[-25:]) + "\n")
        raise SystemExit(f"Échec de la commande : {' '.join(cmd[:6])} ...")
    return r


def duree_media(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def normaliser(mot: str) -> str:
    mot = unicodedata.normalize("NFD", mot.lower())
    mot = "".join(c for c in mot if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", mot)


def info(msg: str) -> None:
    print(f"▸ {msg}", flush=True)


# ---------------------------------------------------------------- script
@dataclass
class Scene:
    n: int
    texte: str
    visuel: str = ""
    effet: str = ""
    image: str = ""
    impact: bool = False
    debut_clip: float = 0.0
    t0: float = 0.0
    t1: float = 0.0
    mots: list = field(default_factory=list)  # [(mot, t0, t1)]


@dataclass
class Short:
    de: int
    a: int
    titre: str


def lire_script(dossier: Path) -> tuple[str, list[Scene], list[Short]]:
    """Format : chaque ligne '- texte' est une scène parlée ; les lignes '> clé: valeur'
    qui suivent la décrivent (visuel, effet, image, impact, debut).
    En tête : 'short: 3-12 | Titre du short'."""
    titre, scenes, shorts = dossier.name, [], []
    for ligne in (dossier / "script.md").read_text(encoding="utf-8").splitlines():
        s = ligne.strip()
        if s.startswith("# ") and titre == dossier.name:
            titre = s[2:].strip()
        elif s.lower().startswith("short:"):
            m = re.match(r"short:\s*(\d+)\s*-\s*(\d+)\s*\|?\s*(.*)", s, re.I)
            if m:
                shorts.append(Short(int(m[1]), int(m[2]), m[3].strip()))
        elif s.startswith("- "):
            scenes.append(Scene(n=len(scenes) + 1, texte=s[2:].strip()))
        elif s.startswith(">") and scenes:
            m = re.match(r">\s*(\w+)\s*:\s*(.*)", s)
            if not m:
                continue
            cle, val, sc = m[1].lower(), m[2].strip(), scenes[-1]
            if cle == "visuel":
                sc.visuel = val
            elif cle == "effet":
                sc.effet = val
            elif cle == "image":
                sc.image = val
            elif cle == "impact":
                sc.impact = val.lower() in ("oui", "yes", "1", "true", "")
            elif cle == "debut":
                sc.debut_clip = float(val.replace(",", "."))
    if not scenes:
        raise SystemExit("Aucune scène trouvée : les phrases à lire doivent commencer par '- '.")
    for sc in scenes:
        if sc.effet not in EFFETS:
            sc.effet = random.Random(sc.n).choice(EFFETS[:6])
    return titre, scenes, shorts


def trouver_media(dossier: Path, sc: Scene) -> Path | None:
    imgs = dossier / "images"
    if sc.image:
        p = imgs / sc.image
        return p if p.exists() else None
    for ext in EXT_VIDEOS + EXT_IMAGES:  # un extrait vidéo passe avant une image
        for nom in (f"{sc.n:02d}{ext}", f"{sc.n}{ext}", f"{sc.n:03d}{ext}"):
            if (imgs / nom).exists():
                return imgs / nom
    return None


# ---------------------------------------------------------------- audio
def preparer_audio(dossier: Path) -> Path:
    sources = [p for p in sorted((dossier / "audio").glob("voix.*")) if "propre" not in p.name]
    if not sources:
        raise SystemExit(f"Pas d'audio : dépose ton enregistrement dans {dossier}/audio/voix.m4a (ou .wav/.mp3)")
    src, sortie = sources[0], dossier / "rendu" / "voix_propre.wav"
    sortie.parent.mkdir(exist_ok=True)
    if sortie.exists() and sortie.stat().st_mtime > src.stat().st_mtime:
        return sortie
    info(f"Nettoyage de la voix ({src.name}) : coupe-bas, débruitage, compression, volume YouTube")
    filtres = ("silenceremove=start_periods=1:start_threshold=-45dB,"
               "highpass=f=80,lowpass=f=14000,afftdn=nf=-25,"
               "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,"
               "loudnorm=I=-14:TP=-1.5:LRA=9")
    run(["ffmpeg", "-y", "-i", str(src), "-af", filtres, "-ar", "48000", "-ac", "1", str(sortie)])
    return sortie


def silences(audio: Path) -> list[float]:
    r = subprocess.run(["ffmpeg", "-i", str(audio), "-af", "silencedetect=n=-35dB:d=0.25",
                        "-f", "null", "-"], capture_output=True, text=True)
    debuts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(a + b) / 2 for a, b in zip(debuts, fins)]


def transcrire(audio: Path, cache: Path) -> list[tuple[str, float, float]] | None:
    if cache.exists() and cache.stat().st_mtime > audio.stat().st_mtime:
        return [tuple(x) for x in json.loads(cache.read_text())]
    try:
        from faster_whisper import WhisperModel
        info("Transcription mot à mot (Whisper)…")
        modele = WhisperModel("small", device="cpu", compute_type="int8")
        segs, _ = modele.transcribe(str(audio), language="fr", word_timestamps=True, vad_filter=True)
        mots = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]
        cache.write_text(json.dumps(mots, ensure_ascii=False))
        return mots
    except Exception as e:  # modèle indisponible (réseau) -> mode approximatif
        info(f"Whisper indisponible ({type(e).__name__}) : synchro approximative sur les pauses de la voix")
        return None


def synchroniser(scenes: list[Scene], audio: Path, dossier: Path) -> float:
    total = duree_media(audio)
    tokens = []  # (scene_idx, mot affiché, mot normalisé)
    for i, sc in enumerate(scenes):
        for m in sc.texte.split():
            tokens.append((i, m, normaliser(m)))
    temps: list[tuple[float, float] | None] = [None] * len(tokens)

    asr = transcrire(audio, dossier / "rendu" / "transcription.json")
    if asr:
        a_norm = [normaliser(w) for w, _, _ in asr]
        sm = difflib.SequenceMatcher(None, [t[2] for t in tokens], a_norm, autojunk=False)
        for bloc in sm.get_matching_blocks():
            for k in range(bloc.size):
                _, t0, t1 = asr[bloc.b + k]
                temps[bloc.a + k] = (t0, t1)
    else:
        # Répartition proportionnelle au nombre de lettres, recalée sur les pauses
        pauses = silences(audio)
        poids = [max(len(t[2]), 1) + 2 for t in tokens]
        cumul, acc = [], 0
        for p in poids:
            cumul.append(acc)
            acc += p
        for k in range(len(tokens)):
            temps[k] = (cumul[k] / acc * total, (cumul[k] + poids[k]) / acc * total)
        for i in range(1, len(scenes)):
            k = next(j for j, t in enumerate(tokens) if t[0] == i)
            t = temps[k][0]
            proches = [p for p in pauses if abs(p - t) < 1.5]
            if proches:
                cible = min(proches, key=lambda p: abs(p - t))
                decal = cible - t
                # décale la scène i et ce qui suit, puis on réétale plus bas
                for j in range(k, len(tokens)):
                    temps[j] = (temps[j][0] + decal, temps[j][1] + decal)
        temps = [(max(0, min(a, total)), max(0, min(b, total))) for a, b in temps]

    # Interpolation des mots non reconnus
    connus = [k for k, t in enumerate(temps) if t]
    if not connus:
        raise SystemExit("Impossible d'aligner le script sur l'audio : vérifie que tu as lu le bon script.")
    for k in range(len(tokens)):
        if temps[k] is None:
            avant = max((j for j in connus if j < k), default=None)
            apres = min((j for j in connus if j > k), default=None)
            ta = temps[avant][1] if avant is not None else 0.0
            tb = temps[apres][0] if apres is not None else total
            ia = avant if avant is not None else -1
            ib = apres if apres is not None else len(tokens)
            f0, f1 = (k - ia) / (ib - ia), (k - ia + 1) / (ib - ia)
            temps[k] = (ta + (tb - ta) * f0 * 0.98, ta + (tb - ta) * f1 * 0.98)

    for i, sc in enumerate(scenes):
        ks = [k for k, t in enumerate(tokens) if t[0] == i]
        sc.mots = [(tokens[k][1], temps[k][0], temps[k][1]) for k in ks]
        sc.t0 = 0.0 if i == 0 else sc.mots[0][1] - 0.08
    for i, sc in enumerate(scenes):
        sc.t1 = scenes[i + 1].t0 if i + 1 < len(scenes) else total
        if sc.t1 - sc.t0 < 0.4:
            sc.t1 = sc.t0 + 0.4
    return total


# ---------------------------------------------------------------- visuels
def police(taille: int, nom: str = "Anton-Regular.ttf") -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(POLICES / nom), taille)
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", taille)


def carte_provisoire(sc: Scene, W: int, H: int) -> Image.Image:
    """Visuel provisoire quand l'image de la scène manque encore."""
    rng = random.Random(sc.n)
    teinte = rng.choice([(20, 24, 48), (40, 12, 18), (12, 30, 34), (30, 20, 40)])
    img = Image.new("RGB", (W, H), teinte)
    d = ImageDraw.Draw(img)
    for r in range(max(W, H), 0, -12):  # halo radial
        c = tuple(min(255, int(v + (1 - r / max(W, H)) * 60)) for v in teinte)
        d.ellipse([W / 2 - r, H / 2 - r * 0.7, W / 2 + r, H / 2 + r * 0.7], fill=c)
    d.text((W * 0.12, H * 0.08), f"SCÈNE {sc.n:02d}", font=police(int(H * 0.07)), fill=(255, 200, 60))
    lignes, ligne = [], ""
    for mot in (sc.visuel or sc.texte).split():
        if len(ligne + mot) > (28 if W > H else 14):
            lignes.append(ligne)
            ligne = ""
        ligne += mot + " "
    lignes.append(ligne)
    f = police(int(H * 0.045), "Montserrat-ExtraBold.ttf")
    for j, l in enumerate(lignes[:6]):
        d.text((W * 0.12, H * 0.22 + j * H * 0.065), l.strip(), font=f, fill=(235, 235, 235))
    d.text((W * 0.12, H * 0.88), "à fournir : images/%02d.jpg" % sc.n, font=police(int(H * 0.035), "Montserrat-ExtraBold.ttf"), fill=(150, 150, 150))
    return img


def couvrir(img: Image.Image, W: int, H: int, marge: float) -> Image.Image:
    """Redimensionne pour couvrir W*marge x H*marge. Pour une image paysage en vertical,
    on garde l'image entière au centre sur un fond flouté (plus joli qu'un recadrage brutal)."""
    img = img.convert("RGB")
    Wm, Hm = int(W * marge), int(H * marge)
    ratio_img, ratio_cible = img.width / img.height, W / H
    if ratio_img > ratio_cible * 1.6:  # ex. image 16:9 dans un short 9:16
        fond = img.resize((int(Hm * ratio_img), Hm), Image.LANCZOS)
        x = (fond.width - Wm) // 2
        fond = fond.crop((x, 0, x + Wm, Hm)).filter(ImageFilter.GaussianBlur(28))
        fond = Image.eval(fond, lambda v: int(v * 0.45))
        h = int(Wm / ratio_img * 1.25)
        avant = img.resize((int(h * ratio_img), h), Image.LANCZOS)
        x = (avant.width - Wm) // 2
        avant = avant.crop((max(0, x), 0, max(0, x) + Wm, h))
        fond.paste(avant, (0, (Hm - h) // 2))
        return fond
    s = max(Wm / img.width, Hm / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    x, y = (img.width - Wm) // 2, (img.height - Hm) // 2
    return img.crop((x, y, x + Wm, y + Hm))


def rendre_scene(args: tuple) -> Path:
    media, sc_dict, W, H, sortie = args
    sc = Scene(**{k: v for k, v in sc_dict.items() if k != "mots"})
    d = max(sc.t1 - sc.t0, 0.4)
    n_img = max(1, round(d * FPS))
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]

    if media and media.suffix.lower() in EXT_VIDEOS:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
              f"fps={FPS},tpad=stop_mode=clone:stop_duration={d:.2f},{ETALONNAGE}")  # fige la fin si trop court
        run(["ffmpeg", "-y", "-ss", str(sc.debut_clip), "-i", str(media),
             "-t", f"{n_img / FPS:.3f}", "-vf", vf, "-an", *enc, str(sortie)])
        return sortie

    marge = 1.18
    base = couvrir(Image.open(media) if media else carte_provisoire(sc, W, H), W, H, marge)
    Wb, Hb = base.size
    rng = random.Random(sc.n * 7)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", ETALONNAGE, *enc, str(sortie)],
                            stdin=subprocess.PIPE)
    for i in range(n_img):
        p = i / max(n_img - 1, 1)
        p = p * p * (3 - 2 * p) * 0.6 + p * 0.4  # mouvement doux
        z0, z1 = {"zoom_in": (1.0, 1.15), "zoom_out": (1.15, 1.0)}.get(sc.effet, (1.08, 1.08))
        if sc.effet == "fixe":
            z0 = z1 = 1.02
        z = z0 + (z1 - z0) * p
        cw = Wb / z
        ch = Hb / z
        libre_x, libre_y = Wb - cw, Hb - ch
        fx, fy = 0.5, 0.5
        if sc.effet == "pan_gauche":
            fx = 1 - p
        elif sc.effet == "pan_droite":
            fx = p
        elif sc.effet == "monte":
            fy = 1 - p
        elif sc.effet == "descend":
            fy = p
        x, y = libre_x * fx, libre_y * fy
        if sc.impact and i < FPS * 0.35:  # tremblement d'impact
            force = (1 - i / (FPS * 0.35)) * W * 0.012
            x = min(max(0, x + rng.uniform(-force, force)), libre_x)
            y = min(max(0, y + rng.uniform(-force, force)), libre_y)
        # transformation affine sous-pixel = mouvement fluide sans saccade
        cadre = base.transform((W, H), Image.AFFINE, (cw / W, 0, x, 0, ch / H, y), resample=Image.BICUBIC)
        if sc.impact and i < 4:  # flash blanc
            cadre = Image.blend(cadre, Image.new("RGB", (W, H), (255, 255, 255)), 0.85 - i * 0.2)
        proc.stdin.write(cadre.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"Échec du rendu de la scène {sc.n}")
    return sortie


def rendre_plans(dossier: Path, scenes: list[Scene], fmt: str, travail: Path) -> Path:
    W, H = FORMATS[fmt]
    travail.mkdir(parents=True, exist_ok=True)
    taches, manquantes = [], []
    for sc in scenes:
        media = trouver_media(dossier, sc)
        if media is None:
            manquantes.append(sc.n)
        d = {k: v for k, v in sc.__dict__.items() if k != "mots"}
        taches.append((media, d, W, H, travail / f"plan_{sc.n:03d}.mp4"))
    if manquantes:
        info(f"{len(manquantes)} visuel(s) manquant(s) → cartes provisoires : scènes {manquantes}")
    info(f"Rendu de {len(taches)} plans en {W}x{H}…")
    with mp.Pool(max(1, mp.cpu_count())) as pool:
        plans = pool.map(rendre_scene, taches)
    liste = travail / "plans.txt"
    liste.write_text("".join(f"file '{p.name}'\n" for p in plans))
    muette = travail / "video_muette.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(muette)])
    return muette


# ---------------------------------------------------------------- sous-titres
def ass_temps(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ecrire_sous_titres(scenes: list[Scene], fmt: str, sortie: Path, decalage: float = 0.0) -> None:
    W, H = FORMATS[fmt]
    taille, marge_v, align = (112, 100, 2) if fmt == "long" else (132, 600, 2)
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Mot,Anton,{taille},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,2,0,1,7,3,{align},80,80,{marge_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lignes = []
    jaune = r"{\c&H00D7FF&}"  # format BGR : jaune doré
    for sc in scenes:
        mots = sc.mots
        # groupes de 1 à 3 mots, coupés sur la ponctuation
        groupes, g = [], []
        for m in mots:
            g.append(m)
            if len(g) == 3 or re.search(r"[.,!?;:…]$", m[0]):
                groupes.append(g)
                g = []
        if g:
            groupes.append(g)
        for gi, g in enumerate(groupes):
            fin_groupe = groupes[gi + 1][0][1] if gi + 1 < len(groupes) else sc.t1
            fin_groupe = min(fin_groupe, g[-1][2] + 0.6)
            for wi, (mot, t0, t1) in enumerate(g):
                fin = g[wi + 1][1] if wi + 1 < len(g) else fin_groupe
                if fin <= t0:
                    continue
                texte = " ".join((jaune + w.upper() + r"{\c&HFFFFFF&}") if k == wi else w.upper()
                                 for k, (w, _, _) in enumerate(g))
                pop = r"{\fscx80\fscy80\t(0,90,\fscx100\fscy100)}" if wi == 0 else ""
                lignes.append(f"Dialogue: 0,{ass_temps(t0 - decalage)},{ass_temps(fin - decalage)},Mot,,0,0,0,,{pop}{texte}")
    sortie.write_text(entete + "\n".join(lignes) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- bruitages
def sfx_par_defaut() -> dict[str, Path]:
    """Génère des bruitages simples et libres de droits s'il n'y en a pas dans sfx/."""
    dossier = RACINE / "sfx"
    dossier.mkdir(exist_ok=True)
    sr = 48000
    fichiers = {"whoosh": dossier / "whoosh.wav", "impact": dossier / "impact.wav"}
    if not fichiers["whoosh"].exists():
        t = np.linspace(0, 0.7, int(sr * 0.7), endpoint=False)
        bruit = np.random.default_rng(1).normal(0, 1, t.size)
        env = np.sin(np.pi * t / 0.7) ** 2
        # filtre passe-bande glissant approximé par lissage variable
        sortie, prec = np.zeros_like(bruit), 0.0
        for i, v in enumerate(bruit):
            a = 0.02 + 0.25 * (i / bruit.size)
            prec = prec + a * (v - prec)
            sortie[i] = prec
        ecrire_wav(fichiers["whoosh"], sortie * env, sr)
    if not fichiers["impact"].exists():
        t = np.linspace(0, 1.2, int(sr * 1.2), endpoint=False)
        freq = 70 * np.exp(-t * 2.5) + 38
        boom = np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-t * 3.2)
        clic = np.random.default_rng(2).normal(0, 1, t.size) * np.exp(-t * 60) * 0.5
        ecrire_wav(fichiers["impact"], boom + clic, sr)
    return fichiers


def ecrire_wav(path: Path, signal: np.ndarray, sr: int) -> None:
    import wave
    s = signal / (np.max(np.abs(signal)) + 1e-9) * 0.9
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((s * 32767).astype(np.int16).tobytes())


def musique_de_fond(dossier: Path) -> Path | None:
    for p in [*sorted((dossier / "audio").glob("musique.*")), *sorted((RACINE / "musique").glob("*.*"))]:
        if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
            return p
    return None


# ---------------------------------------------------------------- assemblage
def assembler(muette: Path, voix: Path, scenes: list[Scene], ass: Path, sortie: Path,
              musique: Path | None, debut_audio: float = 0.0, duree: float | None = None) -> None:
    sfx = sfx_par_defaut()
    entrees = ["-i", str(muette), "-ss", f"{debut_audio:.3f}"]
    if duree:
        entrees += ["-t", f"{duree:.3f}"]
    entrees += ["-i", str(voix)]
    graphe, mix = ["[1:a]aformat=channel_layouts=stereo,volume=1.0[voix]"], ["[voixd]"]
    idx = 2
    if musique:
        entrees += ["-stream_loop", "-1", "-i", str(musique)]
        graphe.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume=0.22[mus]")
        graphe.append("[voix]asplit=2[voixd][voixsc]")
        graphe.append("[mus][voixsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[musd]")
        mix.append("[musd]")
        idx += 1
    else:
        graphe[-1] = graphe[-1].replace("[voix]", "[voixd]")
    # whoosh à chaque changement de partie, impact sur les scènes marquées
    evenements = [(sc.t0 - debut_audio, "impact" if sc.impact else "whoosh")
                  for k, sc in enumerate(scenes) if sc.impact or (k > 0 and k % 6 == 0)]
    for t, nom in evenements:
        if t < 0:
            continue
        entrees += ["-i", str(sfx[nom])]
        vol = 0.55 if nom == "impact" else 0.25
        ms = int(max(t - (0.35 if nom == "whoosh" else 0), 0) * 1000)
        graphe.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[s{idx}]")
        mix.append(f"[s{idx}]")
        idx += 1
    graphe.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[a]")
    graphe.append(f"[0:v]ass='{ass.as_posix()}':fontsdir='{POLICES.as_posix()}'[v]")
    run(["ffmpeg", "-y", *entrees, "-filter_complex", ";".join(graphe), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(sortie)])


def planche_controle(video: Path, scenes: list[Scene], sortie: Path, decalage: float = 0.0) -> None:
    """Planche d'images (milieu de chaque scène) pour vérifier le montage d'un coup d'œil."""
    vignettes = []
    tmp = sortie.parent / "_ctrl.jpg"
    for sc in scenes[:48]:
        t = (sc.t0 + sc.t1) / 2 - decalage
        run(["ffmpeg", "-y", "-ss", f"{max(t, 0):.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=480:-2", str(tmp)])
        vignettes.append(Image.open(tmp).copy())
    tmp.unlink(missing_ok=True)
    if not vignettes:
        return
    w, h = vignettes[0].size
    cols = 6 if w > h else 8
    rows = math.ceil(len(vignettes) / cols)
    planche = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
    for k, v in enumerate(vignettes):
        planche.paste(v, ((k % cols) * w, (k // cols) * h))
    planche.save(sortie, quality=85)


# ---------------------------------------------------------------- commandes
def cmd_nouvelle(nom: str) -> None:
    d = RACINE / "videos" / nom
    if d.exists():
        raise SystemExit(f"{d} existe déjà")
    for sous in ("images", "audio", "rendu"):
        (d / sous).mkdir(parents=True)
    shutil.copy(RACINE / "docs" / "modele-script.md", d / "script.md")
    print(f"Créé : {d}")


def cmd_lecture(dossier: Path) -> None:
    titre, scenes, _ = lire_script(dossier)
    (dossier / "rendu").mkdir(exist_ok=True)
    texte = "\n\n".join(sc.texte for sc in scenes)
    (dossier / "rendu" / "texte_a_lire.txt").write_text(f"{titre}\n\n{texte}\n", encoding="utf-8")
    lignes = [f"# Visuels à trouver — {titre}\n", "| Fichier | Effet | Visuel recherché | Phrase |", "|---|---|---|---|"]
    for sc in scenes:
        ok = "✅" if trouver_media(dossier, sc) else "⬜"
        lignes.append(f"| {ok} {sc.image or f'{sc.n:02d}.jpg'} | {sc.effet}{' 💥' if sc.impact else ''} | {sc.visuel} | {sc.texte[:70]} |")
    (dossier / "rendu" / "visuels.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    mots = len(texte.split())
    print(f"{len(scenes)} scènes, {mots} mots ≈ {mots / 150:.1f} min de voix")
    print(f"→ {dossier}/rendu/texte_a_lire.txt   (à lire au micro)")
    print(f"→ {dossier}/rendu/visuels.md         (liste des images)")


def preparer(dossier: Path):
    titre, scenes, shorts = lire_script(dossier)
    voix = preparer_audio(dossier)
    total = synchroniser(scenes, voix, dossier)
    info(f"{len(scenes)} scènes synchronisées sur {total / 60:.1f} min de voix")
    return titre, scenes, shorts, voix


def cmd_video(dossier: Path, prep=None) -> None:
    titre, scenes, _, voix = prep or preparer(dossier)
    rendu = dossier / "rendu"
    muette = rendre_plans(dossier, scenes, "long", rendu / "_travail_long")
    ass = rendu / "sous_titres_long.ass"
    ecrire_sous_titres(scenes, "long", ass)
    sortie = rendu / f"{dossier.name}.mp4"
    info("Assemblage : voix + musique + bruitages + sous-titres…")
    assembler(muette, voix, scenes, ass, sortie, musique_de_fond(dossier))
    planche_controle(sortie, scenes, rendu / "controle_long.jpg")
    shutil.rmtree(rendu / "_travail_long", ignore_errors=True)
    print(f"✅ Vidéo : {sortie}  ({duree_media(sortie) / 60:.1f} min)")


def cmd_shorts(dossier: Path, prep=None) -> None:
    titre, scenes, shorts, voix = prep or preparer(dossier)
    if not shorts:
        print("Aucun short défini : ajoute 'short: 3-12 | Titre' en tête du script.")
        return
    rendu = dossier / "rendu"
    for k, sh in enumerate(shorts, 1):
        sel = [sc for sc in scenes if sh.de <= sc.n <= sh.a]
        if not sel:
            continue
        debut, fin = sel[0].t0, sel[-1].t1
        if sel[-1] is not scenes[-1]:
            fin = sel[-1].mots[-1][2] + 0.5  # coupe juste après la dernière phrase
        decal = [Scene(**{**sc.__dict__, "t0": sc.t0 - debut, "t1": min(sc.t1, fin) - debut,
                          "mots": [(m, a - debut, b - debut) for m, a, b in sc.mots]}) for sc in sel]
        decal[0].t0 = 0.0
        if fin - debut > 59:
            info(f"⚠ Short {k} dure {fin - debut:.0f}s (> 59s) : réduis la plage de scènes")
        muette = rendre_plans(dossier, decal, "short", rendu / f"_travail_short{k}")
        ass = rendu / f"sous_titres_short{k}.ass"
        ecrire_sous_titres(decal, "short", ass)
        sortie = rendu / f"short_{k:02d}.mp4"
        assembler(muette, voix, decal, ass, sortie, musique_de_fond(dossier), debut, fin - debut)
        planche_controle(sortie, decal, rendu / f"controle_short{k}.jpg")
        shutil.rmtree(rendu / f"_travail_short{k}", ignore_errors=True)
        print(f"✅ Short {k} « {sh.titre} » : {sortie}  ({duree_media(sortie):.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Montage automatique de la chaîne")
    ap.add_argument("commande", choices=["nouvelle", "lecture", "video", "shorts", "tout"])
    ap.add_argument("cible", help="nom de la nouvelle vidéo, ou dossier videos/NNN-...")
    a = ap.parse_args()
    if a.commande == "nouvelle":
        return cmd_nouvelle(a.cible)
    dossier = Path(a.cible).resolve()
    if not (dossier / "script.md").exists():
        raise SystemExit(f"Pas de script.md dans {dossier}")
    if a.commande == "lecture":
        return cmd_lecture(dossier)
    prep = preparer(dossier)
    if a.commande in ("video", "tout"):
        cmd_video(dossier, prep)
    if a.commande in ("shorts", "tout"):
        cmd_shorts(dossier, prep)


if __name__ == "__main__":
    main()
