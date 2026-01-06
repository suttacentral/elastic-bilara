import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';

export class SCBilaraNavMainMobile extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
      }

      nav {
        border-bottom: 1px solid var(--color-disabled, #e0e0e0);
        box-shadow: 0 2px 4px var(--color-shadow, rgba(0, 0, 0, 0.1));
        background-color: var(--color-background-tertiary, #BEB9AA);
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
                <a :href="'https://github.com/' + username" class="username-link">
                  <figure class="user-container" x-cloak x-show="!!username">
                      <img
                        :src="avatarURL"
                        x-bind:alt="username + 's github profile picture'"
                        class="user-avatar"
                        title="profile picture"/>
                      <figcaption x-text="username"></figcaption>
                  </figure>
                </a>
              </li>
              <li class="main-nav-mobile__item"
                  :class="isOpen ? 'main-nav-mobile__item--show' : 'main-nav-mobile__item--hide'" x-cloak
                  x-show="isAdmin && isActive">
                  <a class="main-nav-mobile__item-link btn btn--admin" href="/admin">Admin</a>
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
