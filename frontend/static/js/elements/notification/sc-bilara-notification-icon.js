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

  static SSE_RECONNECT_DELAY = 10000;
  static SSE_MAX_RECONNECT_DELAY = 120000;
  static REQUEST_TIMEOUT = 30000;

  constructor() {
    super();
    this.count = 0;
    this._eventSource = null;
    this._sseReconnectTimer = null;
    this._countRefreshPromise = null;
    this._handleNotificationsUpdated = this._handleNotificationsUpdated.bind(this);
    this._active = false;
    this._generation = 0;
    this._authStopped = false;
    this._needsAuthCheck = false;
    this._recovering = false;
    this._retryDelay = SCBilaraNotificationIcon.SSE_RECONNECT_DELAY;
    this._requests = new Set();
    this._streamHandlers = null;
    this._countVersion = 0;
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

  _isCurrent(generation) {
    return this._active && this._generation === generation && !this._authStopped;
  }

  _handleUnreadCountEvent(event) {
    try {
      const payload = JSON.parse(event.data || '{}');
      if (Number.isInteger(payload.unread_count) && payload.unread_count >= 0) {
        this.count = payload.unread_count;
        this._countVersion += 1;
        // Opening an HTTP connection alone does not mean counting has recovered.
        this._retryDelay = SCBilaraNotificationIcon.SSE_RECONNECT_DELAY;
      }
    } catch (error) {
      console.error('Failed to parse unread_count event:', error);
    }
  }

  _clearSseReconnectTimer() {
    if (this._sseReconnectTimer !== null) {
      clearTimeout(this._sseReconnectTimer);
      this._sseReconnectTimer = null;
    }
  }

  _startRealtimeStream() {
    if (!this._isCurrent(this._generation)) return;
    this._stopRealtimeStream();

    const stream = new EventSource('/api/v1/notifications/stream');
    this._eventSource = stream;
    const onCount = event => {
      if (this._eventSource === stream) this._handleUnreadCountEvent(event);
    };
    const onQueryError = () => {
      if (this._eventSource === stream) this._handleStreamError(false);
    };
    const onConnectionError = () => {
      if (this._eventSource === stream) this._handleStreamError(true);
    };
    this._streamHandlers = { onCount, onQueryError };
    stream.addEventListener('unread_count', onCount);
    stream.addEventListener('stream_error', onQueryError);
    stream.onerror = onConnectionError;
  }

  _stopRealtimeStream() {
    this._clearSseReconnectTimer();
    if (this._eventSource) {
      const { onCount, onQueryError } = this._streamHandlers;
      this._eventSource.removeEventListener('unread_count', onCount);
      this._eventSource.removeEventListener('stream_error', onQueryError);
      this._eventSource.onerror = null;
      this._eventSource.close();
      this._eventSource = null;
      this._streamHandlers = null;
    }
  }

  _handleStreamError(needsAuthCheck) {
    if (!this._isCurrent(this._generation)) return;
    this._stopRealtimeStream();
    this._needsAuthCheck ||= needsAuthCheck;
    if (!this._recovering) this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (!this._isCurrent(this._generation) || this._sseReconnectTimer !== null) return;
    const generation = this._generation;
    const delay = this._retryDelay * (0.5 + Math.random() * 0.5);
    this._retryDelay = Math.min(
      this._retryDelay * 2,
      SCBilaraNotificationIcon.SSE_MAX_RECONNECT_DELAY,
    );
    this._sseReconnectTimer = setTimeout(() => {
      this._sseReconnectTimer = null;
      void this._recoverStream(generation);
    }, delay);
  }

  async _recoverStream(generation) {
    if (!this._isCurrent(generation)) return;
    this._recovering = true;
    try {
      // A local update may already be counting. Do not overlap it with recovery.
      await this._countRefreshPromise;
      if (!this._isCurrent(generation)) return;
      if (this._needsAuthCheck) {
        const status = await this._checkAuthentication();
        if (!this._isCurrent(generation)) return;
        if (status === 401 || status === 403) {
          this._authStopped = true;
          this._stopRealtimeStream();
          return;
        }
        if (status < 200 || status >= 300) throw new Error(`HTTP error! status: ${status}`);
        this._needsAuthCheck = false;
      }
      this._startRealtimeStream();
    } catch (error) {
      if (this._isCurrent(generation)) this._scheduleReconnect();
    } finally {
      if (this._generation === generation) this._recovering = false;
    }
  }

  async _withRequest(operation) {
    const controller = new AbortController();
    this._requests.add(controller);
    const timeout = setTimeout(() => controller.abort(), SCBilaraNotificationIcon.REQUEST_TIMEOUT);
    const checkAborted = () => {
      if (controller.signal.aborted) throw new DOMException('Request aborted', 'AbortError');
    };
    const request = (url, options = {}) => {
      checkAborted();
      return fetch(url, { ...options, credentials: 'include', signal: controller.signal });
    };
    try {
      const result = await operation(request);
      checkAborted();
      return result;
    } finally {
      clearTimeout(timeout);
      this._requests.delete(controller);
    }
  }

  _checkAuthentication() {
    // EventSource does not expose the handshake's HTTP status. This probe does
    // not run notification queries; keep refresh/network failures distinguishable.
    return this._withRequest(async request => {
      let response = await request('/api/v1/users/me', { cache: 'no-store' });
      if (response.status === 401) {
        response = await request('/api/v1/refresh/', { method: 'POST' });
        if (response.ok) response = await request('/api/v1/users/me', { cache: 'no-store' });
      }
      return response.status;
    });
  }

  async _refreshNotificationCount() {
    if (this._countRefreshPromise) return this._countRefreshPromise;
    if (!this._isCurrent(this._generation) || this._recovering || this._sseReconnectTimer !== null) return;
    const generation = this._generation;
    const countVersion = this._countVersion;
    const refresh = (async () => {
      try {
        const result = await this._withRequest(async request => {
          const response = await request('/api/v1/notifications/count');
          return { status: response.status, ok: response.ok, data: response.ok ? await response.json() : null };
        });
        if (!this._isCurrent(generation)) return;
        if (result.status === 401) {
          this._handleStreamError(true);
          return;
        }
        if (result.status === 403) {
          this._authStopped = true;
          this._stopRealtimeStream();
          return;
        }
        if (!result.ok) throw new Error(`HTTP error! status: ${result.status}`);
        if (!Number.isInteger(result.data.unread_count) || result.data.unread_count < 0) {
          throw new Error('Invalid notification count response');
        }
        if (this._countVersion === countVersion) this.count = result.data.unread_count;
      } catch (error) {
        if (this._isCurrent(generation) && error.name !== 'AbortError') {
          console.error('Failed to refresh notification count:', error);
        }
      } finally {
        if (this._countRefreshPromise === refresh) this._countRefreshPromise = null;
      }
    })();
    this._countRefreshPromise = refresh;
    return refresh;
  }

  async _handleNotificationsUpdated() {
    await this._refreshNotificationCount();
  }

  connectedCallback() {
    super.connectedCallback();
    this._generation += 1;
    this._active = true;
    this._authStopped = false;
    this._needsAuthCheck = false;
    this._recovering = false;
    this._retryDelay = SCBilaraNotificationIcon.SSE_RECONNECT_DELAY;
    this._startRealtimeStream();
    window.addEventListener('notifications-updated', this._handleNotificationsUpdated);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._active = false;
    this._generation += 1;
    this._stopRealtimeStream();
    for (const controller of this._requests) controller.abort();
    this._countRefreshPromise = null;
    window.removeEventListener('notifications-updated', this._handleNotificationsUpdated);
  }

}

customElements.define('sc-bilara-notification-icon', SCBilaraNotificationIcon);
