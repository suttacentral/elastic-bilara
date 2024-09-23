import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

export class SCBilaraNavMainMobile extends LitElement {
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
          <ul class="main-nav-mobile" x-data="{isOpen: false}">
              <li class="main-nav-mobile__item main-nav-mobile__item--full main-nav-mobile__item--show main-nav-mobile__item--space-between">
                  <a href="/nav" class="main-nav-mobile__item-link">Bilara</a>
                  <div class="main-nav-mobile__burger" @click="isOpen = !isOpen"
                      :class="{ 'open': isOpen }">
                      <span class="main-nav-mobile__burger--line"></span>
                      <span class="main-nav-mobile__burger--line"></span>
                  </div>
              </li>
              <li class="main-nav-mobile__item"
                  :class="isOpen ? 'main-nav-mobile__item--show' : 'main-nav-mobile__item--hide'">
                  <div class="user-container" x-cloak x-show="!!username">
                      <img :src="avatarURL"
                          x-bind:alt="username + 's github profile picture'"
                          class="user-avatar"/>
                      <span class="user-welcome">Welcome, <strong x-text="username"></strong>!</span>
                  </div>
              </li>
              <li class="main-nav-mobile__item"
                  :class="isOpen ? 'main-nav-mobile__item--show' : 'main-nav-mobile__item--hide'" x-cloak
                  x-show="isAdmin && isActive">
                  <a class="main-nav-mobile__item-link btn btn--admin" href="/admin">Admin Area</a>
              </li>
              <li class="main-nav-mobile__item"
                  :class="isOpen ? 'main-nav-mobile__item--show' : 'main-nav-mobile__item--hide'">
                  <a class="main-nav-mobile__item-link btn btn--main" @click.prevent="await logout()">Logout</a>
              </li>
          </ul>
      </nav>
    `;
  }
}
customElements.define('sc-bilara-nav-main-mobile', SCBilaraNavMainMobile);
