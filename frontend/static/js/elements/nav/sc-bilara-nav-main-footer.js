import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

export class SCBilaraNavMainFooter extends LitElement {
  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <footer class="main-footer">
        <p class="main-footer__description">Computer Assisted Translation for SuttaCentral</p>
        <ul class="main-footer__list">
            <li class="main-footer__list-item">
                <a href="https://suttacentral.net/" class="main-footer__list-item-link">SuttaCentral</a>
            </li>
            <li class="main-footer__list-item">
                <a href="https://github.com/suttacentral/bilara" class="main-footer__list-item-link">Github</a>
            </li>
            <li class="main-footer__list-item">
                <a href="https://discourse.suttacentral.net/" class="main-footer__list-item-link">Forum</a>
            </li>
        </ul>
      </footer>
    `;
  }
}
customElements.define('sc-bilara-nav-main-footer', SCBilaraNavMainFooter);
