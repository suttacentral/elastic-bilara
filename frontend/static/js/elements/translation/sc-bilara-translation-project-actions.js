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
      <div class="project-container__content-body__action">
          <span class="project-container__content-body__text-uid"
              :class="{'project-container__content-body__text--hide': translation.muid !== new URLSearchParams(window.location.search).get('source')}"
              x-text="uid">
          </span>
          <button class="project-header__nav-button btn--split btn--preview-action"
              x-data="{ caption: 'split', previewProcessing: false }"
              @click="withGuard($data, 'previewProcessing', async () => {
                  if (await splitBasedOnUid(translations, uid, document.querySelector('span.project-header__message'))) {
                      splitting = true; merging = false; splittingUid = uid;
                  }
              })"
              x-show="isSource && isAdmin && isActive && (!splitting && !merging)"
              x-bind:disabled="splitting || merging || previewProcessing"
              x-bind:class="{'btn--disabled': splitting || merging || previewProcessing}">
              <span x-text="caption"></span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': previewProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>
          <button class="project-header__nav-button btn--merge btn--preview-action"
              x-data="{ caption: 'merge', previewProcessing: false }"
              @click="withGuard($data, 'previewProcessing', async () => {
                  if (mergeBasedOnUid(translations, uid, document.querySelector('span.project-header__message'))) {
                      splitting = false; merging = true; mergingUid = uid;
                  }
              })"
              x-show="isSource && isAdmin && isActive && i !== Object.keys(translation.data).length - 1 && (!splitting && !merging)"
              x-bind:disabled="merging || splitting || previewProcessing"
              x-bind:class="{'btn--disabled': merging || splitting || previewProcessing}">
              <span x-text="caption"></span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': previewProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>

          <button class="project-header__nav-button btn btn--cancel btn--preview-action"
              x-data="{ cancelProcessing: false }"
              @click="if (splitMergeProcessing) return; withGuard($data, 'cancelProcessing', () => {
                  cancelSplit(translations); splitting = false;
              })"
              x-show="splitting && translation.isSource && uid === splittingUid"
              :disabled="splitMergeProcessing || cancelProcessing"
              :class="{'btn--disabled': splitMergeProcessing || cancelProcessing}"
          >
              <span>Cancel Split</span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': cancelProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>
          <button class="project-header__nav-button btn btn--cancel btn--preview-action"
              x-data="{ cancelProcessing: false }"
              @click="if (splitMergeProcessing) return; withGuard($data, 'cancelProcessing', () => {
                  cancelMerge(translations); merging = false;
              })"
              x-show="merging && translation.isSource && uid === mergingUid"
              :disabled="splitMergeProcessing || cancelProcessing"
              :class="{'btn--disabled': splitMergeProcessing || cancelProcessing}"
          >
              <span>Cancel Merge</span>
              <span class="btn__preview-loading" :class="{ 'btn__preview-loading--visible': cancelProcessing }" aria-hidden="true">
                  <sl-spinner class="btn__preview-spinner"></sl-spinner>
              </span>
          </button>

          <button
              x-data="{params: new URLSearchParams(window.location.search), processing: false}"
              class="project-header__nav-button btn--split btn--confirm-split-merge"
              x-show="translation.canEdit && isAdmin && splitting && isRoot && uid === splittingUid"
              :disabled="processing || splitMergeProcessing"
              :class="{'btn--disabled': processing || splitMergeProcessing}"
              @click="
                  if (splitMergeProcessing) return;
                  processing = true;
                  splitMergeProcessing = true;
                  try {
                      const result = await updateHandlerForSplit(translation.muid || sourceMuid, params.get('prefix'), document.querySelector('span.project-header__message'));
                      if (result) {
                          affectedFiles = result.affectedFiles;
                          affectedPrefix = result.prefix;
                          const toast = document.querySelector('sc-bilara-toast');
                          if (toast) toast.show('Split completed - ' + result.autoPublishedPaths.length + ' scheduled for GitHub, ' + result.manualPublishPaths.length + ' left for manual publish', 'success', 5000);
                          $nextTick(() => document.querySelector('.dialog-affected-files')?.show());
                      }
                  } catch (e) {
                      const toast = document.querySelector('sc-bilara-toast');
                      if (toast) toast.show('Split failed: ' + e.message, 'error', 5000);
                  } finally {
                      processing = false;
                      splitMergeProcessing = false;
                      splitting = false;
                  }
              "
          >
              <span x-show="!processing">Check Split, Then Confirm</span>
              <span x-show="processing" class="btn__loading-content">
                  <sl-spinner class="btn__loading-spinner"></sl-spinner>
                  Processing...
              </span>
          </button>

          <button
              x-data="{params: new URLSearchParams(window.location.search), processing: false}"
              class="project-header__nav-button btn--merge btn--confirm-split-merge"
              x-show="translation.canEdit && isAdmin && merging && isRoot && uid === mergingUid"
              :disabled="processing || splitMergeProcessing"
              :class="{'btn--disabled': processing || splitMergeProcessing}"
              @click="
                  if (splitMergeProcessing) return;
                  processing = true;
                  splitMergeProcessing = true;
                  try {
                      const result = await updateHandlerForMerge(translation.muid || sourceMuid, params.get('prefix'), document.querySelector('span.project-header__message'));
                      if (result) {
                          affectedFiles = result.affectedFiles;
                          affectedPrefix = result.prefix;
                          const toast = document.querySelector('sc-bilara-toast');
                          if (toast) toast.show('Merge completed - ' + result.autoPublishedPaths.length + ' scheduled for GitHub, ' + result.manualPublishPaths.length + ' left for manual publish', 'success', 5000);
                          $nextTick(() => document.querySelector('.dialog-affected-files')?.show());
                      }
                  } catch (e) {
                      const toast = document.querySelector('sc-bilara-toast');
                      if (toast) toast.show('Merge failed: ' + e.message, 'error', 5000);
                  } finally {
                      processing = false;
                      splitMergeProcessing = false;
                      merging = false;
                  }
              "
          >
              <span x-show="!processing">Check Merge, Then Confirm</span>
              <span x-show="processing" class="btn__loading-content">
                  <sl-spinner class="btn__loading-spinner"></sl-spinner>
                  Processing...
              </span>
          </button>
      </div>
    `;
  }
}
customElements.define('sc-bilara-translation-project-actions', ScBilaraTranslationProjectActions);
