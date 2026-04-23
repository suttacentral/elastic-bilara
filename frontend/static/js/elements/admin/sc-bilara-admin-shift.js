import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminShift extends LitElement {

    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="dataTypes.shift">
              <div class="admin-section-header">
                  <h1 class="admin-section-title">Shift Segments</h1>
              </div>
              <div x-cloak x-show="loading" class="admin-loading">
                  <div class="admin-spinner"></div>
              </div>
              <div x-cloak x-show="message" class="admin-alert admin-alert-success admin-text-center">
                  <i class="bi-check-circle"></i>
                  Operation has been scheduled.
              </div>
              <div class="admin-card">
                  <div class="admin-card-body">
                      <form class="admin-shift-form">
                          <div x-cloak x-show="!validPath" class="admin-alert admin-alert-danger">
                              Invalid file path
                          </div>
                          <div class="admin-form-group">
                              <label for="baseInputShift" class="admin-label">File path:</label>
                              <input id="baseInputShift" class="admin-input" type="text" x-model="base"
                                     @input="await handleInput()"
                                     @keyup="await handleKeyUp($event)"
                                     list="baseSuggestionsShift"
                                     placeholder="Enter file path">
                              <datalist id="baseSuggestionsShift">
                                  <template x-for="dir in directories" :key="dir">
                                      <option x-bind:value="dir"></option>
                                  </template>
                                  <template x-for="file in files" :key="file">
                                      <option x-bind:value="file"></option>
                                  </template>
                              </datalist>
                          </div>
                          <div x-cloak x-show="base.endsWith('.json')" class="admin-form-row admin-mt-2">
                              <div class="admin-form-group">
                                  <div class="admin-checkbox-group">
                                      <input type="checkbox" id="exact" x-model="exact" class="admin-checkbox">
                                      <label for="exact" class="admin-label" style="margin-bottom: 0;">Exact Match</label>
                                  </div>
                              </div>
                              <div class="admin-form-group">
                                  <label for="shiftInput" class="admin-label">Segment ID:</label>
                                  <input id="shiftInput" class="admin-input" x-model="segment"
                                         list="shiftSuggestions"
                                         @keyup.enter="addSegment(segment)"
                                         placeholder="Enter segment ID">
                                  <datalist id="shiftSuggestions">
                                      <template x-for="id in segmentIDs" :key="id">
                                          <option x-bind:value="id" x-show="!selectedIDs.includes(id)"></option>
                                      </template>
                                  </datalist>
                              </div>
                          </div>
                          <div x-cloak x-show="segmentIDs && segmentIDs.length > 0" class="admin-flex-between admin-mt-2">
                              <ul class="admin-tag-list">
                                  <template x-for="id in selectedIDs" :key="id">
                                      <li class="admin-tag" x-text="id" @click="removeSegment(id)"></li>
                                  </template>
                              </ul>
                              <button @click="await handleSubmit(true)" class="btn admin-btn admin-btn-primary"
                                      :disabled="!selectedIDs.length > 0">
                                  <i class="bi-arrows-expand"></i> Shift
                              </button>
                          </div>
                      </form>
                  </div>
              </div>
              <!-- Shift Preview -->
              <div x-cloak x-show="data && data.length > 0" class="admin-mt-3" x-data="{modal: false}">
                  <div class="admin-card admin-mb-2">
                      <div class="admin-card-header">
                          <h3 class="admin-card-title">Review Changes</h3>
                      </div>
                      <div class="admin-card-body admin-text-center">
                          <p>The following files will be modified:</p>
                      </div>
                  </div>
                  <div class="admin-shift-preview">
                      <template x-for="(item, index) in data" :key="item.path">
                          <div class="admin-shift-item">
                              <div class="admin-shift-item-header">
                                  <a target="_blank" class="admin-project-tag"
                                     :href="window.location.href.replace('/admin', '') + '/translation?prefix=' + item.prefix + '&muid=' + item.muid + '&source=' + item.source_muid"
                                     x-text="item.filename" style="color: var(--admin-accent);"></a>
                                  <span class="admin-badge admin-badge-role" x-text="item.muid"></span>
                                  <span class="admin-badge" x-text="item.prefix"></span>
                                  <span class="admin-badge" x-text="item.language"></span>
                              </div>
                              <div class="admin-shift-compare">
                                  <div class="admin-shift-column" x-data="adjust()">
                                      <h4>Before</h4>
                                      <template x-for="(segment, segmentID) in item.data_before" :key="item.path+segmentID">
                                          <template x-if="shouldDisplay(index, segmentID)">
                                              <div class="admin-shift-segment">
                                                  <label x-text="segmentID"></label>
                                                  <textarea x-bind:value="segment" disabled></textarea>
                                              </div>
                                          </template>
                                      </template>
                                  </div>
                                  <div class="admin-shift-column">
                                      <h4>After</h4>
                                      <template x-for="(segment, segmentID) in item.data_before" :key="item.path+segmentID+'after'">
                                          <template x-if="shouldDisplay(index, segmentID)">
                                              <div class="admin-shift-segment">
                                                  <label x-text="segmentID"
                                                         :class="{'admin-shift-removed': !(segmentID in item.data_after),
                                                                  'admin-shift-changed': item.data_before[segmentID] !== item.data_after[segmentID]}"></label>
                                                  <textarea x-bind:value="item.data_after[segmentID]"
                                                            x-show="segmentID in item.data_after" disabled
                                                            :class="{'admin-shift-changed': item.data_before[segmentID] !== item.data_after[segmentID]}"></textarea>
                                                  <p x-show="!(segmentID in item.data_after)" class="admin-shift-removed admin-text-center">
                                                      Data no longer available
                                                  </p>
                                              </div>
                                          </template>
                                      </template>
                                  </div>
                              </div>
                          </div>
                      </template>
                  </div>
                  <div class="admin-form-actions admin-mt-2">
                      <button @click.prevent="modal = !modal" class="btn admin-btn admin-btn-danger">
                          <i class="bi-arrows-expand"></i> Apply Shift
                      </button>
                  </div>
                  <!-- Confirm Modal -->
                  <div x-cloak x-show="modal" class="admin-modal-overlay" @click="modal = !modal">
                      <div class="admin-modal" @click.stop>
                          <div class="admin-modal-header">
                              <div class="admin-modal-icon admin-modal-icon-warning">
                                  <i class="bi-exclamation-triangle"></i>
                              </div>
                              <div>
                                  <h2 class="admin-modal-title">Confirm Shift</h2>
                                  <p class="admin-modal-subtitle">Are you sure you want to apply changes to all files?</p>
                              </div>
                          </div>
                          <div class="admin-modal-footer">
                              <button @click.prevent="modal = !modal" class="btn admin-btn admin-btn-secondary">No</button>
                              <button @click.prevent="modal = !modal; await handleSubmit(false)"
                                      class="btn admin-btn admin-btn-danger">Yes, Apply</button>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
        `;
    }
}

customElements.define('sc-bilara-admin-shift', ScBilaraAdminShift);
