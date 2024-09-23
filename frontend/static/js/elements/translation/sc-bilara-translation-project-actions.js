import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm';

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
          <p class="project-container__content-body__text"
              :class="{'project-container__content-body__text--hide': translation.muid !== new URLSearchParams(window.location.search).get('source')}"
              x-text="uid">
          </p>
          <button class="project-header__nav-button btn btn--split"
              x-data="{ caption: 'Split' }"
              x-text="caption"
              @click="
                  if (splitBasedOnUid(translations, uid, document.querySelector('p.project-header__message'))) {
                      splitting = true;
                      merging = false;
                      splittingUid = uid;
                  }"
              x-show="isSource && isAdmin && isActive && (!splitting && !merging)"
              x-bind:disabled="splitting || merging"
              x-bind:class="{'btn--disabled': splitting || merging}">
          </button>
          <button class="project-header__nav-button btn btn--merge"
              x-data="{ caption: 'Merge' }"
              x-text="caption"
              @click="
                  if (mergeBasedOnUid(translations, uid, document.querySelector('p.project-header__message'))) {
                      splitting = false;
                      merging=true;
                      mergingUid = uid;
                  }"
              x-show="isSource && isAdmin && isActive && i !== Object.keys(translation.data).length - 1 && (!splitting && !merging)"
              x-bind:disabled="merging || splitting"
              x-bind:class="{'btn--disabled': merging || splitting}">
          </button>

          <button class="project-header__nav-button btn btn--cancel"
              @click="cancelSplit(translations); splitting=false;"
              x-show="splitting && translation.isSource && uid === splittingUid"
          >
              Cancel Split
          </button>
          <button class="project-header__nav-button btn btn--cancel"
              @click="cancelMerge(translations); merging=false;"
              x-show="merging && translation.isSource && uid === mergingUid"
          >
              Cancel Merge
          </button>

          <button
              x-data="{params: new URLSearchParams(window.location.search)}"
              class="project-header__nav-button btn btn--split"
              x-show="translation.canEdit && isAdmin && splitting && isRoot && uid === splittingUid"
              @click="
                  splitting = false;
                  await updateHandlerForSplit(translation.muid || sourceMuid, params.get('prefix'), document.querySelector('p.project-header__message'));
              "
          >
              Check Split, Then Confirm
          </button>

          <button
              x-data="{params: new URLSearchParams(window.location.search)}"
              class="project-header__nav-button btn btn--merge"
              x-show="translation.canEdit && isAdmin && merging && isRoot && uid === mergingUid"
              @click="
                  merging = false;
                  await updateHandlerForMerge(translation.muid || sourceMuid, params.get('prefix'), document.querySelector('p.project-header__message'));
              "
          >
              Check Merge, Then Confirm
          </button>
      </div>
    `;
  }
}
customElements.define('sc-bilara-translation-project-actions', ScBilaraTranslationProjectActions);
