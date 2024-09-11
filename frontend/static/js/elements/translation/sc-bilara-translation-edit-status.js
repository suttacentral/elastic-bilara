import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/badge/badge.js';

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

    render() {
        return html`
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/themes/light.css" />
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
            ${this.badgeTemplate()}
        `;
    }

    badgeTemplate() {
        return {
            error: html`<sl-badge variant="danger" pill><i class="bi-x"></i></sl-badge>`,
            modified: html`<sl-badge variant="success" pill><i class="bi-exclamation-triangle"></i></sl-badge>`,
            pending: html`<sl-badge variant="neutral" pill><i class="bi-check2"></i></sl-badge>`,
            committed: html`<sl-badge variant="success" pill><i class="bi-check2"></i></sl-badge>`,
        }[this.status] || html``;
    }

    updated(changedProps) {
        if (changedProps.has('status')) {
            this.requestUpdate();
        }
    }
}
customElements.define('sc-bilara-translation-edit-status', SCBilaraTranslationEditStatus);
