import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

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
      <div class="project-header">
          <p class="project-header__message"></p>
          <nav class="project-header__nav">
              <ul class="project-header__nav-list">
                  <li class="project-header__nav-item">
                      <button class="project-header__nav-button btn btn--related-projects"
                              @click="$dispatch('toggle-detail-panel', {panel: 'related'}); adjustVisibleTextareas()">
                          Related
                      </button>
                  </li>
                  <li class="project-header__nav-item">
                      <button class="project-header__nav-button btn btn--search"
                              @click="$dispatch('toggle-detail-panel', {panel: 'search'}); adjustVisibleTextareas()">
                          Search
                      </button>
                  </li>
              </ul>
          </nav>
      </div>
    `;
  }
}
customElements.define('sc-bilara-translation-project-header', SCBilaraTranslationProjectHeader);
