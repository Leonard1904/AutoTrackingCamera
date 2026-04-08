# Auto Tracking for basketball

Ce `README.md` décrit :
- les **fichiers/dossiers** présents dans ce dépôt
- les **étapes à suivre** pour exécuter le programme sur l’équipement 

## Arborescence du dossier (racine)

- `README.md` : ce guide
- `main.py` : point d’entrée
- `config.py` : configuration (classe `SystemConfig`)
- `core/` : logique applicative (boucle principale, tracking, types)
- `hardware/` : accès caméras & servo et intégration Hailo côté matériel
- `io_utils/` : affichage & enregistrement (vidéo + CSV)
- `models/` : modèles (incluant les fichiers **`.hef`** utilisés par Hailo)
- `hailo_apps/` : composants & ressources liés à la pipeline Hailo (SDK/app code)
- `enregistrements/` : dossier de sortie (vidéos/CSV) créé & alimenté à l’exécution

## Prérequis (sur l’équipement)

- **OS** : Linux sur la machine cible (ex. Raspberry Pi) avec accès caméra et accélérateur Hailo
- **Carte Hailo** : drivers installés et device accessible 
- **Python** : Python 3.x disponible sur la machine
- **Dépendances système** : GStreamer + bindings GI, OpenCV (selon votre image système)

> Important : l’exécution “réelle” avec Hailo nécessite un environnement système cohérent (drivers/kernel/modules et permissions). Une exécution sur PC Windows n’est généralement pas adaptée pour piloter la carte Hailo.

## Installation (recommandé : environnement virtuel Python)

Depuis la racine du projet sur la machine cible.

### 1) Créer et activer un environnement virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) Installer les dépendances Python nécessaires à Hailo

Ce projet s’appuie sur la stack Python Hailo (exécution de modèles **`.hef`**) et sur des dépendances de vision (OpenCV/Numpy, etc.).


## Configuration (modèles `.hef`, caméras, sorties)

La configuration se fait dans `config.py` via `SystemConfig`.

Points à vérifier avant de lancer :
- **Chemin du modèle Hailo** : `hef_path` doit pointer vers un fichier `.hef` (ex. `models/<modele>.hef`)
- **Caméras** : index/résolutions/fps (selon votre matériel)
- **Dossier de sortie** : `output_dir` (par défaut `enregistrements`)

## Exécuter le programme

Une fois l’environnement activé :

```bash
python main.py
```

## Sorties

Les enregistrements et métadonnées sont écrits dans `enregistrements/` (ou le dossier défini par `output_dir`).

## Dépannage rapide

- **Hailo non détecté** : vérifier la présence de `/dev/hailo0`, l’installation des drivers et les permissions
- **Modèle `.hef` introuvable** : vérifier `hef_path` dans `config.py` et l’existence du fichier dans `models/`
- **Problèmes caméra** : vérifier l’accès caméra et la compatibilité des bibliothèques (ex. Picamera2 si Raspberry Pi)

