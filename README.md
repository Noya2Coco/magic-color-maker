# Version Termux — Générateur de coloriage magique

Cette variante est prévue pour Android + Termux et n'utilise **ni Streamlit, ni Pandas, ni FastAPI, ni ReportLab**.

Le serveur web utilise uniquement la bibliothèque standard de Python. Le navigateur Android sert d'interface.

## 1. Préparer Termux

```bash
pkg update
pkg install python x11-repo
pkg install opencv python-opencv-python
```

Vérifie OpenCV et NumPy :

```bash
python -c "import cv2, numpy; print('cv2', cv2.__version__, 'numpy', numpy.__version__)"
```

## 2. Installer Pillow

Depuis ce dossier :

```bash
pip install -r requirements-termux.txt
```

Si Pillow tente de compiler et échoue, exécute d'abord :

```bash
pkg search pillow
```

et utilise le paquet Termux proposé s'il en existe un dans tes dépôts activés. Ensuite relance simplement le serveur.

Vérification :

```bash
python -c "from PIL import Image; print('Pillow OK')"
```

## 3. Lancer

```bash
python server.py
```

Puis ouvre dans le navigateur Android :

```text
http://127.0.0.1:8000
```

Pour changer le port :

```bash
COLORIAGE_PORT=8080 python server.py
```

Par sécurité, le serveur écoute uniquement sur `127.0.0.1` par défaut.

## Fonctionnalités

- import PNG/JPEG/WEBP ;
- valeur maximale = nombre maximal de couleurs ;
- simplification et comparaison original/simplifié ;
- augmentation/réduction du nombre de couleurs avant validation ;
- détection des régions connexes ;
- niveaux de complexité ;
- nombres, additions, soustractions, multiplications, divisions et mélange ;
- régénération des calculs sans refaire la segmentation ;
- aperçu élève et corrigé ;
- téléchargement PNG, SVG, PDF et corrigé PNG.

## Différences avec la version Streamlit

Cette variante stocke les projets uniquement en mémoire tant que `server.py` tourne. Un redémarrage efface les sessions, mais les fichiers déjà téléchargés sur le téléphone restent évidemment présents.

Le PDF est généré par Pillow afin d'éviter ReportLab sur Termux.
