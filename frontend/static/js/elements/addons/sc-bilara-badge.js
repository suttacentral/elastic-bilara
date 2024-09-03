import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

export class SCBilaraBadge extends LitElement {
  static styles = css`
    .badge {
      padding: 0.1em 0.2em;
      border-radius: 0.6rem;
      color: #ffffff;
      font-family: sans-serif;
      font-size: 0.7em;
      font-weight: bold;
    }

    .badge-translation {
      background-color: #007bff;
    }

    .badge-secondary {
      background-color: #6c757d;
    }

    .badge-root {
      background-color: #28a745;
    }

    .badge-danger {
      background-color: #dc3545;
    }

    .badge-comment {
      background-color: #ffc107;
    }

    .badge-html {
      background-color: #17a2b8;
    }

    .badge-variant {
      background-color: #f0a1a8;
    }

    .badge-reference {
      background-color: #343a40;
    }
  `;

  static properties = {
    text: { type: String },
    color: { type: String }
  };

  constructor() {
    super();
    this.text = '';
    this.color = '';
  }

  render() {
    return html`
      <span class="badge ${this.color}"><slot>${this.text}</slot></span>
    `;
  }
}

customElements.define('sc-bilara-badge', SCBilaraBadge);