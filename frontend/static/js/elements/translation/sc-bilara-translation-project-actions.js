import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/spinner/spinner.js';

export class ScBilaraTranslationProjectActions extends LitElement {
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
          <button class="project-header__nav-button btn--split btn--preview-action"
              x-data="{ caption: 'split', previewProcessing: false }"
              @click="withGuard($data, 'previewProcessing', async () => {
                  if (await splitBasedOnUid(translations, uid, document.querySelector('span.project-header__message'))) {
                      splitting = true; merging = false; splittingUid = uid;
                  }
              })"
              x-show="isSource && isRoot && isAdmin && isActive && (!splitting && !merging)"
              x-bind:disabled="splitting || merging || previewProcessing || relatedProjectsLocked() || relatedProjectLoads > 0"
              x-bind:class="{'btn--disabled': splitting || merging || previewProcessing || relatedProjectsLocked() || relatedProjectLoads > 0}">
              <span x-text="caption"></span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': previewProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>
          <button class="project-header__nav-button btn--merge btn--preview-action"
              x-data="{ caption: 'merge', previewProcessing: false }"
              @click="withGuard($data, 'previewProcessing', async () => {
                  if (await mergeBasedOnUid(translations, uid, document.querySelector('span.project-header__message'))) {
                      splitting = false; merging = true; mergingUid = uid;
                  }
              })"
              x-show="isSource && isRoot && isAdmin && isActive && rowIndex !== Object.keys(translation.data).length - 1 && (!splitting && !merging)"
              x-bind:disabled="merging || splitting || previewProcessing || relatedProjectsLocked() || relatedProjectLoads > 0"
              x-bind:class="{'btn--disabled': merging || splitting || previewProcessing || relatedProjectsLocked() || relatedProjectLoads > 0}">
              <span x-text="caption"></span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': previewProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>

    `;
  }
}
customElements.define('sc-bilara-translation-project-actions', ScBilaraTranslationProjectActions);
