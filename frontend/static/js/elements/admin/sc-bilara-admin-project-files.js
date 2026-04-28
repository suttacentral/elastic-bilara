import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminProjectFiles extends LitElement {

    // Render into light DOM so Alpine.js directives work
    createRenderRoot() {
        return this;
    }

    render() {
        return html`
              <!-- ===== Toggle Buttons for Add / Remove Files ===== -->
              <div class="admin-projects-toggle" role="tablist" aria-label="Project actions">
                  <button x-on:click="toggleAdd()"
                          class="btn admin-btn"
                          :class="showAdd ? 'admin-btn-primary admin-project-toggle-active' : 'admin-btn-secondary'"
                          :aria-pressed="showAdd.toString()">
                      <i class="bi-plus-circle"></i> Add Project Files
                  </button>
                  <button x-on:click="toggleRemove()"
                          class="btn admin-btn admin-project-remove-btn"
                          :class="showRemove ? 'admin-btn-danger admin-project-toggle-active' : 'admin-btn-secondary'"
                          :aria-pressed="showRemove.toString()">
                      <i class="bi-trash"></i> Remove Project Files
                  </button>
              </div>
              <!-- Add Project Form -->
              <div x-cloak x-show="showAdd" x-data="addNewProject()">
                  <div x-cloak x-show="loading" class="admin-loading">
                      <div class="admin-progress-panel" role="status" aria-live="polite">
                          <p class="admin-progress-title" x-text="progress.phase === 'committing' ? 'Committing files…' : progress.phase === 'indexing' ? 'Indexing files…' : 'Creating project files…'"></p>
                          <div class="admin-progress-bar-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="progress.phase === 'committing' || progress.phase === 'indexing' ? undefined : (progress.total > 0 ? Math.round(progress.current / progress.total * 100) : 0)">
                              <div x-show="progress.phase !== 'indexing' && progress.phase !== 'committing'"
                                   class="admin-progress-bar-fill"
                                   x-bind:style="'width: ' + (progress.total > 0 ? Math.round(progress.current / progress.total * 100) : 0) + '%'"></div>
                              <div x-show="progress.phase === 'indexing' || progress.phase === 'committing'"
                                   class="admin-progress-bar-indeterminate"></div>
                          </div>
                          <p class="admin-progress-info">
                              <span x-show="progress.phase !== 'indexing' && progress.phase !== 'committing'">
                                  <span x-show="progress.total > 0"
                                        x-text="progress.current + ' / ' + progress.total + ' (' + Math.round(progress.current / progress.total * 100) + '%)'"></span>
                                  <span x-show="progress.total === 0">Preparing…</span>
                              </span>
                              <span x-show="progress.phase === 'committing' || progress.phase === 'indexing'"
                                     x-text="'Elapsed ' + (elapsedSeconds >= 60 ? Math.floor(elapsedSeconds / 60) + 'm ' + (elapsedSeconds % 60) + 's' : elapsedSeconds + 's')"></span>
                          </p>
                      </div>
                  </div>
                  <div x-cloak x-show="invalidData" class="admin-alert admin-alert-danger admin-text-center">
                      <i class="bi-exclamation-circle"></i>
                      <span x-text="errorMessage || 'The form contains invalid data.'"></span>
                  </div>
                  <div class="admin-card admin-project-card">
                      <div class="admin-card-header admin-project-card-header">
                          <h3 class="admin-card-title">Create Project Files</h3>
                          <p class="admin-text-muted">Select a root, assignee, and language to scaffold translation files.</p>
                      </div>
                      <div class="admin-card-body">
                          <form class="admin-project-form">
                              <div class="admin-form-group">
                                  <label class="admin-label" for="projectNameInput">Project name:</label>
                                  <input id="projectNameInput" class="admin-input" type="text" x-model="projectName"
                                         placeholder="Enter project name">
                              </div>
                              <div class="admin-form-group">
                                  <label class="admin-label" for="baseInputAddProjects">Root path:</label>
                                  <input id="baseInputAddProjects" class="admin-input" type="text" x-model="base"
                                         @input="await handleInput()"
                                         @keyup="await handleKeyUp($event)"
                                         list="baseSuggestionsAddProjects"
                                         placeholder="Enter root path">
                                  <datalist id="baseSuggestionsAddProjects">
                                      <template x-for="dir in directories" :key="dir">
                                          <option x-bind:value="dir"></option>
                                      </template>
                                      <template x-for="file in files" :key="file">
                                          <option x-bind:value="file"></option>
                                      </template>
                                  </datalist>
                              </div>
                              <div class="admin-form-group">
                                  <label class="admin-label" for="userProjects">User:</label>
                                  <select id="userProjects" x-model="user" class="admin-select">
                                      <option value="">Select a user...</option>
                                      <template x-for="user in users">
                                          <option x-text="user.username" :value="user.github_id"></option>
                                      </template>
                                  </select>
                              </div>
                              <div class="admin-form-group">
                                  <div x-cloak x-show="!validLanguageCode" class="admin-alert admin-alert-danger">
                                      Please select a language.
                                  </div>
                                  <label class="admin-label" for="languageProjects">Language:</label>
                                  <select id="languageProjects" x-model="languageCode" class="admin-select" @change="checkLanguageCode()">
                                      <option value="">Select a language...</option>
                                      <template x-for="(lang, code) in languages" :key="code">
                                          <option x-text="\`\${code} - \${lang.name}\`" :value="code"></option>
                                      </template>
                                  </select>
                              </div>
                              <div class="admin-form-actions">
                                  <button @click.prevent="await handleSubmit()" class="btn admin-btn admin-btn-primary">
                                      <i class="bi-plus-circle"></i> Create
                                  </button>
                              </div>
                          </form>
                      </div>
                  </div>
                  <div x-cloak x-show="created.status" class="admin-card admin-project-created admin-mt-2">
                      <div class="admin-card-header admin-project-created-header">
                          <h3 class="admin-card-title">Files Created</h3>
                          <span class="admin-badge admin-badge-active" x-text="created.paths.length + ' files'"></span>
                      </div>
                      <div class="admin-card-body">
                          <p class="admin-mb-2">Generated for user <strong x-text="created.username"></strong>.</p>
                          <ol class="admin-created-path-list">
                              <template x-for="(path, index) in created.paths" :key="path">
                                  <li class="admin-created-path-item">
                                      <span class="admin-created-index" x-text="index + 1"></span>
                                      <code class="admin-created-path" x-text="path"></code>
                                  </li>
                              </template>
                          </ol>
                      </div>
                  </div>
              </div>
              <!-- Remove Project Form -->
              <div x-cloak x-show="showRemove" x-data="removeProject()">
                  <div x-cloak x-show="loading" class="admin-loading">
                      <div class="admin-spinner"></div>
                  </div>
                  <div class="admin-card admin-project-card">
                      <div class="admin-card-header admin-project-card-header">
                          <h3 class="admin-card-title">Delete Project Files</h3>
                          <p class="admin-text-muted">Preview impacted files first, then confirm deletion.</p>
                      </div>
                      <div class="admin-card-body">
                          <form class="admin-project-form">
                              <div x-cloak x-show="!validPath" class="admin-alert admin-alert-danger">
                                  Invalid file path
                              </div>
                              <div class="admin-form-group">
                                  <label class="admin-label" for="baseInputRemoveProjects">File path:</label>
                                  <input id="baseInputRemoveProjects" class="admin-input" type="text" x-model="base"
                                         @input="await handleInput()"
                                         @keyup="await handleKeyUp($event)"
                                         list="baseSuggestionsRemoveProjects"
                                         placeholder="Enter file path to remove">
                                  <datalist id="baseSuggestionsRemoveProjects">
                                      <template x-for="dir in directories" :key="dir">
                                          <option x-bind:value="dir"></option>
                                      </template>
                                      <template x-for="file in files" :key="file">
                                          <option x-bind:value="file"></option>
                                      </template>
                                  </datalist>
                              </div>
                              <div class="admin-form-actions">
                                  <button @click.prevent="await handleSubmit(true)"
                                          class="btn admin-btn admin-btn-danger" x-bind:disabled="!validPath">
                                      <i class="bi-trash"></i> Delete
                                  </button>
                              </div>
                          </form>
                      </div>
                  </div>
                  <div x-cloak x-show="message" class="admin-alert admin-alert-success admin-mt-2 admin-text-center">
                      <i class="bi-check-circle"></i>
                      Deletion has been scheduled.
                  </div>
                  <!-- Preview Data -->
                  <div x-cloak x-show="data && data.length > 0" x-data="{modal: false}" class="admin-mt-3">
                      <div class="admin-card admin-project-review-card">
                          <div class="admin-card-header admin-project-review-header">
                              <h3 class="admin-card-title">Review Files to Delete</h3>
                              <span class="admin-badge admin-badge-inactive" x-text="data.length + ' items'"></span>
                          </div>
                          <div class="admin-card-body">
                              <p class="admin-text-center admin-mb-2">You are about to delete the following files and directories:</p>
                              <ul class="admin-project-list">
                                  <template x-for="item in data" :key="item.path">
                                      <li x-data="tooltip()" class="admin-project-item admin-project-item-review">
                                          <div class="admin-project-path-wrap">
                                              <span class="admin-project-tag admin-project-path" x-text="item.path"
                                                    @mouseover="await fetchData(item.path)"
                                                    @mouseleave="hide()"></span>
                                              <div x-cloak x-show="show" class="admin-tooltip"
                                                   @mouseover="await fetchData(item.path)"
                                                   @mouseleave="hide()">
                                                  <ul>
                                                      <template x-for="file in tooltipData" :key="file">
                                                          <li x-text="file"></li>
                                                      </template>
                                                  </ul>
                                              </div>
                                          </div>
                                          <div class="admin-project-meta">
                                              <span class="admin-badge admin-badge-role" x-text="item.muid"></span>
                                              <span class="admin-badge" x-text="item.language"></span>
                                          </div>
                                      </li>
                                  </template>
                              </ul>
                              <div class="admin-form-actions admin-mt-2">
                                  <button @click.prevent="modal = !modal" class="btn admin-btn admin-btn-danger">
                                      <i class="bi-trash"></i> Confirm Delete
                                  </button>
                              </div>
                          </div>
                      </div>

                      <div x-cloak x-show="modal" class="admin-modal-overlay" @click="modal = !modal">
                          <div class="admin-modal" @click.stop>
                              <div class="admin-modal-header">
                                  <div class="admin-modal-icon admin-modal-icon-danger">
                                      <i class="bi-exclamation-triangle"></i>
                                  </div>
                                  <div>
                                      <h2 class="admin-modal-title">Confirm Deletion</h2>
                                      <p class="admin-modal-subtitle">Are you sure you want to delete these files?</p>
                                  </div>
                              </div>
                              <div class="admin-modal-footer">
                                  <button @click.prevent="modal = !modal" class="btn admin-btn admin-btn-secondary">No</button>
                                  <button @click.prevent="await handleSubmit(false); modal = !modal"
                                          class="btn admin-btn admin-btn-danger">Yes, Delete</button>
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
        `;
    }
}

customElements.define('sc-bilara-admin-project-files', ScBilaraAdminProjectFiles);
