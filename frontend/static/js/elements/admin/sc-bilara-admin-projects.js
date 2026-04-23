import { LitElement, html } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';
import './sc-bilara-admin-project-files.js';

export class ScBilaraAdminProjects extends LitElement {

    // Render into light DOM so Alpine.js directives work
    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="dataTypes.projects">
              <div class="admin-section-header">
                  <h1 class="admin-section-title">Project Management</h1>
              </div>
              <div class="admin-projects-shell">

              <!-- ===== Project List ===== -->
              <div x-data="projectsListManager()" x-init="await init()">

                  <div x-cloak x-show="toast.show"
                      x-transition:enter="transition ease-out duration-300"
                      x-transition:leave="transition ease-in duration-200"
                      class="pub-toast"
                      :class="toast.type === 'success' ? 'pub-toast-success' : 'pub-toast-error'"
                      x-text="toast.message">
                  </div>

                  <!-- List View -->
                  <div>
                      <div class="pub-header">
                          <h2 class="pub-title"></h2>
                          <div style="display:flex;gap:.5rem">
                              <button class="pub-btn pub-btn-primary" @click="showFileManager = true">
                                  <i class="bi-folder-plus"></i> Manage Files
                              </button>
                              <button class="pub-btn pub-btn-primary" @click="showCreateForm()">
                                  <i class="bi-plus-lg"></i> New Entry
                              </button>
                              <button class="pub-btn" style="background:#2ea44f;color:#fff" @click="await publishToGitHub()" :disabled="publishing">
                                  <i class="bi-github"></i>
                                  <span x-text="publishing ? 'Publishing\u2026' : 'Publish to GitHub'"></span>
                              </button>
                          </div>
                      </div>

                      <div class="pub-stats">
                          <span>Total: <span class="pub-stat-value" x-text="entries.length"></span></span>
                          <span>Showing: <span class="pub-stat-value" x-text="filteredEntries.length"></span></span>
                      </div>

                      <div class="pub-toolbar">
                          <input type="text"
                                class="pub-search"
                                placeholder="Search by UID, name, creator..."
                                x-model.debounce.300ms="searchQuery">
                          <select class="pub-filter" x-model="filterLang">
                              <option value="">All Languages</option>
                              <template x-for="lang in uniqueLanguages" :key="lang">
                                  <option :value="lang" x-text="lang"></option>
                              </template>
                          </select>
                      </div>

                      <div x-cloak x-show="loading" class="pub-loading">
                          <div class="spinner"></div>
                      </div>

                      <div x-cloak x-show="!loading && filteredEntries.length > 0" class="pub-table-wrap">
                          <table class="pub-table">
                              <thead>
                                  <tr>
                                      <th @click="toggleSort('project_uid')">
                                          Project UID <i :class="sortIcon('project_uid')"></i>
                                      </th>
                                      <th @click="toggleSort('name')">
                                          Name <i :class="sortIcon('name')"></i>
                                      </th>
                                      <th @click="toggleSort('root_path')">
                                          Root Path <i :class="sortIcon('root_path')"></i>
                                      </th>
                                      <th @click="toggleSort('translation_path')">
                                          Translation Path <i :class="sortIcon('translation_path')"></i>
                                      </th>
                                      <th @click="toggleSort('translation_muids')">
                                          Translation MUIDs <i :class="sortIcon('translation_muids')"></i>
                                      </th>
                                      <th @click="toggleSort('creator_github_handle')">
                                          Creator <i :class="sortIcon('creator_github_handle')"></i>
                                      </th>
                                      <th>Actions</th>
                                  </tr>
                              </thead>
                              <tbody>
                                  <template x-for="entry in filteredEntries" :key="entry.project_uid">
                                      <tr>
                                          <td><span class="pub-badge pub-badge-lang" x-text="entry.project_uid"></span></td>
                                          <td x-text="entry.name || '\u2014'"></td>
                                          <td x-text="entry.root_path || '\u2014'"></td>
                                          <td x-text="entry.translation_path || '\u2014'"></td>
                                          <td x-text="entry.translation_muids || '\u2014'"></td>
                                          <td x-text="entry.creator_github_handle || '\u2014'"></td>
                                          <td>
                                              <div class="pub-actions">
                                                  <button class="pub-btn pub-btn-sm" @click="showEditForm(entry)" title="Edit">
                                                      <i class="bi-pencil"></i>
                                                  </button>
                                                  <button class="pub-btn pub-btn-sm pub-btn-danger"
                                                          @click="await deleteEntry(entry.project_uid)"
                                                          title="Delete">
                                                      <i class="bi-trash"></i>
                                                  </button>
                                              </div>
                                          </td>
                                      </tr>
                                  </template>
                              </tbody>
                          </table>
                      </div>

                      <div x-cloak x-show="!loading && filteredEntries.length === 0" class="pub-empty">
                          <div><i class="bi-journal-x"></i></div>
                          <p>No project entries found.</p>
                      </div>
                  </div>

                  <!-- Edit / Create Form Modal -->
                  <div x-cloak x-show="view === 'form'" class="admin-modal-overlay" @click="cancelForm()"
                       x-transition:enter="transition ease-out duration-200"
                       x-transition:leave="transition ease-in duration-150">
                      <div class="admin-modal" @click.stop style="max-width:760px;width:92%">
                          <div class="admin-modal-header">
                              <div>
                                  <h2 class="admin-modal-title" x-text="editingEntry ? 'Edit Project Entry' : 'New Project Entry'"></h2>
                              </div>
                              <button @click="cancelForm()" style="background:none;border:none;font-size:1.5rem;line-height:1;cursor:pointer;padding:0;color:inherit;">
                                  <i class="bi-x-lg"></i>
                              </button>
                          </div>

                          <div style="padding:1rem 1.5rem;max-height:70vh;overflow-y:auto">
                              <form @submit.prevent="await submitForm()">
                                  <div class="pub-form-section" style="border:none;margin:0;padding:0;background:transparent;box-shadow:none;">
                                      <div class="pub-form-section-body" style="padding:0;">
                                          <div class="pub-form-row">
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Project UID *</label>
                                                  <input type="text" class="pub-form-input"
                                                        :class="formErrors.project_uid ? 'pub-form-input-error' : ''"
                                                        x-model="form.project_uid"
                                                        placeholder="e.g. ca_ms_translation_bernatfontclos"
                                                        :readonly="!!editingEntry">
                                                  <div x-show="formErrors.project_uid" class="pub-form-error-text"
                                                      x-text="formErrors.project_uid"></div>
                                              </div>
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Name</label>
                                                  <input type="text" class="pub-form-input"
                                                        x-model="form.name"
                                                        placeholder="e.g. Català sutta translation">
                                              </div>
                                          </div>
                                          <div class="pub-form-row">
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Root Path</label>
                                                  <input type="text" class="pub-form-input"
                                                        x-model="form.root_path"
                                                        placeholder="e.g. root/pli/ms/sutta">
                                              </div>
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Translation Path</label>
                                                  <input type="text" class="pub-form-input"
                                                        x-model="form.translation_path"
                                                        placeholder="e.g. translation/ca/bernatfontclos/sutta">
                                              </div>
                                          </div>
                                          <div class="pub-form-row">
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Translation MUIDs</label>
                                                  <input type="text" class="pub-form-input"
                                                        x-model="form.translation_muids"
                                                        placeholder="e.g. translation-ca-bernatfontclos">
                                              </div>
                                              <div class="pub-form-group">
                                                  <label class="pub-form-label">Creator GitHub Handle</label>
                                                  <input type="text" class="pub-form-input"
                                                        x-model="form.creator_github_handle"
                                                        placeholder="e.g. BernatFontClos">
                                              </div>
                                          </div>
                                      </div>
                                  </div>

                                  <div class="pub-form-actions" style="margin-top:1.5rem;padding:0;border-top:none;background:transparent;">
                                      <button type="button" class="pub-btn" @click="cancelForm()">Cancel</button>
                                      <button type="submit" class="pub-btn pub-btn-primary" :disabled="saving">
                                          <template x-if="saving"><span>Saving...</span></template>
                                          <template x-if="!saving">
                                              <span x-text="editingEntry ? 'Update Entry' : 'Create Entry'"></span>
                                          </template>
                                      </button>
                                  </div>
                              </form>
                          </div>
                      </div>
                  </div>
              </div>

              <!-- Modal: Manage Project Files -->
              <div x-cloak x-show="showFileManager" class="admin-modal-overlay" @click="showFileManager = false"
                   x-transition:enter="transition ease-out duration-200"
                   x-transition:leave="transition ease-in duration-150">
                  <div class="admin-modal" @click.stop style="max-width:760px;width:92%">
                      <div class="admin-modal-header">
                          <div>
                              <h2 class="admin-modal-title">Manage Project Files</h2>
                              <p class="admin-modal-subtitle">Add or remove translation project files.</p>
                          </div>
                      </div>
                      <div style="padding:1rem 1.5rem;max-height:70vh;overflow-y:auto">
                          <sc-bilara-admin-project-files></sc-bilara-admin-project-files>
                      </div>
                      <div class="admin-modal-footer">
                          <button @click="showFileManager = false" class="btn admin-btn admin-btn-secondary">Close</button>
                      </div>
                  </div>
              </div>
              </div>
          </div>
        `;
    }
}

customElements.define('sc-bilara-admin-projects', ScBilaraAdminProjects);
