import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
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

    .notification-icon {
      height: 32px;
      width: 32px;
      vertical-align: middle;
      fill: var(--color-text);
      transition: border 0.3s ease;
      border: 2px solid transparent;
      border-radius: 50%;
    }

    .notification-icon:hover,
    .user-container:hover {
      border: 2px solid var(--color-primary);
      border-radius: 50%;
    }

    .notification-count {
      position: absolute;
      top: -2px;
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
  static SSE_RECONNECT_DELAY = 10000;

  constructor() {
    super();
    this.count = 0;
    this._pollIntervalId = null;
    this._eventSource = null;
    this._sseReconnectTimer = null;
    this._handleNotificationsUpdated = this._handleNotificationsUpdated.bind(this);
    this._handleUnreadCountEvent = this._handleUnreadCountEvent.bind(this);
    this._handleStreamError = this._handleStreamError.bind(this);
  }

  render() {
    return html`
      <div class="icon-wrapper" title="See changes by other users">
        <div>
          <a href="/notifications" target="_blank">
            <svg class="notification-icon" xmlns="http://www.w3.org/2000/svg" height="40px" viewBox="0 -960 960 960" width="40px">
              <path d="M160-200v-66.67h80v-296q0-83.66 49.67-149.5Q339.33-778 420-796v-24q0-25 17.5-42.5T480-880q25 0 42.5 17.5T540-820v24q80.67 18 130.33 83.83Q720-646.33 720-562.67v296h80V-200H160Zm320-301.33ZM480-80q-33 0-56.5-23.5T400-160h160q0 33-23.5 56.5T480-80ZM306.67-266.67h346.66v-296q0-72-50.66-122.66Q552-736 480-736t-122.67 50.67q-50.66 50.66-50.66 122.66v296Z"/>
            </svg>
          </a>
          ${this.count > 0
            ? html`<div class="notification-count"><sc-circle-badge variant="danger" pulse content="${this.count}"size="small"></sc-circle-badge></div>`
            : ''}
        </div>
      </div>
    `;
  }

  async fetchNotification() {
    try {
      const response = await fetch('/api/v1/notifications/feed');

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (!data.notifications) {
        throw new Error('Invalid data format from the API');
      }

      return data.notifications;
    } catch (error) {
      throw new Error(error);
    }
  }

  _handleUnreadCountEvent(event) {
    try {
      const payload = JSON.parse(event.data || '{}');
      if (typeof payload.unread_count === 'number') {
        this.count = payload.unread_count;
      }
    } catch (error) {
      console.error('Failed to parse unread_count event:', error);
    }
  }

  _clearSseReconnectTimer() {
    if (this._sseReconnectTimer) {
      clearTimeout(this._sseReconnectTimer);
      this._sseReconnectTimer = null;
    }
  }

  _startRealtimeStream() {
    this._stopRealtimeStream();

    this._eventSource = new EventSource('/api/v1/notifications/stream');
    this._eventSource.addEventListener(
      'unread_count',
      this._handleUnreadCountEvent
    );
    this._eventSource.addEventListener(
      'stream_error',
      this._handleStreamError
    );
    this._eventSource.onerror = this._handleStreamError;
  }

  _stopRealtimeStream() {
    this._clearSseReconnectTimer();

    if (this._eventSource) {
      this._eventSource.removeEventListener(
        'unread_count',
        this._handleUnreadCountEvent
      );
      this._eventSource.removeEventListener(
        'stream_error',
        this._handleStreamError
      );
      this._eventSource.close();
      this._eventSource = null;
    }
  }

  _handleStreamError() {
    this._stopRealtimeStream();
    this._clearSseReconnectTimer();

    this._sseReconnectTimer = setTimeout(() => {
      this._startRealtimeStream();
    }, SCBilaraNotificationIcon.SSE_RECONNECT_DELAY);
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

  _handleNotificationsUpdated() {
    this._updateNotificationCount();
  }

  connectedCallback() {
    super.connectedCallback();
    this._startPolling();
    this._startRealtimeStream();
    window.addEventListener(
      'notifications-updated',
      this._handleNotificationsUpdated
    );
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopPolling();
    this._stopRealtimeStream();
    window.removeEventListener(
      'notifications-updated',
      this._handleNotificationsUpdated
    );
  }

  firstUpdated() {
    this._updateNotificationCount();
  }
}

customElements.define('sc-bilara-notification-icon', SCBilaraNotificationIcon);