// extension.js — AudioHub GNOME Shell extension
// Barre d'etat pour acces rapide a l'application.

import St from 'gi://St';
import GLib from 'gi://GLib';

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const APP_BIN = 'audio-hub';
const APP_NAME = 'AudioHub';

export default class AudioHubExtension extends Extension {
    enable() {
        this._button = new AudioHubButton();
        Main.panel.addToStatusArea('audio-hub', this._button);
    }

    disable() {
        this._button?.destroy();
        this._button = null;
    }
}

class AudioHubButton extends PanelMenu.Button {
    constructor() {
        super(0.5, APP_NAME, false);

        const icon = new St.Icon({
            icon_name: 'multimedia-volume-control-symbolic',
            style_class: 'system-status-icon',
        });

        this.add_child(icon);
        this._addMenuItems();
        this.connect('button-press-event', () => this._onClicked());
    }

    _addMenuItems() {
        const openItem = new PopupMenu.PopupMenuItem(`Ouvrir ${APP_NAME}`);
        openItem.connect('activate', () => {
            GLib.spawn_command_line_async(APP_BIN);
        });
        this.menu.addMenuItem(openItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const statusItem = new PopupMenu.PopupMenuItem('Etat audio');
        statusItem.connect('activate', () => {
            GLib.spawn_command_line_async('bash -c "wpctl status | zenity --text-info --title=\\\"Etat audio\\\""');
        });
        this.menu.addMenuItem(statusItem);
    }

    _onClicked() {
        if (this.menu.isOpen) {
            this.menu.toggle();
        }
    }

    destroy() {
        super.destroy();
    }
}
