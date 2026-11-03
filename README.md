# 🔥 Chaîne motivation (nom à trouver)

Chaîne YouTube en français, sans visage : je documente ma vie (job, école, agence, projets, sport) avec discipline et méthodes concrètes. Stratégie : [docs/strategie.md](docs/strategie.md).
Format : **vidéos de 5 à 12 min**, plus **2 ou 3 Shorts** tirés de chaque vidéo, avec une ambiance animé/manga.
Rythme : **1 vidéo par semaine.**

## Qui fait quoi

| | Toi | Claude |
|---|---|---|
| Sujets | Tu choisis parmi les propositions | Propose les sujets ([docs/idees-sujets.md](docs/idees-sujets.md)) |
| Script | Tu relis et corriges | Écrit le script avec le découpage en scènes |
| Voix | **Tu enregistres** ([conseils](docs/enregistrer-audio.md)) | Nettoie la voix |
| Images | Tu déposes tes images ou extraits (voir [docs/images.md](docs/images.md)) | Liste les visuels à trouver, scène par scène |
| Montage | — | Synchro, zooms, sous-titres animés, musique, bruitages, Shorts |
| Publication | Tu publies | Titre, description, tags, idée de miniature |

## La semaine type

1. **Lundi** : Claude propose 3 sujets, tu en choisis un.
2. **Mardi** : Claude écrit `videos/NNN-sujet/script.md`, tu relis.
3. **Mercredi** : tu lis `rendu/texte_a_lire.txt` au micro et tu envoies le fichier audio. Tu déposes les images listées dans `rendu/visuels.md`.
4. **Jeudi-vendredi** : Claude lance le montage et vérifie le résultat.
5. **Week-end** : tu valides et tu publies.

## Commandes

```bash
pip install -r requirements.txt          # une seule fois (ffmpeg doit être installé)

python3 outils/monter.py nouvelle 002-mon-sujet          # crée le dossier d'une vidéo
python3 outils/monter.py lecture videos/002-mon-sujet    # texte à lire + liste des visuels
python3 outils/images.py videos/002-mon-sujet            # génère les images manquantes (gratuit)
python3 outils/monter.py tout    videos/002-mon-sujet    # vidéo longue + Shorts
```

Résultats dans `videos/NNN-sujet/rendu/` :
- `NNN-sujet.mp4` : la vidéo YouTube en 1920×1080
- `short_01.mp4`, `short_02.mp4`… : les Shorts en 1080×1920
- `controle_*.jpg` : une planche d'images pour vérifier le montage d'un coup d'œil

## Ce que fait le montage automatique

- **Voix** : coupe-bas, débruitage, compression, volume calé sur la norme YouTube (-14 LUFS).
- **Synchro** : transcription mot à mot avec Whisper, alignée sur le script. Sans Whisper, l'outil se cale sur les pauses de la voix.
- **Images** : mouvement fluide sur chaque plan (zoom avant ou arrière, panoramique, montée, descente), tremblement et flash sur les moments forts (`impact`), étalonnage sombre façon cinéma, grain et vignette.
- **Extraits vidéo** : acceptés à la place d'une image (`images/NN.mp4`), recadrés et étalonnés comme le reste.
- **Sous-titres** : 1 à 3 mots à la fois, en majuscules, le mot prononcé surligné en jaune.
- **Son** : musique de fond baissée automatiquement quand tu parles, whoosh et impacts.
- **Image manquante** : une carte provisoire avec la description du visuel, pour voir le rythme avant d'avoir toutes les images.

## Organisation

```
docs/        guides : format du script, enregistrement, images, idées de sujets
outils/      monter.py (le moteur de montage), images.py (génération d'images)
videos/      un dossier par vidéo (script.md, audio/, images/, rendu/)
musique/     musiques libres de droits (YouTube Audio Library, etc.)
sfx/         bruitages (générés automatiquement si vide)
polices/     Anton et Montserrat (licence OFL, libres)
```
