# Linux Audio Manager

Linux Audio Manager est une application de gestion audio pour Linux qui combine l'approche simple d'un controle de volume avec la vision plus technique d'un patchbay audio comme Helvum.

L'objectif est de proposer une interface unique pour piloter le volume, visualiser le routage audio et creer des usages plus avances, comme l'envoi d'un meme son vers plusieurs peripheriques audio en meme temps.

## Vision du projet

Aujourd'hui, les outils audio Linux sont souvent fragmentes:

- un outil pour monter ou baisser le volume;
- un autre pour voir les connexions audio;
- des reglages separes pour chaque application ou chaque peripherique.

Linux Audio Manager vise a reunir ces usages dans une seule application, plus lisible pour un utilisateur classique, mais suffisamment puissante pour les utilisateurs avances.

## Objectifs

- Centraliser le controle du volume systeme, des peripheriques et des applications.
- Afficher la topologie audio sous forme de graphes, noeuds et connexions.
- Permettre le routage manuel ou automatique du son.
- Autoriser la lecture simultanee sur plusieurs sorties audio.
- Garder une interface simple pour les actions courantes.
- Proposer des profils et des regles persistantes.

## Fonctionnalites principales

### 1. Controle de volume unifie

- Volume global du systeme.
- Volume par logiciel actif utilisant l'audio.
- Volume par peripherique de sortie ou d'entree.
- Sourdine rapide.
- Raccourcis clavier et acces rapide depuis la barre systeme.

### 2. Vue audio type patchbay

- Visualisation des flux audio sous forme de noeuds.
- Connexions entre applications, sources, effets et sorties.
- Activation ou suppression des liaisons par glisser-deposer.
- Lecture simplifiee de la chaine audio active.

### 3. Lecture sur plusieurs peripheriques en meme temps

- Choix de plusieurs sorties audio simultanees.
- Groupe de peripheriques pour diffuser un meme flux.
- Gestion de la priorite ou du peripherique principal.
- Option de duplication du son pour bureau, casque, enceintes ou carte externe.

### 4. Regles et profils

- Profils par contexte: travail, jeu, musique, reunion, cinema.
- Routage automatique selon l'application ou le peripherique branche.
- Memorisation des configurations favorites.
- Restauration de l'etat audio au demarrage.

### 5. Outils avances

- Gestion des appareils connectes et de leur statut.
- Detection des changements de peripheriques.
- Reaffectation rapide d'une application vers une autre sortie.
- Historique basique des changements audio.

## Cas d'usage

- Ecouter de la musique en meme temps sur des enceintes et un casque.
- Envoyer une visio vers un casque tout en gardant le son du bureau sur une autre sortie.
- Basculer automatiquement le son d'un jeu vers un DAC USB quand il est branche.
- Couper le son d'une application sans toucher au volume general.
- Reconnecter rapidement les liens audio apres une deconnexion de peripherique.

## Utilisateurs cibles

- Utilisateurs Linux qui veulent un meilleur controle audio sans complexite inutile.
- Creatifs, gamers et streamers qui utilisent plusieurs sorties audio.
- Utilisateurs avances qui connaissent PipeWire ou des outils comme Helvum.
- Equipes techniques qui ont besoin d'un controle precis du routage audio.

## Perimetre MVP

La premiere version doit se concentrer sur les fonctions indispensables:

- afficher les peripheriques audio disponibles;
- regler le volume global et par application;
- visualiser les connexions audio;
- connecter ou deconnecter des flux;
- creer un groupe de sorties pour lecture simultanee;
- sauvegarder et restaurer une configuration simple.

## Fonctionnalites futures

- equaliseur integre;
- normalisation du volume entre peripheriques;
- routage conditionnel selon l'heure ou le profil actif;
- integration avec les notifications du systeme;
- vue detaillee des latences audio;
- presets exportables et importables;
- mode accessible pour navigation clavier complete.

## Architecture proposee

### Backend audio

- Basee sur PipeWire, avec compatibilite avec les usages PulseAudio si necessaire.
- Utilisation de la couche de gestion de session pour lire l'etat audio et modifier le routage.
- Synchronisation des changements de connexion avec l'etat du systeme.

### Moteur de routage

- Construction d'un graphe des sources, sinks, applications et effets.
- Gestion des groupes de sorties pour le multi-peripherique.
- Strategie de duplication des flux avec prise en compte de la latence.

### Interface utilisateur

- Vue simple pour les actions rapides.
- Vue avancee pour le graph audio.
- Barre laterale ou panneau principal avec peripheriques, applications et profils.

### Stockage local

- Sauvegarde des profils utilisateur.
- Regles de routage persistantes.
- Etat de la derniere session.

## Structure GNOME recommandee

Le projet suit une arborescence GNOME classique pour rester compatible avec Meson, GTK4, libadwaita et Flatpak:

- `src/` pour le code de l'application;
- `data/` pour les metadonnees, schemas, fichiers UI et icones;
- `data/ui/` pour les interfaces GTK Builder;
- `data/icons/hicolor/scalable/apps/` pour l'icone principale;
- `po/` pour les traductions;
- `flatpak/` pour le manifeste de distribution;
- `build-aux/` pour les aides de build;
- `tests/` pour les tests;
- `docs/` pour la documentation projet.

Les details de cette arborescence sont documentes dans [docs/gnome-structure.md](docs/gnome-structure.md).

## Lancement rapide

Le prototype peut se lancer avec `make` ou `make run` depuis la racine du projet.
La cible lance l'interface GTK4/libadwaita en mode test.

- `make` ou `make run` : lance l'interface.
- `make check` : verifie la syntaxe des fichiers Python.

Prerequis locaux: Python 3, PyGObject, GTK4 et libadwaita.

---

## Installation

### Option 1 : Flatpak (Recommandé)

```bash
# Installation depuis Flathub (une fois publiée)
flatpak install flathub io.github.linux-audio-manager
flatpak run io.github.linux-audio-manager

# Ou en une commande
flatpak run --file-forwarding io.github.linux-audio-manager @@u %F @@
```

**Avantages** :
- ✅ Installation isolée, zéro dépendance système
- ✅ Permissions contrôlées (PipeWire accès déclaré)
- ✅ Mises à jour automatiques
- ✅ Multi-version possible

### Option 2 : Paquet Debian/Ubuntu

```bash
# Build et installation .deb
make deb
sudo dpkg -i build/linux-audio-manager_0.1.0_amd64.deb

# Ou directement
sudo apt install ./build/linux-audio-manager_0.1.0_amd64.deb

# Lancer l'app
linux-audio-manager
```

**Dépendances** : `python3`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `pipewire`

### Option 3 : Installation source (développeurs)

```bash
# Cloner le repo
git clone https://github.com/yourusername/linux-audio-manager.git
cd linux-audio-manager

# Installation éditable via pip
pip install -e .

# Ou directement
python3 -m src.main
```

### Option 4 : Build Flatpak local

```bash
# Builder le manifest
flatpak-builder --user --install-deps-from=flathub \
  --force-clean build-dir io.github.linux-audio-manager.yml

# Tester
flatpak run io.github.linux-audio-manager

# Désinstaller
flatpak uninstall io.github.linux-audio-manager
```

---

## Prérequis système

- **Python** 3.8+
- **GTK4** (4.0+)
- **libadwaita** (1.0+)
- **PipeWire** (0.3+) pour la gestion audio
- **D-Bus** pour la communication système

### Installation des dépendances

#### Fedora
```bash
sudo dnf install python3 gtk4-devel libadwaita-devel pipewire
```

#### Ubuntu/Debian
```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pipewire
```

#### Arch
```bash
sudo pacman -S python gtk4 libadwaita pipewire
```

---

## Développement

### Structure du projet

```
.
├── src/
│   ├── __init__.py           # Métadonnées app (APP_ID, APP_NAME, VERSION)
│   ├── main.py               # Point entrée, gestion GApplication
│   ├── window.py             # UI principale (GTK4 + libadwaita)
│   ├── audio.py              # API PipeWire (pw-dump, wpctl, pw-link)
│   └── config.py             # Persistance config (~/.config/)
├── data/
│   ├── io.github.linux-audio-manager.desktop      # Entrée système
│   ├── io.github.linux-audio-manager.metainfo.xml # Métadonnées AppStream
│   └── icons/                # Icônes
├── po/
│   ├── LINGUAS               # Langues support
│   ├── linux-audio-manager.pot
│   └── fr.po
├── flatpak/
│   └── io.github.linux-audio-manager.yml  # Manifest Flatpak
├── debian/
│   └── deb-builder.py        # Script build .deb
├── tests/                    # Tests unitaires
└── docs/                     # Documentation
```

### Développer localement

```bash
# Cloner et setup
git clone https://github.com/yourusername/linux-audio-manager.git
cd linux-audio-manager

# Vérifier la syntaxe
make check

# Lancer l'app
make run

# Ou directement
python3 -m src.main
```

### Contribution

1. Fork le repo
2. Créer une branche : `git checkout -b feature/ma-feature`
3. Committer : `git commit -m "Add: description"`
4. Pousser : `git push origin feature/ma-feature`
5. Ouvrir une Pull Request

Voir [docs/changelog.md](docs/changelog.md) pour le format changelog.

---

## Soumission Flathub

Voir [FLATHUB_SUBMISSION_PLAN.md](FLATHUB_SUBMISSION_PLAN.md) pour le processus complet de soumission à Flathub.

### 📚 Navigation Documentation

➡️ **[Accès rapide : INDEX.md](docs/INDEX.md)** — Index complète de toute la documentation

### Documentation clé
- **Roadmap** : [docs/roadmap.md](docs/roadmap.md) — Vision complète v0.1-v1.0+, jalons, priorités
- **Architecture** : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Design modulaire, responsabilités, integration points
- **Plan détaillé Partie 2** : [docs/partie2-plan.md](docs/partie2-plan.md) — Implémentation 5 sections (routage, multi-device, DSP, productivité, fiabilité)
- **Décisions techniques** : [docs/DECISIONS.md](docs/DECISIONS.md) — Choix database, UI, EQ engine, macros, notifications, hotkeys
- **Guide v0.2** : [docs/V02-QUICKSTART.md](docs/V02-QUICKSTART.md) — Plan implémentation détaillé, code skeletons, timeline
- **Changelog** : [CHANGELOG.md](CHANGELOG.md) — Historique versions
- **Règles changelog** : [docs/changelog.md](docs/changelog.md) — Format contributions

### Statut

- ✅ **v0.1.0** (COMPLÈTÉE) : Interface GNOME, contrôle audio simple, routage basique, multi-sortie, persistance
- ⏳ **v0.2** (Planifiée) : Règles intelligentes, zones audio, historique, diagnostics, undo/redo
- 📅 **v0.3+** (Roadmap) : EQ, normalisation, scénarios, raccourcis, Wayland

## Contraintes techniques importantes

- La lecture simultanee sur plusieurs sorties peut generer des decalages de latence.
- Chaque peripherique peut imposer un taux d'echantillonnage different.
- Le routage doit rester stable lors des connexions et deconnexions de materiel.
- L'application doit rester legere et ne pas monopoliser le CPU.

## Principes UX

- Priorite a la lisibilite des routes audio.
- Actions courantes accessibles en un minimum de clics.
- Mode simple pour les utilisateurs debutants et mode avance pour les utilisateurs experts.
- Feedback immediat lors des changements de volume ou de routage.

## Roadmap suggeree

### Phase 1

- lecture de l'etat audio;
- affichage des peripheriques;
- controles de volume;
- patchbay de base.

### Phase 2

- multi-peripherique;
- profils sauvegardes;
- regles automatiques;
- raccourcis et tray icon.

### Phase 3

- traitements audio supplementaires;
- meilleure gestion de la latence;
- personnalisation avancee;
- import/export de profils.

## Definition de succes

Le projet sera considere comme utile si un utilisateur peut:

- comprendre rapidement quelles applications envoient du son vers quels peripheriques;
- activer la lecture sur plusieurs sorties sans manipulations complexes;
- regler le volume et le routage sans passer par plusieurs outils differents;
- restaurer facilement sa configuration audio habituelle.

## Questions ouvertes

- Faut-il cibler PipeWire uniquement ou garder une compatibilite plus large?
- L'interface doit-elle etre plutot GTK/libadwaita ou Qt?
- Le multi-peripherique doit-il fonctionner par duplication simple ou avec compensation de latence?
- Faut-il une version tray-only ou une application fenetre complete?

## Resume

Linux Audio Manager est pense comme un pont entre un controle de volume classique et un outil de routage audio avance. Le produit apporte en plus la lecture sur plusieurs peripheriques, les profils, les regles automatiques et une vue claire de tout le graphe audio.