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
              padding: 4px 16px;
              background: transparent;
              border-radius: 0;
              box-shadow: none;
              margin: 0 16px;
              border: none;
              border-bottom: 1px solid var(--color-background-tertiary, #e0dcd0);
              gap: 12px;
          }

          .project-header__message {
              font-size: 0.9rem;
              font-weight: 600;
              margin: 0;
              color: var(--color-primary, #8b6914);
              letter-spacing: 0.5px;
              text-transform: uppercase;
              position: relative;
              padding-left: 8px;
              flex-shrink: 0;
          }

          .project-header__message::before {
              content: '';
              position: absolute;
              left: 0;
              top: 50%;
              transform: translateY(-50%);
              width: 2px;
              height: 50%;
              background: var(--color-primary, #8b6914);
              border-radius: 1px;
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
              background: var(--color-background-tertiary, #e0dcd0);
              border-radius: 2px;
              overflow: hidden;
              position: relative;
          }

          .project-header__progress-fill {
              position: absolute;
              left: 0;
              top: 0;
              bottom: 0;
              background: linear-gradient(to right, var(--color-success, #28a745), #56c271);
              border-radius: 2px;
              transition: width 0.3s ease;
          }

          .project-header__progress-text {
              font-size: 0.7rem;
              font-weight: 600;
              color: var(--color-primary, #8b6914);
              white-space: nowrap;
          }

          .project-header__progress-detail {
              font-size: 0.65rem;
              color: var(--color-text-secondary, #666);
              white-space: nowrap;
          }

          .project-header__progress-go-btn {
              padding: 2px 8px;
              font-size: 0.65rem;
              font-weight: 600;
              text-transform: uppercase;
              letter-spacing: 0.5px;
              color: white;
              background: linear-gradient(135deg, var(--color-success, #28a745), #56c271);
              border: none;
              border-radius: 3px;
              cursor: pointer;
              transition: all 0.2s ease;
              box-shadow: 0 1px 4px rgba(40, 167, 69, 0.3);
          }

          .project-header__progress-go-btn:hover {
              transform: translateY(-1px);
              box-shadow: 0 2px 6px rgba(40, 167, 69, 0.4);
              background: linear-gradient(135deg, #56c271, var(--color-success, #28a745));
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
              box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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
               init() {
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
          <div class="project-header__progress">
              <div class="project-header__progress-bar">
                  <div class="project-header__progress-fill" :style="'width: ' + percentage + '%'"></div>
              </div>
              <span class="project-header__progress-text" x-text="percentage + '%'"></span>
              <span class="project-header__progress-detail" x-text="'(' + translated + '/' + total + ')'"></span>
              <button x-cloak
                  x-show="percentage >= 90"
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
              </ul>
          </nav>
      </div>
    `;
  }
}

customElements.define('sc-bilara-translation-project-header', SCBilaraTranslationProjectHeader);
