import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/button/button.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/dropdown/dropdown.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/menu/menu.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/menu-item/menu-item.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/divider/divider.js';
import '../notification/sc-bilara-notification-icon.js';
import '../addons/sc-bilara-settings-dialog.js';

export class SCBilaraNavMain extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }

      nav {
        border-bottom: 1px solid var(--color-border);
        box-shadow: var(--shadow-sm);
        background-color: var(--color-background-tertiary);
      }
    `
  ];

  createRenderRoot() {
    return this;
  }

  _openSettings() {
    const dialog = this.querySelector('sc-bilara-settings-dialog');
    if (dialog) {
      dialog.show();
    }
  }

  render() {
    return html`
      <nav>
        <ul class="main-nav">
              <li class="main-nav__item go-home">
                  <a href="/nav" class="main-nav__item-link">Bilara</a>
              </li>
              <div class="image-container main-nav__item--right">
                <sc-bilara-notification-icon></sc-bilara-notification-icon>
              </div>

              <li class="main-nav__item hide-mobile">
                <sl-dropdown distance="8" x-cloak x-show="!!username">
                  <div slot="trigger" class="user-container" style="cursor: pointer;">
                      <img
                        :src="avatarURL"
                        x-bind:alt="username + 's github profile picture'"
                        class="user-avatar"
                        title="profile picture"/>
                  </div>
                  <sl-menu>
                    <sl-menu-item>
                      <a :href="'https://github.com/' + username" target="_blank" rel="noopener noreferrer" class="menu-item-link">
                        GitHub Profile
                      </a>
                    </sl-menu-item>
                    <sl-divider></sl-divider>
                    <sl-menu-item x-show="isActive">
                      <a href="/git_status_panel" target="_blank" rel="noopener noreferrer"  class="menu-item-link">
                        Unpublished Changes
                      </a>
                    </sl-menu-item>
                    <sl-menu-item>
                      <a href="/admin" target="_blank" rel="noopener noreferrer" class="menu-item-link">Admin</a>
                    </sl-menu-item>
                    <sl-menu-item x-show="isAdmin && isActive">
                      <a href="/tags" target="_blank" rel="noopener noreferrer" class="menu-item-link">Tags</a>
                    </sl-menu-item>
                    <sl-menu-item>
                      <a href="/dictionary" target="_blank" rel="noopener noreferrer" class="menu-item-link">Lexicon</a>
                    </sl-menu-item>
                    <sl-menu-item @click=${this._openSettings}>
                      <span class="menu-item-link">Settings</span>
                    </sl-menu-item>
                    <sl-menu-item @click.prevent="await logout()">
                      Logout
                    </sl-menu-item>
                  </sl-menu>
                </sl-dropdown>
              </li>
          </ul>
      </nav>
      <sc-bilara-settings-dialog></sc-bilara-settings-dialog>
    `;
  }
}

customElements.define('sc-bilara-nav-main', SCBilaraNavMain);
