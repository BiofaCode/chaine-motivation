# Les visuels

Chaque scène du script a une ligne `> visuel:` qui décrit l'image recherchée.
`python3 outils/monter.py lecture videos/NNN-sujet` produit `rendu/visuels.md`, une liste à cocher.
Dépose les fichiers dans `videos/NNN-sujet/images/` sous les noms `01.jpg`, `02.png`, `03.mp4`…

Formats acceptés : **jpg, png, webp** (images) et **mp4, mov, webm, mkv** (extraits).
Résolution conseillée : au moins 1280 px de large. Le montage recadre et anime tout seul.

## Option A : images et extraits d'animés que tu fournis

C'est ton choix pour la chaîne. Deux remarques pour que ça tienne dans la durée :
- **Ta voix et ton propos doivent porter la vidéo.** Les images illustrent un commentaire original. C'est aussi ce que YouTube regarde pour accepter une chaîne dans le Programme Partenaire (règle du « contenu réutilisé »).
- **Des plans courts et variés** plutôt que de longues scènes d'un même animé. Le montage fait déjà ça : un plan par phrase, recadré, étalonné et animé.
- Sur une œuvre protégée, une revendication Content ID reste possible : les revenus de la vidéo peuvent alors aller aux ayants droit. Garde une trace de la provenance de tes extraits.

## Option B : images générées gratuitement (100 % à toi, sans risque de droits)

Des outils gratuits à utiliser depuis ton navigateur :
- **Gemini** (gemini.google.com) : génération d'images gratuite avec un compte Google.
- **Bing Image Creator / Microsoft Designer** : gratuit avec un compte Microsoft.
- **ChatGPT** (version gratuite) : quelques images par jour.

Modèle de prompt pour garder un style cohérent sur toute la chaîne :

```
Anime style illustration, cinematic, dramatic lighting, dark moody colors with warm golden highlights,
16:9, highly detailed, emotional atmosphere, no text.
Scene: <colle ici la ligne « visuel » du script>
```

Pour un Short, remplace `16:9` par `9:16`. Le montage accepte les deux formats.

## Option C : génération automatique par Claude (activée)

```bash
python3 outils/images.py videos/NNN-sujet                      # génère toutes les images manquantes
python3 outils/images.py videos/NNN-sujet --scenes 4,12 --refaire   # refait des images ratées
```
- Les descriptions en anglais sont dans `prompts.json` (le modèle comprend mieux l'anglais). Le personnage récurrent y est décrit de la même façon partout : *a young man with short messy black hair and a dark hoodie*.
- En gratuit : 1 image toutes les 45 s (environ 50 min pour une vidéo), en 1024 px, le filigrane est recadré.
- Une clé gratuite Pollinations (enter.pollinations.ai), stockée dans la variable `POLLINATIONS_KEY`, retire ces limites.

## Option D : extraits de films libres (Sintel, etc.)
Voir [CREDITS.md](../CREDITS.md). Un extrait `NN.mp4` passe avant l'image `NN.jpg` de la même scène.
S'il est plus court que la phrase, sa dernière image reste figée jusqu'à la fin. Pense à mettre la ligne de crédit dans la description.

## Mélanger les options
On peut tout à fait mélanger : extraits d'animés pour les moments forts (`impact`), images générées pour le reste.
