# Plan de soumission Flathub - Linux Audio Manager

## 📋 Vue d'ensemble

Ce document décrit les étapes pour soumettre Linux Audio Manager à Flathub (https://flathub.org/).

---

## 🎯 Étapes de préparation et soumission

### **PHASE 1 : Préparation du repository GitHub**

#### Étape 1.1 : Créer un fork officiel sur GitHub
- [ ] Créer/vérifier compte GitHub (https://github.com)
- [ ] Fork ou créer repo `linux-audio-manager` public
- [ ] URL : `https://github.com/yourusername/linux-audio-manager`
- [ ] Vérifier : description, topics (audio, pipewire, gnome)

#### Étape 1.2 : Configurer les fichiers de soumission
- [ ] ✅ LICENSE (GPL-3.0-or-later) — DONE
- [ ] ✅ pyproject.toml — DONE
- [ ] ✅ data/*.desktop — DONE
- [ ] ✅ data/*.metainfo.xml — DONE
- [ ] ✅ README.md avec instructions build — À compléter
- [ ] Ajouter GNOME_CONFORMITY_REPORT.md — À générer

#### Étape 1.3 : Tagger une release stable
- [ ] Créer tag `v0.1.0` : `git tag -a v0.1.0 -m "Initial release"`
- [ ] Push : `git push origin v0.1.0`
- [ ] Créer GitHub Release avec notes

---

### **PHASE 2 : Préparation du manifest Flatpak**

#### Étape 2.1 : Valider le manifest
- [ ] ✅ `io.github.linux-audio-manager.yml` créé
- [ ] Tester localement : `flatpak run --development io.github.linux-audio-manager`
- [ ] Vérifier : permissions PipeWire, D-Bus OK

#### Étape 2.2 : Tester permissions D-Bus
- [ ] `dbus-send --session --print-reply /org/PipeWire/Core0` (santé PipeWire)
- [ ] Vérifier accès : `/org/freedesktop/DBus/Properties` (métadonnées)

#### Étape 2.3 : Tester le build complet
- [ ] `flatpak run --command=bash io.github.linux-audio-manager` — shell test
- [ ] `flatpak run io.github.linux-audio-manager` — app launch test

---

### **PHASE 3 : Création du repository Flathub**

#### Étape 3.1 : Préparer la soumission
- [ ] Créer issue sur https://github.com/flathub/flathub/issues/new
- [ ] Template : "New application" 
- [ ] Remplir :
  - App name: `Linux Audio Manager`
  - App ID: `io.github.linux-audio-manager`
  - Repository URL: `https://github.com/yourusername/linux-audio-manager`
  - Maintainer: `@yourusername`

#### Étape 3.2 : Flathub crée le repo
- [ ] Flathub maintainers créent `flathub/io.github.linux-audio-manager`
- [ ] Vous recevez accès collaborateur

#### Étape 3.3 : Pusher le manifest
```bash
cd /tmp
git clone https://github.com/flathub/io.github.linux-audio-manager.git
cp manifest.yml io.github.linux-audio-manager/
cd io.github.linux-audio-manager
git add manifest.yml
git commit -m "Initial manifest for v0.1.0"
git push origin main
```

---

### **PHASE 4 : Tests et validation Flathub**

#### Étape 4.1 : Flathub bot teste
- [ ] Bot lance build automatique
- [ ] Vérifier : ✅ Logs build (0 erreurs)
- [ ] Attendre validation (~24h)

#### Étape 4.2 : Révision manuelle
- [ ] Flathub reviewers testent l'app
- [ ] Vous répondez aux commentaires

#### Étape 4.3 : Approbation finale
- [ ] App approuvée
- [ ] Publiée sur https://flathub.org/apps/io.github.linux-audio-manager

---

### **PHASE 5 : Publication et maintenance**

#### Étape 5.1 : Distribution
- [ ] App visible dans GNOME Software
- [ ] Installation : `flatpak install flathub io.github.linux-audio-manager`

#### Étape 5.2 : Mises à jour futures
- [ ] Tagger v0.2.0 sur GitHub
- [ ] Pusher manifest.yml mis à jour vers Flathub
- [ ] Bot redéploie automatiquement

---

## 📊 Checklist de conformité

### Code & Métadonnées
- [x] LICENSE présent (GPL-3.0+)
- [x] pyproject.toml bien formé
- [x] APP_ID = `io.github.linux-audio-manager`
- [x] .desktop file présent
- [x] .metainfo.xml (AppStream) présent
- [x] Traductions i18n setup (po/LINGUAS)

### Manifest Flatpak
- [x] Manifest valide YAML
- [x] Permissions PipeWire + D-Bus déclarées
- [x] Finish args cohérents
- [x] Modules corrects

### Sécurité
- [x] Pas de binaire hardcodé
- [x] Subprocess `wpctl`, `pw-*` OK (outils système)
- [x] D-Bus access limité au nécessaire
- [x] Pas de telemetry

### Fonctionnalité
- [x] App se lance
- [x] Interface GTK4 + libadwaita OK
- [x] Shutdown propre (signal handler)
- [x] Pas d'erreurs de compilations

---

## 🚀 Timeline estimée

| Phase | Durée | Notes |
|-------|-------|-------|
| Préparation repo GitHub | 1h | Setup URL, tagger release |
| Tests locaux | 1h | Build Flatpak, vérifier perms |
| Soumission Flathub | 15 min | Créer issue, attendre repo |
| Review Flathub | 24-48h | Bot build + reviewers |
| **Total** | **2-3 jours** | Si première soumission |

---

## 📝 Commandes rapides

```bash
# Builder localement
flatpak-builder --force-clean build-dir io.github.linux-audio-manager.yml

# Tester l'app
flatpak run io.github.linux-audio-manager

# Vérifier permissions
flatpak info --show-metadata io.github.linux-audio-manager

# Créer archive pour Flathub
git clone https://github.com/yourusername/linux-audio-manager.git /tmp/app-src
cd /tmp/app-src && git tag -a v0.1.0 -m "v0.1.0" && git push origin v0.1.0
```

---

## 🔗 Ressources

- [Flathub Submit Guide](https://docs.flathub.org/docs/for-app-authors/submission)
- [Flatpak Manifest Reference](https://docs.flatpak.org/en/latest/manifests.html)
- [GNOME App Guidelines](https://developer.gnome.org/hig/)
- [AppStream Spec](https://www.freedesktop.org/wiki/Distributions/AppStream/)

---

## ⚠️ Points critiques à vérifier AVANT soumission

1. **Manifest YAML valide** → `flatpak manifest --help` ou online validator
2. **PipeWire access** → Permissions D-Bus correctes
3. **Nettoyage shutdown** → Signal handler fonctionne
4. **Métadonnées complètes** → description, version, licence, URL
5. **Pas de dépendances externes** → stdlib Python OK, pas de system-wide libs requises

---

## 📬 Contact Flathub

- Issues: https://github.com/flathub/flathub/issues
- Matrix: #flathub:matrix.org
- Docs: https://docs.flathub.org
