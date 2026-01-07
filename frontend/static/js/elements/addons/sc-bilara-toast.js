import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

/**
 * Toast notification component
 *
 * Usage:
 * <sc-toast-notification></sc-toast-notification>
 *
 * Methods:
 * - show(message, type = 'success', duration = 3000)
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
        type: { type: String, state: true }
    };

    static styles = css`
        :host {
            --color-success: #859900;
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
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-md) var(--space-lg);
            background: var(--color-black);
            color: var(--color-white);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            animation: toastIn 0.3s ease;
            font-family: inherit;
            font-size: var(--text-sm);
            max-width: 400px;
        }

        .toast.success {
            background: var(--color-success);
        }

        .toast.error {
            background: var(--color-error);
        }

        .toast.hidden {
            display: none;
        }

        .toast i {
            font-size: var(--text-lg);
            flex-shrink: 0;
        }

        .toast span {
            flex: 1;
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
        this._timeoutId = null;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of toast: 'success' or 'error'
     * @param {number} duration - Duration in milliseconds (default: 3000)
     */
    show(message, type = 'success', duration = 3000) {
        if (this._timeoutId) {
            clearTimeout(this._timeoutId);
        }

        this.message = message;
        this.type = type;
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
        if (!this.visible) {
            return html``;
        }

        const iconClass = this.type === 'success'
            ? 'bi-check-circle-fill'
            : 'bi-x-circle-fill';

        return html`
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css">
            <div class="toast ${this.type}">
                <i class="${iconClass}"></i>
                <span>${this.message}</span>
            </div>
        `;
    }
}

customElements.define('sc-bilara-toast', ScBilaraToast);
