import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ScBilaraPublications extends LitElement {

    // Render into light DOM so Alpine.js directives work
    createRenderRoot() {
        return this;
    }

    get adminPage() { return false; }

    render() {
        return html`
          <div x-data=${`publicationsManager(${this.adminPage})`}>

              <div x-cloak x-show="toast.show"
                  role="status" class="pub-toast"
                  :class="toast.type === 'success' ? 'pub-toast-success' : 'pub-toast-error'"
                  x-text="toast.message">
              </div>

              <div>
                  <div class="pub-header">
                      <h1 class="pub-title" x-text="isAdmin ? 'Publication Metadata' : 'My Publication Information'"></h1>
                      <div style="display:flex;gap:.5rem">
                          <button class="pub-btn pub-btn-primary" @click="await showCreateForm()" x-show="isAdmin">
                              <i class="bi-plus-lg"></i> New Publication
                          </button>
                          <button class="pub-btn" @click="await publishToGitHub()" x-show="isAdmin" :disabled="publishing">
                              <i class="bi-github"></i>
                              <span x-text="publishing ? 'Publishing\u2026' : 'Publish to GitHub'"></span>
                          </button>
                      </div>
                  </div>

                  <p x-cloak x-show="loadError" x-text="loadError" role="alert" class="pub-form-error-text"></p>
                  <div x-cloak x-show="publishTaskId" class="pub-publish-status" role="status">
                      <span x-text="publishStatus"></span>
                      <button class="pub-btn pub-btn-sm" @click="await checkPublishStatus()">Check status</button>
                  </div>
                  <div class="pub-stats" x-show="authorized">
                      <span>Total: <span class="pub-stat-value" x-text="publications.length"></span></span>
                      <span>Published: <span class="pub-stat-value" x-text="publications.filter(p => p.is_published).length"></span></span>
                      <span>Unpublished: <span class="pub-stat-value" x-text="publications.filter(p => !p.is_published).length"></span></span>
                      <span>Showing: <span class="pub-stat-value" x-text="filteredPublications.length"></span></span>
                  </div>

                  <div class="pub-toolbar" x-show="authorized">
                      <input type="text"
                            class="pub-search"
                            aria-label="Search publications" placeholder="Search by number, title, author, language..."
                            x-model.debounce.300ms="searchQuery">

                      <select class="pub-filter" aria-label="Filter by language" x-model="filterLang">
                          <option value="">All Languages</option>
                          <template x-for="lang in uniqueLanguages" :key="lang">
                              <option :value="lang" x-text="lang"></option>
                          </template>
                      </select>

                      <select class="pub-filter" aria-label="Filter by status" x-model="filterPublished">
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
                                                      @click="await showEditForm(pub)" :disabled="loadingDetail"
                                                      title="Edit" aria-label="Edit publication">
                                                  <i class="bi-pencil"></i>
                                              </button>
                                              <button class="pub-btn pub-btn-sm pub-btn-danger"
                                                      @click="await deletePub(pub.publication_number)"
                                                      x-show="isAdmin"
                                                      title="Delete" aria-label="Delete publication">
                                                  <i class="bi-trash"></i>
                                              </button>
                                          </div>
                                      </td>
                                  </tr>
                              </template>
                          </tbody>
                      </table>
                  </div>

                  <div x-cloak x-show="authorized && !loadError && !loading && filteredPublications.length === 0" class="pub-empty">
                      <div><i class="bi-journal-x"></i></div>
                      <p x-text="isAdmin ? 'No publications found.' : 'No publication records are assigned to your GitHub account.'"></p>
                  </div>
              </div>

              <!-- Edit / Create Form Modal -->
              <div x-cloak x-show="view === 'form'" class="admin-modal-overlay" @click="cancelForm()" @keydown.escape.window="cancelForm()">
                  <div class="admin-modal" role="dialog" aria-modal="true" @keydown.tab="trapFormFocus($event)" aria-labelledby="publication-form-title" @click.stop style="max-width:860px;width:92%">
                      <div class="admin-modal-header">
                          <div>
                              <h2 id="publication-form-title" class="admin-modal-title" x-text="editingPub ? 'Edit Publication' : 'New Publication'"></h2>
                          </div>
                          <button aria-label="Close publication form" :disabled="saving" @click="cancelForm()" style="background:none;border:none;font-size:1.5rem;line-height:1;cursor:pointer;padding:0;color:inherit;">
                              <i class="bi-x-lg"></i>
                          </button>
                      </div>

                      <div class="pub-modal-scroll-area">
                          <form @submit.prevent="await submitForm()">
                              <div x-cloak x-show="formError" role="alert" class="pub-form-error-text pub-save-error">
                                  <p x-text="formError"></p>
                                  <button x-show="conflict" type="button" class="pub-btn"
                                      @click="if (confirm('Discard your unsaved edits and load the latest record?')) await showEditForm({ publication_number: editingPub })">
                                      Reload latest record
                                  </button>
                              </div>
                              <fieldset class="pub-form-fields" :disabled="saving">

                      <!-- Basic Info -->
                      <div class="pub-form-section">
                          <div class="pub-form-section-header">
                              <i class="bi-info-circle"></i> Basic Information
                          </div>
                          <div class="pub-form-section-body">
                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-publication_number">Publication Number *</label>
                                      <input id="pub-publication_number" type="text" class="pub-form-input"
                                            :class="formErrors.publication_number ? 'pub-form-input-error' : ''"
                                            x-model="form.publication_number"
                                            placeholder="e.g. scpub104"
                                            :readonly="!!editingPub">
                                      <div x-show="formErrors.publication_number" class="pub-form-error-text"
                                          x-text="formErrors.publication_number"></div>
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-text_uid">Text UID</label>
                                      <input id="pub-text_uid" type="text" class="pub-form-input"
                                            x-model="form.text_uid" :readonly="!isAdmin"
                                            placeholder="e.g. thag, dn, mn">
                                  </div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-root_lang_iso">Root Language ISO</label>
                                      <input id="pub-root_lang_iso" type="text" class="pub-form-input"
                                            x-model="form.root_lang_iso" :readonly="!isAdmin"
                                            placeholder="e.g. pli">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-root_lang_name">Root Language Name</label>
                                      <input id="pub-root_lang_name" type="text" class="pub-form-input"
                                            x-model="form.root_lang_name" :readonly="!isAdmin"
                                            placeholder="e.g. Pali">
                                  </div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-translation_lang_iso">Translation Language ISO</label>
                                      <input id="pub-translation_lang_iso" type="text" class="pub-form-input"
                                            x-model="form.translation_lang_iso" :readonly="!isAdmin"
                                            placeholder="e.g. en, it, zh"
                                            @change="autoGenerateSourceUrl()">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-translation_lang_name">Translation Language Name</label>
                                      <input id="pub-translation_lang_name" type="text" class="pub-form-input"
                                            x-model="form.translation_lang_name" :readonly="!isAdmin"
                                            placeholder="e.g. English, Italiano">
                                  </div>
                              </div>
                          </div>
                      </div>

                      <div class="pub-form-section">
                          <div class="pub-form-section-header"><i class="bi-person"></i> Creator Information</div>
                          <div class="pub-form-section-body">
                              <div x-show="isAdmin && !editingAuthors">
                                  <button type="button" class="pub-btn" @click="beginAuthorEdit()">Edit author structure</button>
                                  <p class="pub-form-hint">Switch between a single author and a team, or add and remove authors.</p>
                              </div>
                              <template x-if="!editingAuthors"><div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label">Creator UID<span x-show="!editingPub"> *</span></label>
                                      <template x-if="!Array.isArray(form.creator_uid)"><input class="pub-form-input" aria-label="Creator UID" x-model="form.creator_uid" :readonly="!!editingPub || !isAdmin"></template>
                                      <template x-if="Array.isArray(form.creator_uid)"><div>
                                          <template x-for="(value, index) in form.creator_uid" :key="index"><input class="pub-form-input" :aria-label="'Creator UID ' + (index + 1)" x-model="form.creator_uid[index]" :readonly="!!editingPub || !isAdmin"></template>
                                      </div></template>
                                      <p x-show="formErrors.creator_uid" x-text="formErrors.creator_uid" role="alert" class="pub-form-error-text"></p>
                                  </div><div class="pub-form-group">
                                      <label class="pub-form-label">Creator name</label>
                                      <template x-if="!Array.isArray(form.creator_name)"><input class="pub-form-input" aria-label="Creator name" x-model="form.creator_name"></template>
                                      <template x-if="Array.isArray(form.creator_name)"><div>
                                          <template x-for="(value, index) in form.creator_name" :key="index"><input class="pub-form-input" :aria-label="'Creator name ' + (index + 1)" x-model="form.creator_name[index]"></template>
                                      </div></template>
                                  </div>
                              </div></template>
                              <template x-if="isAdmin && editingAuthors"><div class="pub-author-editor">
                                  <div class="pub-author-mode-select">
                                      <label class="pub-form-label" for="pub-author-mode">Author type</label>
                                      <select id="pub-author-mode" class="pub-form-input pub-form-select" :value="authorMode" @change="setAuthorMode($event.target.value)">
                                          <option value="single">Single author</option><option value="team">Team</option>
                                      </select>
                                  </div>
                                  <div class="pub-form-group" x-show="authorMode === 'single' && authorRows.length > 1">
                                      <label class="pub-form-label" for="pub-retained-author">Author to retain</label>
                                      <select id="pub-retained-author" class="pub-form-input pub-form-select" x-model="singleAuthorIndex">
                                          <option value="">Choose an author</option>
                                          <template x-for="(row, index) in authorRows" :key="index"><option :value="String(index)" x-text="row.name + ' (' + row.uid + ')' "></option></template>
                                      </select>
                                      <p class="pub-form-hint">Saving as a single author removes the other authors. Editing access is managed separately below.</p>
                                  </div>
                                  <template x-for="(row, index) in visibleAuthorRows" :key="index"><div class="pub-author-row">
                                      <div class="pub-form-group pub-author-uid-col">
                                          <label class="pub-form-label" :for="'pub-author-uid-' + index">Creator UID</label>
                                          <input :id="'pub-author-uid-' + index" class="pub-form-input" :aria-label="'Author UID ' + (index + 1)" x-model="row.uid">
                                      </div>
                                      <div class="pub-form-group pub-author-name-col">
                                          <label class="pub-form-label" :for="'pub-author-name-' + index">Creator name</label>
                                          <input :id="'pub-author-name-' + index" class="pub-form-input" :aria-label="'Author name ' + (index + 1)" x-model="row.name">
                                      </div>
                                      <div class="pub-author-action-col" x-show="authorMode === 'team'">
                                          <button type="button" class="pub-btn pub-btn-danger pub-btn-sm" :disabled="authorRows.length <= 1" :aria-label="'Remove author ' + (index + 1)" @click="removeAuthor(index)"><i class="bi-trash"></i> Remove</button>
                                      </div>
                                  </div></template>
                                  <div class="pub-author-actions">
                                      <button type="button" class="pub-btn pub-btn-sm" x-show="authorMode === 'team'" @click="addAuthor()"><i class="bi-plus-lg"></i> Add author</button>
                                      <button type="button" class="pub-btn pub-btn-sm" @click="editingAuthors = false; formErrors.authors = ''">Cancel author changes</button>
                                  </div>
                                  <p x-show="formErrors.authors" x-text="formErrors.authors" role="alert" class="pub-form-error-text"></p>
                              </div></template>
                              <div class="pub-form-divider"></div>
                              <div class="pub-form-group">
                                  <label class="pub-form-label">GitHub accounts with editing access</label>
                                  <template x-if="!Array.isArray(form.creator_github_handle)"><input class="pub-form-input" aria-label="GitHub handle" x-model="form.creator_github_handle" :readonly="!isAdmin"></template>
                                  <template x-if="Array.isArray(form.creator_github_handle)"><div>
                                      <template x-for="(value, index) in form.creator_github_handle" :key="index"><div class="pub-compact-row">
                                          <input class="pub-form-input" :aria-label="'GitHub handle ' + (index + 1)" x-model="form.creator_github_handle[index]" :readonly="!isAdmin">
                                          <button type="button" class="pub-btn pub-btn-danger pub-btn-sm pub-compact-row-btn" x-show="isAdmin" :aria-label="'Remove editing account ' + (index + 1)" @click="removeEditorHandle(index)"><i class="bi-trash"></i> Remove account</button>
                                      </div></template>
                                  </div></template>
                                  <div style="margin-top:var(--space-xs)">
                                      <button type="button" class="pub-btn pub-btn-sm" x-show="isAdmin" @click="addEditorHandle()"><i class="bi-plus-lg"></i> Add editing account</button>
                                  </div>
                                  <p class="pub-form-hint">These accounts can edit this publication when they have the Writer role. Changing authors does not change these accounts.</p>
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
                                      <label class="pub-form-label" for="pub-translation_title">Translation Title</label>
                                      <input id="pub-translation_title" x-ref="publicationTitle" x-effect="if (view === 'form') $nextTick(() => $refs.publicationTitle.focus())" type="text" class="pub-form-input"
                                            x-model="form.translation_title"
                                            placeholder="Translation title">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-translation_subtitle">Translation Subtitle</label>
                                      <input id="pub-translation_subtitle" type="text" class="pub-form-input"
                                            x-model="form.translation_subtitle"
                                            placeholder="Subtitle">
                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-root_title">Root Title</label>
                                  <input id="pub-root_title" type="text" class="pub-form-input"
                                        x-model="form.root_title"
                                        placeholder="e.g. Therag\u0101th\u0101">
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-creation_process">Creation Process</label>
                                  <textarea id="pub-creation_process" class="pub-form-textarea"
                                            x-model="form.creation_process"
                                            placeholder="Describe the translation process..."></textarea>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-text_description">Text Description</label>
                                  <textarea id="pub-text_description" class="pub-form-textarea"
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
                                  <label class="pub-form-label" for="pub-source_url">Source URL</label>
                                  <input id="pub-source_url" type="text" class="pub-form-input"
                                        x-model="form.source_url" :readonly="!isAdmin"
                                        placeholder="https://github.com/suttacentral/bilara-data/tree/published/...">
                                  <div class="pub-form-hint">For a new publication, generated from creator UID and language ISO. Existing paths are preserved.</div>
                              </div>

                              <div class="pub-form-row">
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-publication_status">Publication Status</label>
                                      <input id="pub-publication_status" type="text" class="pub-form-input"
                                            x-model="form.publication_status"
                                            placeholder="e.g. Completed, In progress">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-first_published">First Published</label>
                                      <input id="pub-first_published" type="text" class="pub-form-input"
                                            x-model="form.first_published"
                                            placeholder="e.g. 2024">

                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-editions_url">Editions URL</label>
                                  <input id="pub-editions_url" type="text" class="pub-form-input"
                                        x-model="form.editions_url"
                                        placeholder="e.g. https://suttacentral.net/thag">

                              </div>

                              <div class="pub-form-checkbox-group">
                                  <input type="checkbox" class="pub-form-checkbox"
                                        id="pub-is-published" x-model="form.is_published" :disabled="!isAdmin">
                                  <label for="pub-is-published">Is Published</label>
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
                                      <label class="pub-form-label" for="pub-license_type">License Type</label>
                                      <input id="pub-license_type" type="text" class="pub-form-input"
                                            x-model="form.license_type"
                                            placeholder="Creative Commons Zero">
                                  </div>
                                  <div class="pub-form-group">
                                      <label class="pub-form-label" for="pub-license_abbreviation">License Abbreviation</label>
                                      <input id="pub-license_abbreviation" type="text" class="pub-form-input"
                                            x-model="form.license_abbreviation"
                                            placeholder="CC0">
                                  </div>
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-license_url">License URL</label>
                                  <input id="pub-license_url" type="text" class="pub-form-input"
                                        x-model="form.license_url"
                                        placeholder="https://creativecommons.org/publicdomain/zero/1.0/">
                              </div>

                              <div class="pub-form-group">
                                  <label class="pub-form-label" for="pub-license_statement">License Statement</label>
                                  <textarea id="pub-license_statement" class="pub-form-textarea"
                                            x-model="form.license_statement"
                                            placeholder="License statement text..."></textarea>
                              </div>
                          </div>
                      </div>
                      </fieldset>

                      <div class="pub-form-actions" style="margin-top:1.5rem;padding:0;border-top:none;background:transparent;">
                          <button type="button" class="pub-btn" @click="cancelForm()">Cancel</button>
                          <button type="submit" class="pub-btn pub-btn-primary" :disabled="saving || conflict">
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

customElements.define('sc-bilara-publications', ScBilaraPublications);
