import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

export class SCBilaraAdminHeader extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }
    `
  ];

  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <nav class="admin-header-nav">
          <ul class="admin-header-list">
              <li class="admin-header-brand">
                  <a href="/nav">Bilara</a>
              </li>
              <li class="admin-header-howto">
                  <details>
                      <summary>How to</summary>
                      <div class="admin-header-dropdown"></div>
                      <!-- Add this later-->
                  </details>
              </li>
              <li class="admin-header-user">
                  <div class="admin-header-user-info" x-cloak x-show="!!username">
                      <img :src="avatarURL"
                          :alt="username + 's github profile picture'"
                          class="admin-header-avatar"/>
                      <span>Welcome, <strong x-text="username"></strong>!</span>
                  </div>
              </li>
              <li class="admin-header-admin-link" x-cloak x-show="isAdmin && isActive">
                  <a class="admin-header-btn" href="/admin">Admin Area</a>
              </li>
              <li class="admin-header-logout">
                  <a class="admin-header-btn" @click.prevent="await logout()">Logout</a>
              </li>
          </ul>
      </nav>
    `;
  }
}

customElements.define('sc-bilara-admin-header', SCBilaraAdminHeader);
