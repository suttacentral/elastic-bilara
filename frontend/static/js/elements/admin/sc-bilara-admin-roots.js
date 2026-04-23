import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminRoots extends LitElement {

    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="dataTypes.roots" x-init="await getData(base)">
              <div class="admin-section-header">
                  <h1 class="admin-section-title">Root Files Management</h1>
              </div>
              <p x-cloak id="rootCreateMessage" x-show="message" class="admin-alert admin-alert-success admin-text-center"></p>
              <div class="admin-card">
                  <div class="admin-card-body">
                      <div class="admin-roots-form">
                          <input id="baseInput" class="admin-input" type="text" x-model="base"
                                 @input="await handleInput()"
                                 @keyup="await handleKeyUp($event)"
                                 list="baseSuggestions"
                                 placeholder="Enter root path">
                          <datalist id="baseSuggestions">
                              <template x-for="dir in directories" :key="dir">
                                  <option x-bind:value="dir"></option>
                              </template>
                              <template x-for="file in files" :key="file">
                                  <option x-bind:value="file"></option>
                              </template>
                          </datalist>
                      </div>
                      <div class="admin-form-actions">
                          <div id="loadingContainer"></div>
                          <button @click.prevent="await create()" class="btn admin-btn admin-btn-primary">
                              <i class="bi-plus-circle"></i> Create
                          </button>
                      </div>
                      <div x-cloak x-show="isFile" class="admin-roots-segments admin-mt-2">
                          <template x-for="(data, index) in rootData" :key="index">
                              <div class="admin-roots-row">
                                  <input class="admin-input" type="text" x-model="data.id"
                                         @focus="addInputPair(index)"
                                         placeholder="Segment ID"
                                         :style="index === (rootData.length - 1) ? 'cursor: pointer' : ''">
                                  <input class="admin-input" type="text" x-model="data.value"
                                         placeholder="Segment Value">
                              </div>
                          </template>
                      </div>
                  </div>
              </div>
          </div>
        `;
    }
}

customElements.define('sc-bilara-admin-roots', ScBilaraAdminRoots);
