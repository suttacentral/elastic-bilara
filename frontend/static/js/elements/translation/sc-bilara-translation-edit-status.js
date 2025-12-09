import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';
import '../addons/sc-bilara-circle-badge.js';

export class SCBilaraTranslationEditStatus extends LitElement {
    static styles = [
        css`
            :host {
                display: block;
            }
        `
    ];

    static get properties() {
        return {
            status: { type: String },
        };
    }

    constructor() {
        super();
        this.status = "";
    }

    createRenderRoot() {
        return this;
    }

    render() {
        return html`
            ${this.badgeTemplate()}
        `;
    }

    badgeTemplate() {
        return {
            error: html`<sc-circle-badge variant="danger" content="×" size="small"></sc-circle-badge>`,
            modified: html`<sc-circle-badge variant="success" size="small"><i class="bi-exclamation-triangle"></i></sc-circle-badge>`,
            pending: html`<sc-circle-badge variant="neutral" size="small"><i class="bi-check2"></i></sc-circle-badge>`,
            committed: html`<sc-circle-badge variant="success" content="✓" size="small"></sc-circle-badge>`,
        }[this.status] || html``;
    }

    updated(changedProps) {
        if (changedProps.has('status')) {
            this.requestUpdate();
        }
    }
}
customElements.define('sc-bilara-translation-edit-status', SCBilaraTranslationEditStatus);
