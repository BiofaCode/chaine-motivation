#!/usr/bin/env python3
"""
Génère les visuels manquants d'une vidéo avec Pollinations (gratuit, sans compte).

    python3 outils/images.py videos/001-...            # toutes les scènes sans image
    python3 outils/images.py videos/001-... --scenes 3,7,12 --refaire

Offre gratuite : 1 image / 45 s, 1024x576, filigrane en bas à droite (recadré automatiquement).
Avec une clé gratuite Pollinations (variable POLLINATIONS_KEY) : plus rapide, sans filigrane, meilleurs modèles.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from monter import lire_script, trouver_media  # noqa: E402

STYLE = ("anime key visual, 2D cel shaded japanese animation style, cinematic composition, "
         "dramatic lighting, dark moody colors with warm golden highlights, emotional atmosphere, "
         "highly detailed background, no text, no watermark")
ATTENTE_GRATUIT = 46


def generer(prompt: str, seed: int, cle: str | None) -> Image.Image:
    q = urllib.parse.quote(prompt)
    params = {"width": 1280, "height": 720, "nologo": "true", "seed": seed}
    if cle:
        params["model"] = "flux"
    url = f"https://image.pollinations.ai/prompt/{q}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {cle}"} if cle else {})
    for essai in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
                if not cle:  # retire la bande du filigrane (bas de l'image)
                    img = img.crop((0, 0, img.width, int(img.height * 0.92)))
                return img
        except urllib.error.HTTPError as e:
            attente = 50 if e.code in (402, 429) else 15 * (essai + 1)
            print(f"   ↻ HTTP {e.code}, nouvel essai dans {attente}s", flush=True)
            time.sleep(attente)
        except Exception as e:  # réseau
            print(f"   ↻ {type(e).__name__}, nouvel essai", flush=True)
            time.sleep(15 * (essai + 1))
    raise RuntimeError("génération impossible")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("--scenes", help="numéros séparés par des virgules")
    ap.add_argument("--refaire", action="store_true", help="remplace les images existantes")
    ap.add_argument("--graine", type=int, default=1000)
    a = ap.parse_args()
    dossier = Path(a.dossier).resolve()
    _, scenes, _ = lire_script(dossier)
    choix = {int(x) for x in a.scenes.split(",")} if a.scenes else None
    cle = os.environ.get("POLLINATIONS_KEY")
    fichier = dossier / "prompts.json"  # descriptions en anglais (meilleur résultat)
    prompts = __import__("json").loads(fichier.read_text()) if fichier.exists() else {}
    a_faire = [sc for sc in scenes
               if (choix is None or sc.n in choix) and (a.refaire or trouver_media(dossier, sc) is None)]
    print(f"{len(a_faire)} image(s) à générer" + ("" if cle else f" (≈ {len(a_faire) * ATTENTE_GRATUIT // 60} min en gratuit)"))
    (dossier / "images").mkdir(exist_ok=True)
    for k, sc in enumerate(a_faire):
        debut = time.time()
        prompt = f"{STYLE}. Scene: {prompts.get(str(sc.n)) or sc.visuel or sc.texte}"
        try:
            img = generer(prompt, a.graine + sc.n, cle)
        except RuntimeError:
            print(f"✗ scène {sc.n:02d} : échec, on passe")
            continue
        sortie = dossier / "images" / f"{sc.n:02d}.jpg"
        img.save(sortie, quality=92)
        print(f"✓ scène {sc.n:02d} ({k + 1}/{len(a_faire)}) : {sc.visuel[:60]}", flush=True)
        if not cle and k + 1 < len(a_faire):
            time.sleep(max(0, ATTENTE_GRATUIT - (time.time() - debut)))


if __name__ == "__main__":
    main()
