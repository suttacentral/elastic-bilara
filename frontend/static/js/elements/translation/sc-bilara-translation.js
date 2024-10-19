import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';
import { unsafeHTML } from 'https://cdn.jsdelivr.net/npm/lit-html@3.2.0/directives/unsafe-html.js';

export class SCBilaraTranslation extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }
    `
  ];

  static properties = {
    translationsCount: { type: String },
    panels: { state: true },
  };

  constructor() {
    super();
    this.translationsCount = '';
    this.panels = 0;
  }

  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      ${this.renderPanels(this.panels)}
    `;
  }

  renderPanels(count, current = 2) {
    if (current > count) {
      return html``;
    }

    return html`
      <sl-split-panel>
        <i class="bi-grip-vertical" slot="divider"></i>
        <div slot="start" class="content-detail">
        </div>
        <div slot="end"  class="content-detail">
          ${this.renderPanels(count, current + 1)}
        </div>
      </sl-split-panel>
    `;
  }

  firstUpdated() {
    if (this.panels % 2!== 0) {
      const lastContentDetail = document.querySelector('.content-detail:last-child');
      lastContentDetail.style.display = 'none';
    }
  }

  _removeSplitPanels() {
    const splitPanels = Array.from(document.querySelectorAll('sl-split-panel'));
    splitPanels.forEach(splitPanel => {
      splitPanel.remove();
    });
  }

  _calculatePositions(totalWidth, numSplits) {
    const positions = [];
    for (let i = numSplits; i > 0; i--) {
      const position = 100 / i;
      positions.push(position);
    }
    return positions;
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    if (changedProperties.has('translationsCount')) {
      this.panels = parseInt(this.translationsCount);
      const positions = this._calculatePositions(100, this.panels);
      const contentDetails = Array.from(document.querySelectorAll('.project-container__content-details'));
      this.contentDetails = contentDetails;

      if (this.panels > 0) {
        const splitPanels = Array.from(document.querySelectorAll('sl-split-panel'));
        splitPanels.forEach((div, i) => {
          div.position = `${positions[i]}`;
        });
      }

      setTimeout(() => {
        const contentDetails = Array.from(document.querySelectorAll('.project-container__content-details'));
        const splitPanelContentDetails = Array.from(document.querySelectorAll('.content-detail'));
        let j = 0;
        splitPanelContentDetails.forEach((div, i) => {
          if (contentDetails[j] && !div.querySelector('sl-split-panel')) {
              div.appendChild(contentDetails[j]);
              j++;
          }
        });
      }, 100);
    }
  }
}

customElements.define('sc-bilara-translation', SCBilaraTranslation);
