import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.16.0/cdn/components/button/button.js';

import '../notification/sc-bilara-notification-icon.js';

export class SCBilaraNavMain extends LitElement {
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
      <nav>
        <ul class="main-nav">
              <li class="main-nav__item">
                  <a href="/nav" class="main-nav__item-link">Bilara</a>
              </li>
              <li class="main-nav__item">
                  <details class="main-nav__item-detail">
                      <summary>How to</summary>
                      <div></div>
                      <!-- Add this later-->
                  </details>
              </li>
              <li class="main-nav__item main-nav__item--right hide-mobile">
                  <div class="user-container" x-cloak x-show="!!username">
                      <img
                        :src="avatarURL"
                        x-bind:alt="username + 's github profile picture'"
                        class="user-avatar"
                        title="profile picture"/>
                      <span class="user-welcome">Welcome, <strong x-text="username"></strong>!</span>
                  </div>
              </li>
              <div class="image-container">
                <sc-bilara-notification-icon></sc-bilara-notification-icon>
              </div>
              <li class="main-nav__item hide-mobile" x-cloak x-show="isAdmin && isActive">
                <a class="main-nav__item-link btn btn--admin" href="/admin">Admin Area</a>
              </li>
              <li class="main-nav__item hide-mobile">
                  <a class="main-nav__item-link btn btn--main" @click.prevent="await logout()">Logout</a>
              </li>
          </ul>
      </nav>
    `;
  }
}

customElements.define('sc-bilara-nav-main', SCBilaraNavMain);
