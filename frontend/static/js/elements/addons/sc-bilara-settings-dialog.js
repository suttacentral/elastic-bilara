import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/dialog/dialog.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/switch/switch.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/button/button.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/spinner/spinner.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/alert/alert.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/icon/icon.js';

import { registerIconLibrary } from 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/utilities/icon-library.js';

registerIconLibrary('bi', {
  resolver: name => `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/icons/${name}.svg`,
});

export class SCBilaraSettingsDialog extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    sl-dialog::part(panel) {
      max-width: 480px;
      width: 100%;
      border-radius: 12px;
      background-color: var(--color-background);
      border: 1px solid var(--color-border);
    }

    sl-dialog::part(header) {
      padding: 20px 24px 12px;
    }

    sl-dialog::part(title) {
      color: var(--color-text-emphasized);
    }

    sl-dialog::part(close-button) {
      color: var(--color-text-secondary);
    }

    sl-dialog::part(close-button):hover {
      color: var(--color-text-emphasized);
    }

    sl-dialog::part(body) {
      padding: 12px 24px 20px;
      color: var(--color-text);
    }

    sl-dialog::part(footer) {
      padding: 12px 24px 20px;
    }

    .dialog-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 1.125rem;
      font-weight: 600;
      color: var(--color-text-emphasized);
    }

    .dialog-title sl-icon {
      font-size: 1.25rem;
      color: var(--color-primary);
    }

    .settings-section {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .setting-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      background: var(--color-background-secondary);
      border-radius: 8px;
      border: 1px solid var(--color-border);
      transition: background-color 0.2s ease;
    }

    .setting-row:hover {
      background: var(--color-background-tertiary);
    }

    .setting-label {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .setting-label .title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--color-text-emphasized);
    }

    .setting-label .title sl-icon {
      font-size: 1rem;
      color: var(--color-primary);
    }

    .setting-label .description {
      font-size: 0.75rem;
      color: var(--color-text-secondary);
      margin-left: 22px;
    }

    .setting-control {
      flex-shrink: 0;
    }

    .loading-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 0;
      gap: 12px;
      color: var(--color-text-secondary);
    }

    .loading-container sl-spinner {
      font-size: 2rem;
      --track-width: 3px;
      --indicator-color: var(--color-primary);
      --track-color: var(--color-background-tertiary);
    }

    .footer-buttons {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      width: 100%;
    }

    sl-switch {
      --sl-color-primary-600: var(--color-primary);
      --sl-color-primary-500: var(--color-primary);
      --sl-color-neutral-300: var(--color-border);
      --sl-color-neutral-600: var(--color-text-secondary);
    }

    sl-button[variant="primary"]::part(base) {
      background-color: var(--color-primary);
      border-color: var(--color-primary);
      color: var(--color-text-on-strong);
    }

    sl-button[variant="primary"]::part(base):hover {
      opacity: 0.9;
    }

    sl-button[variant="default"]::part(base) {
      background-color: var(--color-background-secondary);
      border-color: var(--color-border);
      color: var(--color-text-emphasized);
    }

    sl-button[variant="default"]::part(base):hover {
      background-color: var(--color-background-tertiary);
      border-color: var(--color-border);
      color: var(--color-text-emphasized);
    }
  `;

  static properties = {
    open: { type: Boolean, reflect: true },
    _loading: { type: Boolean, state: true },
    _saving: { type: Boolean, state: true },
    _settings: { type: Object, state: true },
    _toast: { type: Object, state: true },
  };

  constructor() {
    super();
    this.open = false;
    this._loading = false;
    this._saving = false;
    this._settings = {
      pali_lookup: true,
      dblclick_search: true,
    };
    this._toast = { show: false, message: '', variant: 'primary' };
  }

  async show() {
    this.open = true;
    await this._loadSettings();
  }

  hide() {
    this.open = false;
  }

  async _loadSettings() {
    this._loading = true;
    try {
      const resp = await fetch('/api/v1/settings', { credentials: 'include' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this._settings = {
        pali_lookup: data.pali_lookup ?? true,
        dblclick_search: data.dblclick_search ?? true,
      };
    } catch (err) {
      console.error('Failed to load settings:', err);
      this._showToast('Failed to load settings', 'danger');
    } finally {
      this._loading = false;
    }
  }

  async _saveSettings() {
    this._saving = true;
    try {
      const resp = await fetch('/api/v1/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(this._settings),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this._showToast('Settings saved', 'success');
      this.dispatchEvent(new CustomEvent('settings-saved', {
        detail: { ...this._settings },
        bubbles: true,
        composed: true,
      }));
      setTimeout(() => this.hide(), 800);
    } catch (err) {
      console.error('Failed to save settings:', err);
      this._showToast('Failed to save settings', 'danger');
    } finally {
      this._saving = false;
    }
  }

  _showToast(message, variant = 'primary') {
    this._toast = { show: true, message, variant };
    setTimeout(() => {
      this._toast = { ...this._toast, show: false };
    }, 3000);
  }

  _onPaliLookupChange(e) {
    this._settings = { ...this._settings, pali_lookup: e.target.checked };
  }

  _onDblclickSearchChange(e) {
    this._settings = { ...this._settings, dblclick_search: e.target.checked };
  }

  _onDialogHide() {
    this.open = false;
    this.dispatchEvent(new CustomEvent('settings-closed', { bubbles: true, composed: true }));
  }

  render() {
    return html`
      <sl-dialog
        ?open=${this.open}
        @sl-after-hide=${this._onDialogHide}
        label="Settings"
      >
        <div slot="label">
          <span class="dialog-title">
            <sl-icon library="bi" name="gear"></sl-icon>
            Settings
          </span>
        </div>

        ${this._loading
          ? html`
            <div class="loading-container">
              <sl-spinner></sl-spinner>
              <span>Loading settings...</span>
            </div>
          `
          : html`
            <div class="settings-section">
              <div class="setting-row">
                <div class="setting-label">
                  <span class="title">
                    <sl-icon library="bi" name="book"></sl-icon>
                    Pali Lookup
                  </span>
                  <span class="description">Single-click text to activate Pali word lookup</span>
                </div>
                <div class="setting-control">
                  <sl-switch
                    ?checked=${this._settings.pali_lookup}
                    @sl-change=${this._onPaliLookupChange}
                  ></sl-switch>
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-label">
                  <span class="title">
                    <sl-icon library="bi" name="search"></sl-icon>
                    Double-click Search
                  </span>
                  <span class="description">Double-click text to search related content</span>
                </div>
                <div class="setting-control">
                  <sl-switch
                    ?checked=${this._settings.dblclick_search}
                    @sl-change=${this._onDblclickSearchChange}
                  ></sl-switch>
                </div>
              </div>
            </div>
          `}

        ${this._toast.show
          ? html`
            <sl-alert variant=${this._toast.variant} open duration="3000" closable>
              ${this._toast.message}
            </sl-alert>
          `
          : ''}

        <div slot="footer" class="footer-buttons">
          <sl-button
            variant="default"
            @click=${this.hide}
            ?disabled=${this._saving}
          >
            Cancel
          </sl-button>
          <sl-button
            variant="primary"
            @click=${this._saveSettings}
            ?loading=${this._saving}
            ?disabled=${this._loading}
          >
            Save Settings
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }
}

customElements.define('sc-bilara-settings-dialog', SCBilaraSettingsDialog);
