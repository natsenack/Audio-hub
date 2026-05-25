# Guide de Distribution - Linux Audio Manager

Ce guide explique comment préparer et distribuer l'application via Flathub ou en tant que paquet Debian.

## 📦 Distribution Flathub (Recommandé)

Flathub est le magasin officiel des applications GNOME. C'est le meilleur moyen de distribuer votre app auprès d'une large audience Linux.

### Prérequis

```bash
# Installer Flatpak
sudo apt install flatpak

# Ajouter Flathub
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo

# Installer le builder
flatpak install -y flathub org.flatpak.Builder
```

### 1. Tester localement

```bash
make build-flatpak
flatpak run io.github.linux-audio-manager
```

### 2. Valider le manifest

```bash
make lint-manifest
```

### 3. Soumettre à Flathub

Voir **FLATHUB_SUBMISSION.md** pour le processus détaillé.

Résumé:
1. Fork https://github.com/flathub/flathub (branche `new-pr`)
2. Créez un répertoire `io/github/linux-audio-manager/`
3. Copiez-y `io.github.linux-audio-manager.json` et `flathub.json`
4. Ouvrez une Pull Request
5. Attendez la révision et les tests

**Timeline typique:** 1-4 semaines (les reviewers sont bénévoles)

---

## 📥 Paquet Debian/Ubuntu

Pour distribuer sur les systèmes Debian/Ubuntu, vous pouvez créer un paquet `.deb`.

### Tester la construction

```bash
python3 debian/deb-builder.py
```

Ou manuellement:
```bash
dpkg-buildpackage -us -uc
```

### Installer le paquet

```bash
sudo dpkg -i linux-audio-manager_*.deb
sudo apt install -f  # Installer les dépendances manquantes
```

### Distribuer le paquet

Pour publier des paquets `.deb`:

1. **PPA Personnel (Ubuntu)**
   ```bash
   # Créer un PPA sur Launchpad
   # Upload du paquet source avec clés GPG
   ```

2. **Repository APT Custom**
   ```bash
   # Créer un serveur APT et installer via sources.list
   ```

3. **Releases GitHub**
   ```bash
   # Attacher les .deb aux releases GitHub
   ```

---

## 🐧 Installation Système

Pour installer manuellement sur votre machine:

```bash
make install     # Installe dans /usr/local/
make uninstall   # Désinstalle
```

---

## 🔧 Configuration du Repository GitHub

Avant la soumission, mettez à jour les URLs:

1. **pyproject.toml**
   ```toml
   Homepage = "https://github.com/yourusername/linux-audio-manager"
   Repository = "https://github.com/yourusername/linux-audio-manager.git"
   ```

2. **data/io.github.linux-audio-manager.desktop**
   ```ini
   # Vérifier que X-GNOME-Bugzilla-Bugzilla pointe au bon repo
   ```

3. **debian/control**
   ```
   Maintainer: Your Name <your-email@example.com>
   ```

---

## 📋 Checklist de Soumission Flathub

- [ ] Manifest construit sans erreurs localement
- [ ] `make lint-manifest` passe (0 erreurs, warnings acceptables)
- [ ] App fonctionne correctement: `flatpak run io.github.linux-audio-manager`
- [ ] `.metainfo.xml` valide et complet
- [ ] `.desktop` correctement formaté
- [ ] LICENSE inclus (GPL-3.0-or-later)
- [ ] Repository GitHub public avec tous les sources
- [ ] README docummente l'app
- [ ] Screenshots dans `.metainfo.xml` (recommandé)
- [ ] Pas de fichiers source ou binaires dans la soumission Flathub

---

## 🔒 Vérification et Sécurité

### Permissions Flatpak

L'app demande:
- `--share=ipc` — Accès mémoire partagée (nécessaire pour GTK)
- `--socket=wayland` — Interface Wayland
- `--socket=fallback-x11` — Interface X11
- `--system-talk-name=org.freedesktop.DBus` — Accès D-Bus système pour PipeWire

Ces permissions sont minimales et nécessaires.

### Licence

L'app est sous **GPL-3.0-or-later**. Assurez-vous que:
- Le fichier LICENSE inclut le texte GPL-3.0 complet
- Toutes les dépendances Python ont des licences compatibles

---

## 🆘 Support

- **Flathub Documentation:** https://docs.flathub.org/
- **Flatpak Documentation:** https://docs.flatpak.org/
- **Flathub Matrix:** https://matrix.to/#/#flathub:matrix.org
- **Issues GitHub:** https://github.com/yourusername/linux-audio-manager/issues

---

## Résumé des Commandes

```bash
# Développement
make run              # Lancer l'app
make check            # Valider le Python
make clean            # Nettoyer le cache

# Distribution
make build-flatpak    # Construire pour Flathub
make lint-manifest    # Valider le manifest
make build-deb        # Construire paquet Debian

# Installation système
make install          # Installer localement
make uninstall        # Désinstaller
```

---

**Prêt? Commencez par `make build-flatpak` pour tester!**
