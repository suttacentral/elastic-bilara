import { LitElement, html, css, nothing } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

/**
 * Toast notification component
 *
 * Usage:
 * <sc-toast-notification></sc-toast-notification>
 *
 * Methods:
 * - show(message, type = 'success', duration = 3000, actions = [])
 *
 * Example:
 * const toast = document.querySelector('sc-toast-notification');
 * toast.show('Operation successful!', 'success');
 * toast.show('An error occurred', 'error');
 */
export class ScBilaraToast extends LitElement {
    static properties = {
        visible: { type: Boolean, state: true },
        message: { type: String, state: true },
        type: { type: String, state: true },
        actions: { type: Array, state: true },
        dismissible: { type: Boolean, state: true }
    };

    static styles = css`
        :host {
            --color-success: #859900;
            --color-warning: #b58900;
            --color-error: #dc322f;
            --color-black: #2C2B2B;
            --color-white: #FBF6EF;
            --space-sm: 0.5rem;
            --space-md: 1rem;
            --space-lg: 1.5rem;
            --radius-md: 8px;
            --shadow-lg: 0 4px 8px rgba(0, 0, 0, 0.15);
        }

        .toast {
            position: fixed;
            right: 1rem;
            bottom: 1rem;
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) auto;
            align-items: start;
            column-gap: 0.75rem;
            width: fit-content;
            min-width: min(18rem, calc(100vw - 2rem));
            max-width: min(28rem, calc(100vw - 2rem));
            max-height: min(80dvh, 36rem);
            padding: 0.875rem 1rem;
            overflow: hidden;
            box-sizing: border-box;
            background-color: var(--color-black);
            color: var(--color-text-on-strong);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            animation: toastIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: inherit;
            font-size: var(--text-sm);
        }

        .toast.success {
            background-color: var(--color-success);
        }

        .toast.warning {
            background-color: var(--color-warning);
        }

        .toast.error {
            background-color: var(--color-error);
        }

        .toast.hidden {
            display: none;
        }

        .toast a {
            display: inline-flex;
            align-items: center;
            min-height: 1.75rem;
            padding: 0.2rem 0.5rem;
            color: var(--color-white, #FBF6EF);
            border: 1px solid rgba(255, 255, 255, 0.45);
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.08);
            text-decoration: none;
            font-weight: 600;
            line-height: 1.2;
        }

        .toast a:hover {
            background: rgba(255, 255, 255, 0.18);
        }

        .toast a:focus-visible {
            outline: 2px solid currentColor;
            outline-offset: 2px;
        }

        .toast i {
            display: grid;
            place-items: center;
            width: 1.5rem;
            height: 1.5rem;
            font-size: 1.35rem;
            line-height: 1;
            flex-shrink: 0;
        }

        .toast-content {
            display: flex;
            min-width: 0;
            max-height: calc(80dvh - 1.75rem);
            overflow-y: auto;
            flex-direction: column;
            gap: 0.5rem;
        }

        .toast-message {
            line-height: 1.4;
            word-break: break-word;
            white-space: pre-wrap;
        }

        .toast-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.375rem 0.5rem;
        }

        .toast-actions[hidden] {
            display: none;
        }

        .close-button {
            display: grid;
            place-items: center;
            width: 1.75rem;
            height: 1.75rem;
            margin: -0.375rem -0.5rem 0 0;
            padding: 0;
            border: 0;
            border-radius: 50%;
            background: transparent;
            color: inherit;
            font: inherit;
            font-size: 1.25rem;
            line-height: 1;
            cursor: pointer;
        }

        .close-button[hidden] {
            display: none;
        }

        .close-button:hover {
            background: rgba(255, 255, 255, 0.16);
        }

        .close-button:focus-visible {
            outline: 2px solid currentColor;
            outline-offset: 1px;
        }

        @keyframes toastIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .toast {
                animation: none;
            }
        }
    `;

    constructor() {
        super();
        this.visible = false;
        this.message = '';
        this.type = 'success';
        this.actions = [];
        this.dismissible = false;
        this._timeoutId = null;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of toast: 'success' or 'error'
     * @param {number} duration - Duration in milliseconds; 0 persists until dismissed
     * @param {Array<{label: string, href: string}>} actions - Safe link actions
     */
    show(message, type = 'success', duration = 3000, actions = []) {
        if (this._timeoutId) {
            clearTimeout(this._timeoutId);
            this._timeoutId = null;
        }

        this.message = message;
        this.type = type;
        this.actions = actions;
        this.dismissible = duration === 0;
        this.visible = true;

        if (this.dismissible) {
            return;
        }

        this._timeoutId = setTimeout(() => {
            this.hide();
        }, duration);
    }

    hide() {
        this.visible = false;
        if (this._timeoutId) {
            clearTimeout(this._timeoutId);
            this._timeoutId = null;
        }
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        if (this._timeoutId) {
            clearTimeout(this._timeoutId);
        }
    }

    render() {
        const iconClass = {
            success: 'bi-check-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            error: 'bi-x-circle-fill',
        }[this.type] || 'bi-info-circle-fill';

        return html`
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css">
            <div
                class="toast ${this.type} ${this.visible ? '' : 'hidden'}"
                aria-live="polite"
                role="${this.visible ? 'status' : nothing}"
            >
                <i class="${iconClass}" aria-hidden="true"></i>
                <div class="toast-content">
                    <span class="toast-message">${this.message}</span>
                    <div
                        class="toast-actions"
                        ?hidden=${this.actions.length === 0}
                    >
                    ${this.actions.map(action => html`
                        <a href="${action.href}" target="_blank" rel="noopener noreferrer">
                            ${action.label}
                        </a>
                    `)}
                    </div>
                </div>
                <button
                    class="close-button"
                    type="button"
                    aria-label="Close notification"
                    title="Close"
                    ?hidden=${!this.dismissible}
                    @click=${this.hide}
                >&times;</button>
            </div>
        `;
    }
}

customElements.define('sc-bilara-toast', ScBilaraToast);
