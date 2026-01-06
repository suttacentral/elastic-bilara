import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';

export class SCBilaraTranslationProjectHeader extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }
    `
  ];

  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <style>
          .project-header__message {
              font-size: 3rem;
              font-weight: 600;
              padding-left: 15px;
          }
      </style>
      <div class="project-header" x-data="{prefix: new URLSearchParams(window.location.search).get('prefix')}">
          <p class="project-header__message" x-text="prefix"></p>
          <nav class="project-header__nav">
              <ul class="project-header__nav-list">
                  <li class="project-header__nav-item">
                      <sl-button size="small" variant="warning" outline @click="$dispatch('toggle-detail-panel', {panel: 'related'});">Related</sl-button>
                  </li>
                  <li class="project-header__nav-item">
                      <sl-button size="small" variant="primary" outline @click="$dispatch('toggle-detail-panel', {panel: 'search'});">Search</sl-button>
                  </li>
              </ul>
          </nav>
      </div>
    `;
  }
}

customElements.define('sc-bilara-translation-project-header', SCBilaraTranslationProjectHeader);
