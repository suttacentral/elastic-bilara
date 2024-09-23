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
      <nav class="h-full admin-nav">
          <ul class="flex items-center h-full">
              <li class="mx-4 uppercase tracking-wide font-bold">
                  <a href="/nav">Bilara</a>
              </li>
              <li>
                  <details class="relative">
                      <summary>How to</summary>
                      <div class="absolute"></div>
                      <!-- Add this later-->
                  </details>
              </li>
              <li class="ml-auto mr-2">
                  <div class="flex items-center h-10 space-x-2" x-cloak x-show="!!username">
                      <img :src="avatarURL"
                          :alt="username + 's github profile picture'"
                          class="h-full w-auto object-cover rounded-full border-2 border-amber-300"/>
                      <span>Welcome, <strong x-text="username"></strong>!</span>
                  </div>
              </li>
              <li :class="{'mr-2': isAdmin}" x-cloak x-show="isAdmin && isActive"><a
                      class="rounded py-2 px-4 bg-zinc-100 hover:bg-green-50 border border-neutral-500 hover:cursor-pointer"
                      href="/admin">Admin Area</a></li>
              <li class="mr-4">
                  <a
                          class="rounded py-2 px-4 bg-zinc-100 hover:bg-green-50 border border-neutral-500 hover:cursor-pointer"
                          @click.prevent="await logout()"
                  >Logout
                  </a>
              </li>
          </ul>
      </nav>
    `;
  }
}

customElements.define('sc-bilara-admin-header', SCBilaraAdminHeader);
