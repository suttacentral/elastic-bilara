import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';

export class SCBilaraTranslationProjectHeader extends LitElement {
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
      <style>
          .project-header {
              display: flex;
              justify-content: space-between;
              align-items: center;
              padding: 0px 5px 0px 20px;
              background-color: transparent;
              border-radius: 0;
              box-shadow: none;
              border: none;
              border-bottom: 1px solid var(--color-background-tertiary);
              gap: 12px;
          }

          .project-header__message {
              font-weight: 600;
              margin: 0;
              color: var(--color-primary);
              letter-spacing: var(--letter-spacing);
              text-transform: uppercase;
              position: relative;
              padding-left: 0px;
              flex-shrink: 0;
          }

          /* Progress Bar - Horizontal */
          .project-header__progress {
              display: flex;
              align-items: center;
              gap: 8px;
              flex: 1;
              max-width: 350px;
              min-width: 120px;
          }

          .project-header__progress-bar {
              flex: 1;
              height: 8px;
              background-color: var(--color-background);
              border-radius: 2px;
              overflow: hidden;
              position: relative;
          }

          .project-header__progress-fill {
              position: absolute;
              left: 0;
              top: 0;
              bottom: 0;
              background-color: var(--color-success);
              border-radius: 2px;
              transition: width 0.3s ease;
          }

          .project-header__progress-text {
              font-size: 0.7rem;
              font-weight: 600;
              color: var(--color-primary);
              white-space: nowrap;
          }

          .project-header__progress-detail {
              font-size: 0.65rem;
              color: var(--color-text-secondary);
              white-space: nowrap;
          }

          .project-header__progress-go-btn {
              padding: 2px 8px;
              font-size: 0.65rem;
              font-weight: 600;
              text-transform: uppercase;
              letter-spacing: 0.5px;
              color: white;
              background-color: var(--color-success);
              border: none;
              border-radius: 3px;
              cursor: pointer;
              transition: all 0.2s ease;
              box-shadow: var(--shadow-sm);
          }

          .project-header__progress-go-btn:hover {
              transform: translateY(-1px);
              box-shadow: var(--shadow-sm);
              background-color: var(--color-success);
          }

          .project-header__nav {
              display: flex;
              align-items: center;
              flex-shrink: 0;
              margin-right: auto;
              padding: var(--space-xs) var(--space-sm);
          }

          .project-header__nav-list {
              display: flex;
              list-style: none;
              margin: 0;
              padding: 0;
              justify-content: right;
              gap: var(--space-md);
          }

          .project-header__nav-button {
              padding: 0 8px;
              border-radius: var(--radius-md);
              cursor: pointer;
              transition: var(--transition);
              background-color: var(--secondary-background-color);
              white-space: nowrap;
              font-size: var(--text-xs);
          }

          .project-header__nav-item {
              display: flex;
              align-items: center;
          }

          .project-header__nav-item sl-button::part(base) {
              font-weight: 500;
              font-size: 0.7rem;
              padding: 4px 8px;
              min-height: unset;
              transition: all 0.2s ease;
          }

          .project-header__nav-item sl-button::part(base):hover {
              transform: translateY(-1px);
              box-shadow: var(--shadow-sm);
          }

          @media (min-width: 1280px) {
              .project-header__search-toggle {
                  display: none !important;
              }
          }

          @media (max-width: 768px) {
              .project-header {
                  flex-wrap: wrap;
                  gap: 6px;
              }

              .project-header__progress {
                  order: 3;
                  width: 100%;
                  max-width: none;
              }
          }
      </style>
      <div class="project-header"
           x-data="{
               prefix: new URLSearchParams(window.location.search).get('prefix'),
               translated: 0,
               total: 0,
               percentage: 0,
               muid: new URLSearchParams(window.location.search).get('muid'),
               userRole: '',
               username: '',
               get canSeeGoBtn() {
                   if (this.userRole === ROLES.admin || this.userRole === ROLES.superuser) {
                       return true;
                   }
                   if (!this.muid || !this.username) return false;
                   const parts = this.muid.split('-');
                   return parts.includes(this.username);
               },
               async init() {
                   const userInfo = getUserInfo();
                   await userInfo.getRole();
                   this.userRole = userInfo.role;
                   this.username = userInfo.username;

                   window.addEventListener('translation-progress-update', (e) => {
                       this.translated = e.detail.translated;
                       this.total = e.detail.total;
                       this.percentage = e.detail.percentage;
                   });
               },
               goToUnpublished() {
                   window.location.href = 'git_status_panel.html?filter=' + encodeURIComponent(this.muid);
               }
           }">
          <span class="project-header__message" x-text="prefix"></span>

          <!-- Horizontal Progress Bar -->
          <div class="project-header__progress" title="Translation progress">
              <div class="project-header__progress-bar">
                  <div class="project-header__progress-fill" :style="'width: ' + percentage + '%'"></div>
              </div>
              <span class="project-header__progress-text" x-text="percentage + '%'"></span>
              <span class="project-header__progress-detail" x-text="'(' + translated + '/' + total + ')'"></span>
              <button x-cloak
                  x-show="percentage >= 90 && canSeeGoBtn"
                  @click="goToUnpublished()"
                  class="project-header__progress-go-btn"
                  title="Go to Unpublished Changes">
                  Go
              </button>
          </div>

          <nav class="project-header__nav">
              <ul class="project-header__nav-list">
                  <li class="project-header__nav-item">
                      <sl-button size="small" variant="warning" outline @click="$dispatch('toggle-detail-panel', {panel: 'related'});">
                          <i class="bi bi-collection" style="margin-right: 6px;"></i>Related
                      </sl-button>
                  </li>
                  <li class="project-header__nav-item project-header__search-toggle">
                      <sl-button size="small" variant="warning" outline
                           @click="$dispatch('toggle-search-panel')"
                           x-data="{ panelVisible: window.innerWidth >= 1280 }"
                           @toggle-search-panel.window="panelVisible = !panelVisible"
                           @show-search-panel.window="panelVisible = true"
                           @resize.window="if(window.innerWidth >= 1280) panelVisible = true"
                           :title="panelVisible ? 'Hide search panel' : 'Show search panel'">
                           <i class="bi" :class="panelVisible ? 'bi-layout-sidebar-reverse' : 'bi-layout-sidebar'" style="margin-right: 6px;"></i>
                          <span x-text="panelVisible ? 'Hide Search Panel' : 'Show Search Panel'"></span>
                      </sl-button>
                  </li>
              </ul>
          </nav>
      </div>
    `;
  }
}

customElements.define('sc-bilara-translation-project-header', SCBilaraTranslationProjectHeader);
