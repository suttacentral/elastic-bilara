import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

class SCBilaraNotificationIcon extends LitElement {
  static styles = css`
    .icon-wrapper {
      position: relative;
      display: inline-block;
    }

    .notification-count {
      position: absolute;
      top: -6px;
      right: -6px;
      width: 24px;
      height: 24px;
      background-color: #c21f30;
      color: #fff;
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
        <div class="">
          <a href="/notifications" target="_blank"><img src="./static/img/notification.png" alt="notification"/></a>
          ${this.count > 0
            ? html`<div class="notification-count">${this.count}</div>`
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