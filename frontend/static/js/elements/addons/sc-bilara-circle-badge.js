import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.1/+esm';

/**
 * Circular badge components
 *
 * @element sc-circle-badge
 *
 * @prop {String} variant - Badge Variations: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
 * @prop {String} size - Badge size: 'small' | 'medium' | 'large'
 * @prop {String} content - Badge content(text or number)
 * @prop {Number} max - Maximum value of the number, if exceeded, will be displayed as {max}+
 * @prop {Boolean} pulse - Should pulse animation be displayed
 * @prop {Boolean} dot - Whether to display as a dot (no content)
 *
 * @slot - Default slot, can contain icons or other content
 *
 * @example
 * <sc-circle-badge variant="danger" content="5"></sc-circle-badge>
 * <sc-circle-badge variant="success" dot pulse></sc-circle-badge>
 * <sc-circle-badge variant="primary" size="large">
 *   <i class="bi-bell"></i>
 * </sc-circle-badge>
 */
export class SCCircleBadge extends LitElement {
    static styles = css`
        :host {
            display: inline-block;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            font-weight: 600;
            font-family: sans-serif;
            line-height: 1;
            box-sizing: border-box;
            position: relative;
            overflow: visible;
        }

        /* Size */
        .badge--small {
            width: 20px;
            height: 20px;
            font-size: 10px;
        }

        .badge--medium {
            width: 28px;
            height: 28px;
            font-size: 12px;
        }

        .badge--large {
            width: 36px;
            height: 36px;
            font-size: 14px;
        }

        /* Dot Mode */
        .badge--dot {
            width: 10px;
            height: 10px;
            padding: 0;
        }

        .badge--dot.badge--small {
            width: 8px;
            height: 8px;
        }

        .badge--dot.badge--large {
            width: 12px;
            height: 12px;
        }

        /* Color */
        .badge--primary {
            background-color: #0d6efd;
            color: white;
        }

        .badge--success {
            background-color: #198754;
            color: white;
        }

        .badge--warning {
            background-color: #ffc107;
            color: #000;
        }

        .badge--danger {
            background-color: #dc3545;
            color: white;
        }

        .badge--info {
            background-color: #0dcaf0;
            color: #000;
        }

        .badge--neutral {
            background-color: #6c757d;
            color: white;
        }

        .badge--pending {
            background-color: #fd7e14;
            color: white;
        }

        /* Pulse Animation */
        .badge--pulse::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background-color: inherit;
            opacity: 0.6;
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        @keyframes pulse {
            0%, 100% {
                transform: scale(1);
                opacity: 0.6;
            }
            50% {
                transform: scale(1.3);
                opacity: 0;
            }
        }

        .badge__content {
            position: relative;
            z-index: 1;
        }

        /* Slot Styles */
        ::slotted(*) {
            display: flex;
            align-items: center;
            justify-content: center;
        }
    `;

    static properties = {
        variant: { type: String, reflect: true },
        size: { type: String, reflect: true },
        content: { type: String },
        max: { type: Number },
        pulse: { type: Boolean, reflect: true },
        dot: { type: Boolean, reflect: true }
    };

    constructor() {
        super();
        this.variant = 'primary';
        this.size = 'medium';
        this.content = '';
        this.max = 99;
        this.pulse = false;
        this.dot = false;
    }

    render() {
        const classes = {
            badge: true,
            [`badge--${this.variant}`]: true,
            [`badge--${this.size}`]: true,
            'badge--pulse': this.pulse,
            'badge--dot': this.dot
        };

        const className = Object.entries(classes)
            .filter(([_, value]) => value)
            .map(([key]) => key)
            .join(' ');

        return html`
            <div class="${className}" part="base">
                ${this.dot ? html`` : this.renderContent()}
            </div>
        `;
    }

    renderContent() {
        // If there is slot content, display it with priority
        if (this.hasSlotContent()) {
            return html`<slot></slot>`;
        }

        // If there is text content
        if (this.content) {
            const displayContent = this.formatContent(this.content);
            return html`<span class="badge__content" part="content">${displayContent}</span>`;
        }

        return html``;
    }

    formatContent(content) {
        // If the content is a number and exceeds the maximum value, display as max+
        const numValue = parseInt(content, 10);
        if (!isNaN(numValue) && numValue > this.max) {
            return `${this.max}+`;
        }
        return content;
    }

    hasSlotContent() {
        const slot = this.shadowRoot?.querySelector('slot');
        if (!slot) return false;
        const nodes = slot.assignedNodes({ flatten: true });
        return nodes.length > 0;
    }

    updated(changedProperties) {
        if (changedProperties.has('variant') ||
            changedProperties.has('size') ||
            changedProperties.has('pulse') ||
            changedProperties.has('dot')) {
            this.requestUpdate();
        }
    }
}

customElements.define('sc-circle-badge', SCCircleBadge);