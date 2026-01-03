import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';
import '../addons/sc-bilara-circle-badge.js';

class SCBilaraNotificationIcon extends LitElement {
  static styles = css`
    .icon-wrapper {
      position: relative;
      display: inline-block;
    }

    .icon-wrapper img {
      height: 32px;
      vertical-align: middle;
    }

    .notification-count {
      position: absolute;
      top: -6px;
      right: -6px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: bold;
    }
  `;

  static properties = {
    count: { type: Number },
  };

  static POLL_INTERVAL = 30 * 60 * 1000;

  constructor() {
    super();
    this.count = 0;
    this._pollIntervalId = null;
  }

  render() {
    return html`
      <div class="icon-wrapper">
        <div>
          <a href="/notifications_panel" target="_blank"><img src="./static/img/notification.svg" alt="notification"/></a>
          ${this.count > 0
            ? html`<div class="notification-count"><sc-circle-badge variant="danger" pulse content="${this.count}"size="small"></sc-circle-badge></div>`
            : ''}
        </div>
      </div>
    `;
  }

  async fetchNotification() {
    try {
      const response = await fetch(`api/v1/notifications/git`);
      const data = await response.json();
      if (!data.git_recent_commits) {
          throw new Error("Invalid data format from the API");
      }
      return data.git_recent_commits;
    } catch (error) {
        throw new Error(error);
    }
  }

  async _updateNotificationCount() {
    try {
      const data = await this.fetchNotification();
      this.count = data.length;
    } catch (error) {
      console.error('Failed to update notification count:', error);
    }
  }

  _startPolling() {
    this._stopPolling();
    this._pollIntervalId = setInterval(
      () => this._updateNotificationCount(),
      SCBilaraNotificationIcon.POLL_INTERVAL
    );
  }

  _stopPolling() {
    if (this._pollIntervalId) {
      clearInterval(this._pollIntervalId);
      this._pollIntervalId = null;
    }
  }

  connectedCallback() {
    super.connectedCallback();
    this._startPolling();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopPolling();
  }

  firstUpdated() {
    this._updateNotificationCount();
  }
}

customElements.define('sc-bilara-notification-icon', SCBilaraNotificationIcon);