# Flathub Submission Ready - Linux Audio Manager

**Status** : ✅ **READY FOR SUBMISSION**  
**Date** : 25 mai 2026  
**App ID** : `io.github.linux-audio-manager`  
**Version** : 0.1.0

---

## 📋 Checklist finale avant soumission

- [x] Tous les fichiers critiques présents
- [x] Syntaxe Python valide
- [x] Licence GPL-3.0 conforme
- [x] App ID cohérent (io.github.linux-audio-manager)
- [x] .desktop file valide
- [x] .metainfo.xml (AppStream) présent
- [x] Manifest Flatpak (YAML) créé
- [x] flathub.json configuration présent
- [x] pyproject.toml correct
- [x] README avec instructions build
- [x] Conformité GNOME vérifiée (9/10)

---

## 🚀 Instructions de soumission

### Étape 1 : Préparer le repository GitHub

**Résumé** : Vous devez avoir un repository GitHub public avec :
- [ ] Code source complet
- [ ] Tag `v0.1.0` créé et poussé
- [ ] Description et topics configurés

**Commandes** :

```bash
cd /mnt/wwn-0x5000000000002733-part2/1.*linux*audio*manager

# Initialiser git si pas encore fait
git init
git add .
git commit -m "Initial commit: Linux Audio Manager v0.1.0"

# Créer le tag
git tag -a v0.1.0 -m "v0.1.0 - Initial stable release"

# Ajouter GitHub origin (remplacer yourusername)
git remote add origin https://github.com/yourusername/linux-audio-manager.git
git push -u origin main
git push origin v0.1.0
```

**Configuration GitHub** :
- Description: "A modern audio management application for Linux combining simple volume control with advanced PipeWire routing"
- Topics: `audio`, `pipewire`, `gtk`, `gnome`, `linux`, `volume-control`
- License: GPL-3.0

### Étape 2 : Créer une issue de soumission Flathub

1. Aller à : https://github.com/flathub/flathub/issues/new

2. Choisir template : **"New application"**

3. Remplir le formulaire :

```
**App name** : Linux Audio Manager
**App ID** : io.github.linux-audio-manager

**Source location (git)** : https://github.com/yourusername/linux-audio-manager.git

**Does it come with any scripts or binaries?**
No, it's pure Python with system subprocess calls (wpctl, pw-link, etc.)

**Maintainer** : @yourusername

**License** : GNU General Public License v3.0 or later

**Is the app currently available on GitHub, GitLab, etc.?**
Yes: https://github.com/yourusername/linux-audio-manager
```

4. Soumettre l'issue

**Flathub créera alors** `https://github.com/flathub/io.github.linux-audio-manager`

### Étape 3 : Cloner le repo Flathub et pousser le manifest

**Une fois que Flathub a créé le repo** :

```bash
cd /tmp
git clone https://github.com/flathub/io.github.linux-audio-manager.git flathub-repo
cd flathub-repo

# Copier le manifest
cp /mnt/wwn*/1.*audio*/io.github.linux-audio-manager.yml .

# Tester que le YAML est valide (optionnel)
# flatpak manifest io.github.linux-audio-manager.yml

# Pousser
git add io.github.linux-audio-manager.yml
git commit -m "Add Flatpak manifest for v0.1.0"
git push origin main
```

### Étape 4 : Attendre la validation Flathub

- **Timeline** : 24-48h
- **Processus** :
  - Bot Flathub lance un build automatique
  - Reviewers testent l'app
  - Vous recevez commentaires (si besoin)
  - Une fois approuvé → app publiée sur Flathub

### Étape 5 : Application disponible

Une fois publiée :

**Installation par utilisateurs** :
```bash
flatpak install flathub io.github.linux-audio-manager
flatpak run io.github.linux-audio-manager
```

**Visible dans GNOME Software** (après ~2h de propagation CDN)

---

## 📁 Fichiers de soumission

Vérifier que tous ces fichiers existent et sont corrects :

```
.
├── LICENSE                                        ✅ GPL-3.0
├── pyproject.toml                                 ✅ Setup Python
├── README.md                                      ✅ Instructions
├── io.github.linux-audio-manager.yml              ✅ Manifest Flatpak
├── flathub.json                                   ✅ Config Flathub
├── GNOME_CONFORMITY_REPORT.md                     ✅ Audit conformité
├── FLATHUB_SUBMISSION_PLAN.md                     ✅ Plan détaillé
├── data/
│   ├── io.github.linux-audio-manager.desktop      ✅ Entrée système
│   └── io.github.linux-audio-manager.metainfo.xml ✅ AppStream
├── po/
│   ├── LINGUAS                                    ✅ Langues
│   ├── linux-audio-manager.pot                    ✅ Template trad
│   └── fr.po                                      ✅ Traductions FR
└── src/
    ├── __init__.py                                ✅ App ID correct
    ├── main.py                                    ✅ Point entrée
    ├── window.py                                  ✅ UI GTK4
    ├── audio.py                                   ✅ Backend PipeWire
    └── config.py                                  ✅ Persistance
```

---

## 🔍 Vérifications finales avant Étape 2

Lancer ceci pour valider une dernière fois :

```bash
./prepare-submission.sh
```

Assurez-vous que **TOUS les ✅** s'affichent.

---

## ⚠️ Points critiques

**NE PAS** :
- ❌ Modifier APP_ID (doit rester `io.github.linux-audio-manager`)
- ❌ Supprimer les fichiers .desktop ou .metainfo.xml
- ❌ Changer de licence
- ❌ Créer une issue sans que le repo GitHub soit PUBLIC

**VÉRIFIER** :
- ✅ GitHub repo est PUBLIC
- ✅ Tag v0.1.0 existe
- ✅ License visible sur GitHub
- ✅ README explique l'installation

---

## 📞 Support

Si Flathub refuse la soumission :

1. Vérifier les commentaires sur l'issue
2. Corriger le problème
3. Pousser correction vers GitHub
4. Flathub bot redéploie automatiquement

**Contacts** :
- Matrix : #flathub:matrix.org
- Issues : github.com/flathub/flathub
- Docs : docs.flathub.org

---

## ✅ Prochaine action

**Vous êtes prêt à soumettre!**

Allez à **Étape 1** ci-dessus pour commencer.

---

**Généré** : 25 mai 2026  
**Conforme** : GNOME + Flathub standards
