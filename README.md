# Générateur de coloriage magique — MVP

Application locale permettant de transformer une illustration simple en coloriage magique.

## Fonctionnalités
- upload PNG/JPG/JPEG/WEBP ;
- valeur maximale = nombre maximal de couleurs ;
- quantification des couleurs ;
- comparaison originale / simplifiée et validation ;
- détection de cellules par composantes connexes ;
- filtre des micro-zones par niveau de complexité ;
- placement du texte via distance transform ;
- nombres, additions, soustractions, multiplications, divisions, mélange ;
- respect de l'opérande maximum ;
- génération reproductible via seed ;
- version élève + corrigé ;
- exports PNG, SVG, PDF A4.

## Lancement

```bash
python -m venv .venv
```

### Windows
```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Linux/macOS
```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre généralement sur `http://localhost:8501`.

## Limites du MVP
- la fusion manuelle de deux couleurs n'est pas encore implémentée ;
- les petites zones sont actuellement ignorées plutôt que fusionnées intelligemment avec une voisine ;
- le SVG repose sur des polygones simplifiés OpenCV ;
- le PDF utilise le rendu raster pour le dessin principal ;
- pour les images très photographiques, la qualité est inférieure à celle obtenue sur des illustrations à aplats.

## Évolution recommandée
Pour une version production : frontend React/Vite + backend FastAPI, éditeur manuel de palette/cellules, fusion interactive de zones, sauvegarde de projets et SVG 100 % vectoriel.
