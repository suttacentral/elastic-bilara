import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
import { registerIconLibrary } from 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/utilities/icon-library.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/input/input.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/button/button.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/spinner/spinner.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/icon/icon.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/card/card.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/divider/divider.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/textarea/textarea.js';

if (!globalThis.__scBilaraBiIconLibraryRegistered) {
  registerIconLibrary('bi', {
    resolver: name => `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/icons/${name}.svg`,
    mutator: svg => svg.setAttribute('fill', 'currentColor'),
  });
  globalThis.__scBilaraBiIconLibraryRegistered = true;
}

export class SCBilaraDictionary extends LitElement {
  static styles = css`
    :host {
      display: block;
      height: 100%;
      --nav-width: 350px;
    }

    .container {
      display: flex;
      height: 100%;
      background-color: var(--color-background);
      font-family: var(--sl-font-sans);
    }

    .sidebar {
      width: var(--nav-width);
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--color-border);
      background-color: var(--color-background-secondary);
    }

    .search-container {
      padding: 1rem;
      border-bottom: 1px solid var(--color-border);
    }

    .word-list {
      flex: 1;
      overflow-y: auto;
      padding: 0.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .word-item {
      display: flex;
      align-items: center;
      padding: 0.75rem 1rem;
      cursor: pointer;
      border-radius: var(--sl-border-radius-medium);
      color: var(--color-text);
      transition: background-color 0.15s ease, color 0.15s ease;
      font-size: 1.1rem;
    }

    .word-item:hover {
      background-color: var(--sl-color-neutral-200);
    }

    .word-item.selected {
      background-color: var(--sl-color-primary-100);
      color: var(--sl-color-primary-700);
      font-weight: 600;
    }

    .word-label {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .word-remove-btn {
      flex-shrink: 0;
      opacity: 0;
      margin-left: 0.25rem;
      color: var(--sl-color-neutral-500);
      transition: opacity 0.15s ease, color 0.15s ease;
      cursor: pointer;
      font-size: 1rem;
    }

    .word-item:hover .word-remove-btn {
      opacity: 1;
    }

    .word-remove-btn:hover {
      color: var(--sl-color-danger-600);
    }

    .content-area {
      flex: 1;
      padding: 2rem 3rem;
      overflow-y: auto;
      background-color: var(--color-background);
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--sl-color-neutral-500);
      text-align: center;
    }

    .empty-state sl-icon {
      font-size: 4rem;
      margin-bottom: 1rem;
      color: var(--sl-color-neutral-300);
    }

    .definition-header {
      margin-bottom: 2rem;
    }

    .definition-title {
      font-size: 2.5rem;
      color: var(--color-text);
      margin: 0 0 0.5rem 0;
      font-weight: 700;
    }

    .html-content {
      line-height: 1.6;
      color: var(--color-text);
      font-size: 1.1rem;
    }

    .html-content p {
      margin-bottom: 1rem;
    }

    .html-content a {
      color: var(--sl-color-primary-600);
      text-decoration: none;
    }

    .html-content a:hover {
      text-decoration: underline;
    }

    /* DPD specific styles */
    .dpd-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.35rem 0.85rem;
      margin: 0.25rem;
      border-radius: var(--sl-border-radius-pill);
      background-color: var(--sl-color-primary-50);
      color: var(--sl-color-primary-700);
      text-decoration: none !important;
      cursor: pointer;
      font-size: 0.95rem;
      font-weight: 500;
      border: 1px solid var(--sl-color-primary-200);
      transition: all 0.2s ease;
    }

    .dpd-button:hover {
      background-color: var(--sl-color-primary-100);
      border-color: var(--sl-color-primary-400);
    }

    .dpd-button svg {
      width: 1.2rem;
      height: 1.2rem;
      margin-right: 0.35rem;
    }

    .dpd-button.play:not(.small) svg {
      margin-right: 0;
    }

    .dpd-button.play.small {
      padding: 0.2rem;
      margin: 0 0.2rem;
      border-radius: 50%;
    }

    .dpd-button.play.small svg {
      width: 1.1rem;
      height: 1.1rem;
      margin-right: 0;
    }

    .button-box {
      margin: 1.5rem 0;
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .content.hidden {
      display: none;
    }

    .html-content table {
      width: 100%;
      border-collapse: collapse;
      margin: 1.5rem 0;
      font-size: 0.95rem;
      background-color: var(--color-background-secondary);
      border-radius: var(--sl-border-radius-medium);
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .html-content th, .html-content td {
      border: 1px solid var(--color-border);
      padding: 0.75rem 1rem;
      text-align: left;
    }

    .html-content th {
      background-color: var(--color-background-tertiary);
      font-weight: 600;
      color: var(--color-text-emphasized);
      width: 25%;
    }

    .html-content td.gr0, .html-content td.gap {
      color: var(--sl-color-neutral-300);
    }

    .html-content .gray {
      color: var(--sl-color-neutral-400);
    }

    .heading.underlined {
      border-bottom: 2px solid var(--sl-color-neutral-200);
      padding-bottom: 0.5rem;
      margin-bottom: 1rem;
      font-weight: 600;
      color: var(--color-text);
      font-size: 1.1rem;
    }

    .dpd-footer {
      font-size: 0.85rem;
      color: var(--sl-color-neutral-500);
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid var(--sl-color-neutral-200);
    }

    .loading-container {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 2rem;
    }

    .pagination {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem;
      border-top: 1px solid var(--color-border);
      background-color: var(--color-background-tertiary);
    }

    .pagination-button::part(base) {
      background-color: var(--color-background-secondary);
      border-color: var(--color-text-secondary);
      color: var(--color-text-emphasized);
      box-shadow: none;
    }

    .pagination-button:hover::part(base),
    .pagination-button:focus-within::part(base) {
      background-color: var(--color-background);
      border-color: var(--color-primary);
      color: var(--color-text-emphasized);
    }

    .pagination-button[disabled]::part(base) {
      background-color: var(--color-background-secondary);
      border-color: var(--color-border);
      color: var(--color-text-secondary);
      opacity: 0.7;
    }

    /* Notes section */
    .notes-card {
      margin-top: 2rem;
      width: 100%;
    }

    .notes-card::part(base) {
      border: 1px solid var(--color-border);
      box-shadow: var(--sl-shadow-sm);
    }

    .section-card-header {
      font-weight: 600;
      color: var(--color-text-emphasized);
    }

    .notes-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 600;
      color: var(--color-text-emphasized);
    }

    .empty-list-message {
      padding: 1rem;
      color: var(--color-text-secondary);
      text-align: center;
    }

    .pagination-label {
      font-size: 0.9rem;
      color: var(--color-text-secondary);
    }

    .notes-actions {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-top: 1rem;
    }

    .notes-actions-spacer {
      flex: 1;
    }

    .notes-login-hint {
      color: var(--sl-color-neutral-500);
      font-size: 0.95rem;
      padding: 1rem 0;
    }

    .notes-status {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.9rem;
      font-weight: 500;
      opacity: 0;
      transition: opacity 0.3s ease;
    }

    .notes-status.visible {
      opacity: 1;
    }

    .notes-status.saved {
      color: var(--sl-color-success-600);
    }

    .notes-status.error {
      color: var(--sl-color-danger-600);
    }

    .notes-textarea {
      --sl-input-background-color: var(--color-background-secondary);
      --sl-input-background-color-hover: var(--color-background-tertiary);
      --sl-input-background-color-focus: var(--color-background);
      --sl-input-border-color: var(--color-border);
      --sl-input-border-color-focus: var(--sl-color-primary-400);
      --sl-input-color: var(--color-text-emphasized);
      --sl-input-placeholder-color: var(--color-text-secondary);
      --sl-input-color-focus: var(--color-text-emphasized);
      --sl-focus-ring-color: var(--sl-color-primary-100);
    }

    .notes-textarea::part(base) {
      background-color: var(--color-background-secondary);
      border-color: var(--color-border);
    }

    .notes-textarea::part(textarea) {
      background-color: transparent;
      color: var(--color-text-emphasized);
      -webkit-text-fill-color: var(--color-text-emphasized);
      caret-color: var(--color-text-emphasized);
      opacity: 1;
    }

    .notes-textarea::part(textarea)::placeholder {
      color: var(--color-text-secondary);
      -webkit-text-fill-color: var(--color-text-secondary);
      opacity: 1;
    }

    .notes-textarea:focus-within::part(base) {
      background-color: var(--color-background);
      border-color: var(--sl-color-primary-400);
    }

    .notes-textarea:focus-within::part(textarea) {
      color: var(--color-text-emphasized);
      -webkit-text-fill-color: var(--color-text-emphasized);
      caret-color: var(--color-text-emphasized);
    }
  `;

  static properties = {
    words: { type: Array },
    selectedWord: { type: Object },
    selectedWordDetail: { type: Object },
    loading: { type: Boolean },
    detailLoading: { type: Boolean },
    searchQuery: { type: String },
    page: { type: Number },
    hasMore: { type: Boolean },
    noteValue: { type: String },
    noteLoading: { type: Boolean },
    noteSaving: { type: Boolean },
    noteExists: { type: Boolean },
    noteStatus: { type: String },
    isLoggedIn: { type: Boolean },
  };

  constructor() {
    super();
    this.words = [];
    this.selectedWord = null;
    this.selectedWordDetail = null;
    this.loading = false;
    this.detailLoading = false;
    this.searchQuery = '';
    this.page = 0;
    this.limit = 50;
    this.hasMore = false;
    // Notes state
    this.noteValue = '';
    this._savedNoteValue = '';
    this.noteLoading = false;
    this.noteSaving = false;
    this.noteExists = false;
    this.noteStatus = '';
    this.isLoggedIn = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this._initLoad();
  }

  async _initLoad() {
    await this._checkLoginStatus();
    this.fetchWords();
  }

  async _checkLoginStatus() {
    try {
      const response = await requestWithTokenRetry('users/me');
      this.isLoggedIn = response.ok;
    } catch {
      this.isLoggedIn = false;
    }
  }

  _getListUrl() {
    const skip = this.page * this.limit;
    const base = this.isLoggedIn ? 'dictionary/my-list' : 'dictionary/list';
    let url = `${base}?skip=${skip}&limit=${this.limit}`;
    if (this.searchQuery) {
      url += `&search=${encodeURIComponent(this.searchQuery)}`;
    }
    return url;
  }

  async fetchWords() {
    this.loading = true;
    try {
      let response;
      if (this.isLoggedIn) {
        response = await requestWithTokenRetry(this._getListUrl());
      } else {
        response = await fetch(`/api/v1/${this._getListUrl()}`);
      }
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();

      this.words = data.items || [];
      this.hasMore = Boolean(data.has_more);

      // Select first word if none selected and words exist
      if (this.words.length > 0 && !this.selectedWord) {
        this.selectWord(this.words[0]);
      } else if (this.selectedWord) {
        const current = this.words.find((w) => w.word === this.selectedWord.word);
        if (current) {
          this.selectedWord = current;
        } else {
          this.selectedWord = null;
          this.selectedWordDetail = null;
        }
      }
    } catch (error) {
      console.error('Failed to fetch dictionary entries:', error);
      this.hasMore = false;
    } finally {
      this.loading = false;
    }
  }

  async hideWord(word, e) {
    e.stopPropagation();
    try {
      const response = await requestWithTokenRetry(
        `dictionary/${encodeURIComponent(word)}/list-entry`,
        { method: 'DELETE', credentials: 'include' }
      );
      if (!response.ok) throw new Error('Failed to hide word');

      // Remove from local list
      this.words = this.words.filter(w => w.word !== word);

      // Handle selected word removal
      if (this.selectedWord?.word === word) {
        if (this.words.length > 0) {
          this.selectWord(this.words[0]);
        } else {
          this.selectedWord = null;
          this.selectedWordDetail = null;
          this.noteValue = '';
          this._savedNoteValue = '';
          this.noteExists = false;
          this.noteStatus = '';
        }
      }
    } catch (error) {
      console.error('Failed to hide word:', error);
    }
  }

  async fetchWordDetail(word) {
    this.detailLoading = true;
    try {
      const response = await fetch(`/api/v1/dictionary/${encodeURIComponent(word)}`);
      if (!response.ok) throw new Error('Failed to fetch dictionary detail');
      this.selectedWordDetail = await response.json();
    } catch (error) {
      console.error('Failed to fetch dictionary detail:', error);
      this.selectedWordDetail = null;
    } finally {
      this.detailLoading = false;
    }
  }

  handleSearch(e) {
    if (e.key === 'Enter' || e.type === 'sl-clear') {
      this.searchQuery = e.target.value;
      this.page = 0;
      this.selectedWord = null;
      this.fetchWords();
    }
  }

  handleHtmlClick(e) {
    const button = e.target.closest('.dpd-button');
    if (button) {
      e.preventDefault();
      const targetId = button.getAttribute('data-target');
      if (targetId) {
        const targetEl = this.shadowRoot.getElementById(targetId);
        if (targetEl) {
          // Toggle hidden state
          const isHidden = targetEl.classList.contains('hidden');

          // Optionally, hide other open sections here if exclusive tabs are desired
          // this.shadowRoot.querySelectorAll('.content:not(.hidden)').forEach(el => el.classList.add('hidden'));

          if (isHidden) {
            targetEl.classList.remove('hidden');
          } else {
            targetEl.classList.add('hidden');
          }
        }
      }
    }
  }

  async selectWord(word) {
    this.selectedWord = word;
    this.selectedWordDetail = null;
    this.noteValue = '';
    this._savedNoteValue = '';
    this.noteExists = false;
    this.noteStatus = '';
    this.fetchWordDetail(word.word);
    this.fetchNote(word.word);
  }

  // ── Notes methods ──────────────────────────────────────────────

  async fetchNote(word) {
    if (!this.isLoggedIn) return;
    this.noteLoading = true;
    try {
      const response = await requestWithTokenRetry(
        `dictionary/${encodeURIComponent(word)}/note`,
        { credentials: 'include' }
      );
      if (this.selectedWord?.word !== word) return;
      if (response.ok) {
        const data = await response.json();
        if (data) {
          this.noteValue = data.note_value;
          this._savedNoteValue = data.note_value;
          this.noteExists = true;
        } else {
          this.noteValue = '';
          this._savedNoteValue = '';
          this.noteExists = false;
        }
      }
    } catch (error) {
      console.error('Failed to fetch note:', error);
    } finally {
      if (this.selectedWord?.word === word) {
        this.noteLoading = false;
      }
    }
  }

  async saveNote() {
    if (!this.selectedWord || this.noteSaving) return;
    const word = this.selectedWord.word;
    this.noteSaving = true;
    this.noteStatus = '';
    try {
      const response = await requestWithTokenRetry(
        `dictionary/${encodeURIComponent(word)}/note`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_value: this.noteValue }),
        }
      );
      if (this.selectedWord?.word !== word) return;
      if (response.ok) {
        this._savedNoteValue = this.noteValue;
        this.noteExists = true;
        this.noteStatus = 'saved';
        setTimeout(() => { this.noteStatus = ''; }, 3000);
      } else {
        this.noteStatus = 'error';
      }
    } catch (error) {
      console.error('Failed to save note:', error);
      this.noteStatus = 'error';
    } finally {
      this.noteSaving = false;
    }
  }

  async deleteNote() {
    if (!this.selectedWord || !this.noteExists) return;
    const word = this.selectedWord.word;
    this.noteSaving = true;
    this.noteStatus = '';
    try {
      const response = await requestWithTokenRetry(
        `dictionary/${encodeURIComponent(word)}/note`,
        { method: 'DELETE', credentials: 'include' }
      );
      if (this.selectedWord?.word !== word) return;
      if (response.ok) {
        this.noteValue = '';
        this._savedNoteValue = '';
        this.noteExists = false;
        this.noteStatus = '';
      }
    } catch (error) {
      console.error('Failed to delete note:', error);
    } finally {
      this.noteSaving = false;
    }
  }

  _onNoteInput(e) {
    this.noteValue = e.target.value;
  }

  get _noteHasChanges() {
    return this.noteValue !== this._savedNoteValue;
  }

  nextPage() {
    if (this.hasMore) {
      this.page++;
      this.selectedWord = null;
      this.selectedWordDetail = null;
      this.fetchWords();
    }
  }

  prevPage() {
    if (this.page > 0) {
      this.page--;
      this.selectedWord = null;
      this.selectedWordDetail = null;
      this.fetchWords();
    }
  }

  render() {
    return html`
      <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
          <div class="search-container">
            <sl-input
              placeholder="Search words..."
              clearable
              value=${this.searchQuery}
              @keydown=${this.handleSearch}
              @sl-clear=${this.handleSearch}
            >
              <sl-icon library="bi" name="search" slot="prefix"></sl-icon>
            </sl-input>
          </div>

          ${this.loading
            ? html`<div class="loading-container"><sl-spinner style="font-size: 2rem;"></sl-spinner></div>`
            : html`
                <div class="word-list">
                  ${this.words.map(w => html`
                    <div
                      class="word-item ${this.selectedWord?.word === w.word ? 'selected' : ''}"
                      @click=${() => this.selectWord(w)}
                    >
                      <span class="word-label">${w.word}</span>
                      ${this.isLoggedIn ? html`
                        <sl-icon
                          library="bi"
                          class="word-remove-btn"
                          name="x-lg"
                          label="Remove from my list"
                          @click=${(e) => this.hideWord(w.word, e)}
                        ></sl-icon>
                      ` : ''}
                    </div>
                  `)}
                  ${this.words.length === 0 ? html`<div class="empty-list-message">No words found</div>` : ''}
                </div>
              `
          }

          <!-- Pagination -->
          ${this.page > 0 || this.hasMore ? html`
            <div class="pagination">
              <sl-button class="pagination-button" size="small" circle ?disabled=${this.page === 0} @click=${this.prevPage}>
                <sl-icon library="bi" name="chevron-left"></sl-icon>
              </sl-button>
              <span class="pagination-label">Page ${this.page + 1}</span>
              <sl-button class="pagination-button" size="small" circle ?disabled=${!this.hasMore} @click=${this.nextPage}>
                <sl-icon library="bi" name="chevron-right"></sl-icon>
              </sl-button>
            </div>
          ` : ''}
        </div>

        <!-- Main Content Area -->
        <div class="content-area">
          ${this.selectedWord ? html`
            <div class="definition-header">
              <h1 class="definition-title">${this.selectedWord.word}</h1>
            </div>

            ${this.detailLoading ? html`
              <div class="loading-container"><sl-spinner style="font-size: 2rem;"></sl-spinner></div>
            ` : ''}

            ${!this.detailLoading && this.selectedWordDetail?.summary_html ? html`
              <sl-card style="margin-bottom: 2rem; width: 100%;">
                <div slot="header" class="section-card-header">Summary</div>
                <div class="html-content" .innerHTML=${this.selectedWordDetail.summary_html} @click=${this.handleHtmlClick}></div>
              </sl-card>
            ` : ''}

            ${!this.detailLoading && this.selectedWordDetail?.dpd_html ? html`
              <sl-card style="width: 100%;">
                <div slot="header" class="section-card-header">Detailed Definition (DPD)</div>
                <div class="html-content" .innerHTML=${this.selectedWordDetail.dpd_html} @click=${this.handleHtmlClick}></div>
              </sl-card>
            ` : ''}

            ${!this.detailLoading && this.selectedWordDetail && !this.selectedWordDetail.summary_html && !this.selectedWordDetail.dpd_html ? html`
              <div class="empty-state">
                <h2>No definition content</h2>
                <p>This word has no cached summary or detailed definition.</p>
              </div>
            ` : ''}

            <!-- My Notes -->
            <sl-card class="notes-card">
              <div slot="header" class="notes-header">
                <sl-icon library="bi" name="pencil-square"></sl-icon>
                My Notes
              </div>
              ${!this.isLoggedIn ? html`
                <div class="notes-login-hint">Please login to add notes.</div>
              ` : this.noteLoading ? html`
                <div class="loading-container"><sl-spinner style="font-size: 1.5rem;"></sl-spinner></div>
              ` : html`
                <sl-textarea
                  class="notes-textarea"
                  placeholder="Write your notes about this word..."
                  rows="4"
                  resize="auto"
                  .value=${this.noteValue}
                  @sl-input=${this._onNoteInput}
                ></sl-textarea>
                <div class="notes-actions">
                  <div class="notes-status ${this.noteStatus} ${this.noteStatus ? 'visible' : ''}">
                    ${this.noteStatus === 'saved' ? html`<sl-icon library="bi" name="check-circle-fill"></sl-icon> Saved successfully` : ''}
                    ${this.noteStatus === 'error' ? html`<sl-icon library="bi" name="exclamation-circle-fill"></sl-icon> Failed to save` : ''}
                  </div>
                  <div class="notes-actions-spacer"></div>
                  ${this.noteExists ? html`
                    <sl-button
                      variant="danger"
                      outline
                      size="small"
                      ?disabled=${this.noteSaving}
                      @click=${this.deleteNote}
                    >
                      <sl-icon library="bi" slot="prefix" name="trash"></sl-icon>
                      Delete
                    </sl-button>
                  ` : ''}
                  <sl-button
                    variant="primary"
                    size="small"
                    ?disabled=${this.noteSaving || !this.noteValue.trim() || !this._noteHasChanges}
                    ?loading=${this.noteSaving}
                    @click=${this.saveNote}
                  >
                    <sl-icon library="bi" slot="prefix" name="check-lg"></sl-icon>
                    Save
                  </sl-button>
                </div>
              `}
            </sl-card>
          ` : html`
            <div class="empty-state">
              <sl-icon library="bi" name="journal-text"></sl-icon>
              <h2>Select a word</h2>
              <p>Choose a Pali word from the list to view its summary and definition.</p>
            </div>
          `}
        </div>
      </div>
    `;
  }
}

customElements.define('sc-bilara-dictionary', SCBilaraDictionary);
