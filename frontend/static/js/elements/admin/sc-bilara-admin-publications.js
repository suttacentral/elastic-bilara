import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraAdminPublications extends LitElement {

    // Render into light DOM so Alpine.js directives work
    createRenderRoot() {
        return this;
    }

    render() {
        return html`
          <div x-data="publicationsManager()" x-init="isAdmin = true; await init()">

              <div x-cloak x-show="toast.show"
                  x-transition:enter="transition ease-out duration-300"
                  x-transition:leave="transition ease-in duration-200"
                  class="pub-toast"
                  :class="toast.type === 'success' ? 'pub-toast-success' : 'pub-toast-error'"
                  x-text="toast.message">
              </div>

              <div>
                  <div class="pub-header">
                      <h1 class="pub-title">Publication Metadata</h1>
                      <div style="display:flex;gap:.5rem">
                          <button class="pub-btn pub-btn-primary" @click="await showCreateForm()" x-show="isAdmin">
                              <i class="bi-plus-lg"></i> New Publication
                          </button>
                          <button class="pub-btn" style="background:#2ea44f;color:#fff" @click="await publishToGitHub()" x-show="isAdmin" :disabled="publishing">
                              <i class="bi-github"></i>
                              <span x-text="publishing ? 'Publishing\u2026' : 'Publish to GitHub'"></span>
                          </button>
                      </div>
                  </div>

                  <div class="pub-stats">
                      <span>Total: <span class="pub-stat-value" x-text="publications.length"></span></span>
                      <span>Published: <span class="pub-stat-value" x-text="publications.filter(p => p.is_published).length"></span></span>
                      <span>Unpublished: <span class="pub-stat-value" x-text="publications.filter(p => !p.is_published).length"></span></span>
                      <span>Showing: <span class="pub-stat-value" x-text="filteredPublications.length"></span></span>
                  </div>

                  <div class="pub-toolbar">
                      <input type="text"
                            class="pub-search"
                            placeholder="Search by number, title, author, language..."
                            x-model.debounce.300ms="searchQuery">

                      <select class="pub-filter" x-model="filterLang">
                          <option value="">All Languages</option>
                          <template x-for="lang in uniqueLanguages" :key="lang">
                              <option :value="lang" x-text="lang"></option>
                          </template>
                      </select>

                      <select class="pub-filter" x-model="filterPublished">
                          <option value="">All Status</option>
                          <option value="true">Published</option>
                          <option value="false">Unpublished</option>
                      </select>
                  </div>

                  <div x-cloak x-show="loading" class="pub-loading">
                      <div class="spinner"></div>
                  </div>

                  <div x-cloak x-show="!loading && filteredPublications.length > 0" class="pub-table-wrap">
                      <table class="pub-table">
                          <thead>
                              <tr>
                                  <th @click="toggleSort('publication_number')">
                                      # <i :class="sortIcon('publication_number')"></i>
                                  </th>
                                  <th @click="toggleSort('translation_lang_iso')">
                                      Lang <i :class="sortIcon('translation_lang_iso')"></i>
                                  </th>
                                  <th @click="toggleSort('creator_uid')">
                                      Creator <i :class="sortIcon('creator_uid')"></i>
                                  </th>
                                  <th @click="toggleSort('text_uid')">
                                      Text UID <i :class="sortIcon('text_uid')"></i>
                                  </th>
                                  <th @click="toggleSort('translation_title')">
                                      Title <i :class="sortIcon('translation_title')"></i>
                                  </th>
                                  <th @click="toggleSort('is_published')">
                                      Status <i :class="sortIcon('is_published')"></i>
                                  </th>
                                  <th>Actions</th>
                              </tr>
                          </thead>
                          <tbody>
                              <template x-for="pub in filteredPublications" :key="pub.publication_number">
                                  <tr>
                                      <td>
                                          <span class="pub-badge pub-badge-lang" x-text="pub.publication_number"></span>
                                      </td>
                                      <td>
                                          <span x-text="pub.translation_lang_name || pub.translation_lang_iso"></span>
                                          <span style="opacity:0.5" x-show="pub.translation_lang_iso" x-text="'(' + pub.translation_lang_iso + ')'"></span>
                                      </td>
                                      <td>
                                          <span x-text="pub.creator_name || pub.creator_uid"></span>
                                      </td>
                                      <td x-text="pub.text_uid || '\u2014'"></td>
                                      <td>
                                          <span x-text="pub.translation_title || '\u2014'"></span>
                                      </td>
                                      <td>
                                          <span class="pub-badge"
                                                :class="pub.is_published ? 'pub-badge-published' : 'pub-badge-unpublished'"
                                                x-text="pub.is_published ? 'Published' : 'Unpublished'">
                                          </span>
                                      </td>
                                      <td>
                                          <div class="pub-actions">
                                              <button class="pub-btn pub-btn-sm"
                                                      @click="showEditForm(pub)"
                                                      title="Edit">
                                                  <i class="bi-pencil"></i>
                                              </button>
                                              <button class="pub-btn pub-btn-sm pub-btn-danger"
                                                      @click="await deletePub(pub.publication_number)"
                                                      x-show="isAdmin"
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

                  <div x-cloak x-show="!loading && filteredPublications.length === 0" class="pub-empty">
                      <div><i class="bi-journal-x"></i></div>
                      <p>No publications found.</p>
                  </div>
              </div>

              <!-- Edit / Create Form Modal -->
              <div x-cloak x-show="view === 'form'" class="admin-modal-overlay" @click="cancelForm()"
                   x-transition:enter="transition ease-out duration-200"
                   x-transition:leave="transition ease-in duration-150">
                  <div class="admin-modal" @click.stop style="max-width:860px;width:92%">
                      <div class="admin-modal-header">
                          <div>
                              <h2 class="admin-modal-title" x-text="editingPub ? 'Edit Publication' : 'New Publication'"></h2>
                          </div>
                          <button @click="cancelForm()" style="background:none;border:none;font-size:1.5rem;line-height:1;cursor:pointer;padding:0;color:inherit;">
                              <i class="bi-x-lg"></i>
                          </button>
                      </div>

                      <div style="padding:1rem 1.5rem;max-height:75vh;overflow-y:auto">
                          <form @submit.prevent="await submitForm()">

                      <!-- Basic Info -->
                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-info-circle"></i> Basic Information
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Publication Number *</label>
                                      <input type="text" class="pub-form-input"
                                            :class="formErrors.publication_number ? 'pub-form-input-error' : ''"
                                            x-model="form.publication_number"
                                            placeholder="e.g. scpub104"
                                            :readonly="!!editingPub">
                                      <div x-show="formErrors.publication_number" class="pub-form-error-text"
                                          x-text="formErrors.publication_number"></div>
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Text UID</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.text_uid"
                                            placeholder="e.g. thag, dn, mn">
                                  </div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Root Language ISO</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.root_lang_iso"
                                            placeholder="e.g. pli">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Root Language Name</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.root_lang_name"
                                            placeholder="e.g. Pali">
                                  </div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Translation Language ISO</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.translation_lang_iso"
                                            placeholder="e.g. en, it, zh"
                                            @change="autoGenerateSourceUrl()">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Translation Language Name</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.translation_lang_name"
                                            placeholder="e.g. English, Italiano">
                                  </div>
                              </div>
                          </div>
                      </div>

                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-person"></i> Creator Information
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Creator UID</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.creator_uid"
                                            placeholder="e.g. sujato"
                                            @change="autoGenerateSourceUrl()">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Creator Name</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.creator_name"
                                            placeholder="e.g. Bhikkhu Sujato">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">GitHub Handle</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.creator_github_handle"
                                            placeholder="e.g. sujato">
                                  </div>
                              </div>
                          </div>
                      </div>

                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-translate"></i> Translation Details
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Translation Title</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.translation_title"
                                            placeholder="Translation title">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Translation Subtitle</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.translation_subtitle"
                                            placeholder="Subtitle">
                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">Root Title</label>
                                  <input type="text" class="pub-form-input"
                                        x-model="form.root_title"
                                        placeholder="e.g. Therag\u0101th\u0101">
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">Creation Process</label>
                                  <textarea class="pub-form-textarea"
                                            x-model="form.creation_process"
                                            placeholder="Describe the translation process..."></textarea>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">Text Description</label>
                                  <textarea class="pub-form-textarea"
                                            x-model="form.text_description"
                                            placeholder="Describe the text..."></textarea>
                              </div>
                          </div>
                      </div>

                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-globe"></i> Publishing &amp; URLs
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-group">
                                  <label class="pub-form-label">Source URL</label>
                                  <input type="text" class="pub-form-input"
                                        x-model="form.source_url"
                                        placeholder="https://github.com/suttacentral/bilara-data/tree/published/...">
                                  <div class="pub-form-hint">Auto-generated from creator UID and language ISO</div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Publication Status</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.publication_status"
                                            placeholder="e.g. Completed, In progress">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">First Published</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.first_published"
                                            placeholder="e.g. 2024">
                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">Editions URL</label>
                                  <input type="text" class="pub-form-input"
                                        x-model="form.editions_url"
                                        placeholder="e.g. https://suttacentral.net/thag">
                              </div>

                              <div class="pub-form-checkbox-group">
                                  <input type="checkbox" class="pub-form-checkbox"
                                        x-model="form.is_published">
                                  <label>Is Published</label>
                              </div>
                          </div>
                      </div>

                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-shield-check"></i> License
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">License Type</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.license_type"
                                            placeholder="Creative Commons Zero">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">License Abbreviation</label>
                                      <input type="text" class="pub-form-input"
                                            x-model="form.license_abbreviation"
                                            placeholder="CC0">
                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">License URL</label>
                                  <input type="text" class="pub-form-input"
                                        x-model="form.license_url"
                                        placeholder="https://creativecommons.org/publicdomain/zero/1.0/">
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label">License Statement</label>
                                  <textarea class="pub-form-textarea"
                                            x-model="form.license_statement"
                                            placeholder="License statement text..."></textarea>
                              </div>
                          </div>
                      </div>



                      <div class="pub-form-actions" style="margin-top:1.5rem;padding:0;border-top:none;background:transparent;">
                          <button type="button" class="pub-btn" @click="cancelForm()">Cancel</button>
                          <button type="submit" class="pub-btn pub-btn-primary" :disabled="saving">
                              <template x-if="saving"><span>Saving...</span></template>
                              <template x-if="!saving">
                                  <span x-text="editingPub ? 'Update Publication' : 'Create Publication'"></span>
                              </template>
                          </button>
                      </div>
                          </form>
                      </div>
                  </div>
              </div>

          </div>
        `;
    }
}

customElements.define('sc-bilara-admin-publications', ScBilaraAdminPublications);
