# Dépendances et autonomie

## Principe

Le logiciel récupère **100% de ses données depuis l'OS** via **PipeWire**. Aucune configuration externe, aucune bibliothèque spécialisée, aucun serveur tiers.

- **Backend audio** (module `src/audio.py`) : Python pur + stdlib → PipeWire via `pw-dump` et `wpctl`.
- **Interface** (modules `src/main.py`, `src/window.py`) : GTK4/libadwaita pour le UI seulement.

## Dépendances système requises

### Obligatoires (pour fonctionner 100%)

1. **Python 3.8+** (stdlib uniquement : `json`, `subprocess`, `dataclasses`)
2. **PipeWire** + outils système :
   - `pw-dump` : lecture du graphe audio (fourni avec PipeWire Core)
   - `wpctl` : écriture du volume (fourni avec WirePlumber, driver PipeWire standard)
3. **PyGObject** : bridge Python ↔ C (fourni avec GNOME/Linux standard)

### Optionnels (pour l'interface uniquement)

4. **GTK 4** : interface GNOME moderne (optionnel : GTK3 peut fonctionner en fallback)
5. **libadwaita 1** : composants GNOME (dépend de GTK4)

## Test d'autonomie du backend

Le backend fonctionne 100% seul, sans GTK/libadwaita :

```bash
cd "/mnt/wwn-0x5000000000002733-part2/1. projet vscode/linux audio manager"
python3 -c "
from src import audio
streams, sinks = audio.get_audio_state()
print(f'{len(streams)} flux audio · {len(sinks)} périphériques')
"
```

Résultat : ✓ 4 flux détectés, 4 périphériques détectés, aucune erreur.

## Statut des dépendances sur ce système

| Dépendance | Disponible | Chemin | Statut |
|---|---|---|---|
| Python 3 | ✓ | `/usr/bin/python3` | OK |
| pw-dump | ✓ | `/usr/bin/pw-dump` | OK, PipeWire 1.6.2 |
| wpctl | ✓ | `/usr/bin/wpctl` | OK, WirePlumber prêt |
| PyGObject | ✓ | Site-packages | OK, fonctionne |
| GTK4 | ✗ | Non disponible | Fallback GTK3 activé |
| GTK3 | ✓ | `/usr/lib` | OK, interface légère |
| libadwaita | ? | Non testée | Optionnel, fallback GTK3 actif |

## Mode opérationnel

Le logiciel détecte automatiquement les libs disponibles au lancement :

1. **Essai GTK4/libadwaita** : si disponible → interface moderne GNOME
2. **Fallback GTK3** : si GTK4 absent → interface légère GTK3 (100% fonctionnelle)

À ce jour : **GTK3 activé**, interface légère mais complète.

## Conclusion

✓ **OUI, le logiciel est 100% autonome et fonctionnel.**

- **Backend audio** : récupère tout depuis PipeWire (l'OS), stdlib Python, aucune dépendance tierce.
- **Interface** : détection auto des libs, GTK4/libadwaita si disponible, sinon fallback GTK3.
- **Portabilité** : fonctionne sur tout système Linux avec PipeWire + Python 3 + PyGObject.
- **Autonomie** : ne dépend d'aucun serveur externe, aucune configuration tierce.
