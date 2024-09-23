import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

import { unsafeHTML } from 'https://cdn.jsdelivr.net/npm/lit-html@3.2.0/directives/unsafe-html.js';

import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/button/button.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/alert/alert.js';
import "https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/tooltip/tooltip.js";
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/badge/badge.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/button-group/button-group.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/spinner/spinner.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/skeleton/skeleton.js';

import '../addons/sc-bilara-badge.js';
import "../../auth.js";
import "../../utils.js";

class SCBilaraNotification extends LitElement {
  static styles = css`
    :host {
      background-color: var(--color-primary-lighter);
      margin: 0;
      padding: 20px;
    }

    .notification {
      background-color: #ffffff;
      border: 1px solid #e1e4e8;
      border-radius: 6px;
      padding: 15px;
      margin-bottom: 10px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .notification-content {
      margin: 10px 0;
    }

    .notification {
      background-color: var(--color-primary-lighter);
    }

    .notify-item:hover {
      background-color: var(--color-primary-light);
    }

    .notify-item {
      display: flex;
      flex-direction: row;
      justify-content: space-between;
      background-color: var(--color-primary-light);
      border: 1px solid #ccc;
      border-radius: 5px;
      padding: 10px;
      margin: 10px 0;
      font-family: Arial, sans-serif;
      font-size: 14px;
      color: #333;
    }

    .notify-item div {
      display: flex;
      flex-direction: column;
    }

    .notify-item strong {
      color: #007bff;
      font-size: 16px;
    }

    ul {
      list-style-type: none;
      padding-left: 10px;
      padding-right: 10px;

    }

    li {
      font-size: var(--text-lg)
    }

    .notify-item a {
      text-decoration: none;
    }

    .notify-item a:hover {
      text-decoration: underline;
    }

    .notify-item p {
      margin: 1px;
    }

    .effected-file {
      display: flex;
      justify-content: space-between;
    }

    .sc-link-button, .notify-item-detail {
      font-size: 16px;
    }

    .effected-file div {
      margin: 10px;
    }

    .delete {
      background-color: #ffebe9;
    }

    .add {
      background-color: #dafbe1;
    }

    .spinner {
      text-align: center;
    }

    .skeleton-overview header {
        display: flex;
        align-items: center;
        margin-bottom: 1rem;
      }

      .skeleton-overview header sl-skeleton:last-child {
        flex: 0 0 auto;
        width: 30%;
      }

      .skeleton-overview sl-skeleton {
        margin-bottom: 1rem;
      }

      .skeleton-overview sl-skeleton:nth-child(1) {
        float: left;
        width: 3rem;
        height: 3rem;
        margin-right: 1rem;
        vertical-align: middle;
      }

      .skeleton-overview sl-skeleton:nth-child(3) {
        width: 95%;
      }

      .skeleton-overview sl-skeleton:nth-child(4) {
        width: 80%;
      }

      sl-alert {
        margin-bottom: 3px;
      }
  `;

  static properties = {
    notifications: { type: Array },
  };

  constructor() {
    super();
    this.notification = [];
    this.loadingData = true;
  }

  render() {
    return html`
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/themes/light.css" />
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
      <div class="notification">
        <h2>
          <i class="bi-bell"></i>Notifications
          <sl-badge variant="danger" pill>${this.notification.length}</sl-badge>
        </h2>
        <div class="spinner">
          ${this.loadingData ? html`<sl-spinner style="font-size: 50px; --track-width: 6px;"></sl-spinner>` : ''}
        </div>

        <div class="notification-content">
          ${this.loadingData ? html`${this.skeletonTemplate()}` : ''}
          ${this.notification.length > 0 ? this.notification?.map(notify => html`
            <div class="notify-item">
                <div>
                  <p class="notify-item-detail"><strong>Author:</strong> ${notify.author}</p>
                  <p class="notify-item-detail"><strong>Date:</strong> ${notify.date}</p>
                </div>

                <sl-button-group label="Alignment">
                  <sl-button variant="primary" @click="${() => this.#setNotificationAsDone(notify.commit)}">Done <i class="bi-check-circle-fill"></i></sl-button>
                  <sl-button href="${'https://github.com/ihongda/bilara-data/commit/'+notify.commit}" target="_blank" variant="primary">View in Github <i class="bi-github"></i></sl-button>
                </sl-button-group>
            </div>
            <ul>${notify.effected_files.map(file => html`
              <li class="effected-file">
                <div>${file.file_name}<sc-bilara-badge text="${file.file_type}" color="badge-${file.file_type}"></sc-bilara-badge></div>
                <sl-button href="${file.sc_url}" target="_blank" variant="primary">View in SuttaCentral</sl-button>
              </li>
              <div>
                <sl-alert variant="primary" open> ${file.file_name.includes('_html') ?  html`<pre>${file.change_detail}</pre>` : unsafeHTML(file.change_detail)} </sl-alert>
              </div>
              `)}
            </ul>
          `) : ''}
      </div>
    </div>
    `;
  }

  skeletonTemplate() {
    let skeletons = [1, 2, 3, 4]
    return html`
      ${skeletons.map(() => html`
        <div class="skeleton-overview">
          <header>
            <sl-skeleton></sl-skeleton>
            <sl-skeleton></sl-skeleton>
          </header>

          <sl-skeleton></sl-skeleton>
          <sl-skeleton></sl-skeleton>
          <sl-skeleton></sl-skeleton>
        </div>
      `)}
    `;
  }

  firstUpdated() {
    this.fetchNotification();
  }

  async _getUserInfo() {
    const userInfo = getUserInfo();
    await userInfo.getRole();
  }

  async #setNotificationAsDone(commitId) {
    const response = await requestWithTokenRetry(`notifications/done/${commitId}`);
    const data = await response.json();
    if (data.success) {
      this.fetchNotification();
    }
  }

  async fetchNotification() {
    this.loadingData = true;
    try {
      const response = await fetch(`api/v1/notifications/git`);
      const data = await response.json();
      if (!data.git_recent_commits) {
          throw new Error("Invalid data format from the API");
      }
      this.notification = data.git_recent_commits;
      this.requestUpdate();
    } catch (error) {
        throw new Error(error);
    }
    this.loadingData = false;
  }
}

customElements.define('sc-bilara-notification', SCBilaraNotification);
