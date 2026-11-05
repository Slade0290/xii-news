# XII News

Le monde en 12 infos, chaque matin sur Instagram : [@xii.news](https://www.instagram.com/xii.news/).

## Comment ça marche

1. Chaque matin, Claude fait la veille et dépose l'édition du jour dans `daily/AAAA-MM-JJ.json`.
2. Ce dépôt déclenche le robot **Publier XII News** (`.github/workflows/publish.yml`), qui :
   - fabrique les visuels (`scripts/render.py`) : un carrousel de 13 images (sommaire + 12 infos sourcées) et 12 stories ;
   - les met en ligne sur la branche `media` (Instagram a besoin d'images accessibles publiquement) ;
   - publie le carrousel avec la légende et les sources, puis les 12 stories (`scripts/publish.py`), via l'API officielle d'Instagram.
3. L'avancement est noté dans `published/`. Une édition n'est jamais publiée deux fois.

Un second robot, **Renouveler le jeton Instagram**, prolonge le jeton d'accès chaque lundi.

## Réglages

Dans **Settings → Secrets and variables → Actions** :

| Nom | Type | Rôle |
|---|---|---|
| `IG_ACCESS_TOKEN` | Secret | Jeton Instagram (Meta for Developers → ton app → Instagram → « Generate token »). Sans lui, le robot fait un essai à blanc. |
| `SECRETS_PAT` | Secret, facultatif | Jeton GitHub (fine-grained, ce dépôt, droit *Secrets : Read and write*) pour que le renouvellement enregistre lui-même le nouveau jeton. |
| `IG_API_VERSION` | Variable, facultative | Version de l'API Instagram, par ex. `v23.0`. |

## Lancer à la main

Onglet **Actions → Publier XII News → Run workflow** : choisis la date, coche « Essai à blanc » pour tout vérifier sans publier, ou « Republier » pour forcer.

## Tester les visuels en local

```bash
pip install pillow requests
python3 scripts/render.py examples/exemple.json out brand/xii.jpg
```

Les polices (Archivo, JetBrains Mono) sont sous licence SIL Open Font License et téléchargées depuis Google Fonts.
