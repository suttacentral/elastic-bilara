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
        actions: { type: Array, state: true }
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
            bottom: var(--space-lg);
            right: var(--space-lg);
            display: flex;
            align-items: flex-start;
            gap: var(--space-sm);
            padding: var(--space-md) var(--space-lg);
            background-color: var(--color-black);
            color: var(--color-text-on-strong);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            animation: toastIn 0.3s ease;
            font-family: inherit;
            font-size: var(--text-sm);
            max-width: min(90vw, 500px);
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
            color: var(--color-white, #FBF6EF);
            text-decoration: underline;
            text-underline-offset: 2px;
            font-weight: 600;
            margin-left: var(--space-xs, 0.25rem);
        }

        .toast a:hover {
            opacity: 0.85;
        }

        .toast i {
            font-size: var(--text-lg);
            flex-shrink: 0;
            margin-top: 2px;
        }

        .toast span {
            flex: 1;
            word-break: break-word;
            white-space: pre-wrap;
            max-height: 80vh;
            overflow-y: auto;
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
    `;

    constructor() {
        super();
        this.visible = false;
        this.message = '';
        this.type = 'success';
        this.actions = [];
        this._timeoutId = null;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of toast: 'success' or 'error'
     * @param {number} duration - Duration in milliseconds (default: 3000)
     * @param {Array<{label: string, href: string}>} actions - Safe link actions
     */
    show(message, type = 'success', duration = 3000, actions = []) {
        if (this._timeoutId) {
            clearTimeout(this._timeoutId);
        }

        this.message = message;
        this.type = type;
        this.actions = actions;
        this.visible = true;

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
                <i class="${iconClass}"></i>
                <span>
                    ${this.message}
                    ${this.actions.map(action => html`
                        <a href="${action.href}" target="_blank" rel="noopener noreferrer">
                            ${action.label}
                        </a>
                    `)}
                </span>
            </div>
        `;
    }
}

customElements.define('sc-bilara-toast', ScBilaraToast);
