# Format du script

Un seul fichier `script.md` par vidéo. **Tu lis uniquement les lignes qui commencent par `- `.**
Les lignes qui commencent par `>` servent au montage.

```markdown
# Titre de la vidéo

short: 8-18 | Titre du Short 1        ← scènes 8 à 18 = un Short (moins de 60 s)
short: 33-45 | Titre du Short 2

## Accroche

- Lundi, tu te lèves à six heures.     ← une scène = une phrase lue
> visuel: jeune homme qui se réveille à l'aube, lumière bleue
> effet: zoom_in
- Et jeudi, c'est fini.
> visuel: personnage allongé, téléphone en main
> impact: oui                           ← flash, tremblement et boum
```

## Les directives `>`

| Clé | Rôle | Valeurs |
|---|---|---|
| `visuel` | Ce que doit montrer l'image | texte libre |
| `effet` | Mouvement de caméra | `zoom_in`, `zoom_out`, `pan_gauche`, `pan_droite`, `monte`, `descend`, `fixe` |
| `impact` | Moment fort | `oui` |
| `image` | Nom de fichier précis (sinon `images/NN.jpg`) | ex. `bambou.png`, `combat.mp4` |
| `debut` | Pour un extrait vidéo : seconde de départ | ex. `12.5` |

Les images sont trouvées automatiquement par numéro de scène : `images/01.jpg`, `images/02.png`, `images/03.mp4`…
La commande `lecture` génère `rendu/visuels.md`, la liste à cocher de tous les visuels.

## Règles d'écriture de la chaîne

1. **Accroche en moins de 10 secondes** : une situation où le spectateur se reconnaît, puis une rupture.
2. **Des phrases courtes.** Une idée par phrase, donc une image par phrase. Le rythme vient des coupes.
3. **On tutoie.** On parle à une seule personne, comme un grand frère.
4. **Du concret.** Chaque vidéo donne au moins une méthode applicable ce soir même.
5. **Une histoire ou une image forte** au milieu (une parabole, une anecdote, une métaphore).
6. **Une fin qui marque** : une phrase à retenir, puis l'appel à s'abonner.
7. **Rien d'inventé présenté comme un fait** : pas de fausses études ni de fausses citations. Une légende se présente comme une légende (« on raconte que… »).
8. Entre **600 et 1 400 mots**, soit 5 à 12 min lus lentement, avec des pauses.
