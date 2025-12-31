import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';
import '../addons/sc-bilara-circle-badge.js';

class SCBilaraNotificationIcon extends LitElement {
  static styles = css`
    .icon-wrapper {
      position: relative;
      display: inline-block;
    }

    .notification-icon {
      height: 32px;
      vertical-align: middle;
      fill: var(--color-primary);
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

  constructor() {
    super();
    this.count = 0;
  }

  render() {
    return html`
      <div class="icon-wrapper">
        <div>
          <a href="/notifications" target="_blank"><svg class='notification-icon' xmlns="http://www.w3.org/2000/svg" height="40px" viewBox="0 -960 960 960" width="40px" fill="#e3e3e3"><path d="M160-200v-66.67h80v-296q0-83.66 49.67-149.5Q339.33-778 420-796v-24q0-25 17.5-42.5T480-880q25 0 42.5 17.5T540-820v24q80.67 18 130.33 83.83Q720-646.33 720-562.67v296h80V-200H160Zm320-301.33ZM480-80q-33 0-56.5-23.5T400-160h160q0 33-23.5 56.5T480-80ZM306.67-266.67h346.66v-296q0-72-50.66-122.66Q552-736 480-736t-122.67 50.67q-50.66 50.66-50.66 122.66v296Z"/></svg></a>
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

  firstUpdated() {
    this.fetchNotification().then((data) => {
      this.count = data.length;
    });
  }
}

customElements.define('sc-bilara-notification-icon', SCBilaraNotificationIcon);