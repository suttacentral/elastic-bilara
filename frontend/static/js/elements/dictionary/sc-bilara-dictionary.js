import { html, css, LitElement } from 'https://cdn.jsdelivr.net/npm/lit@3.3.2/+esm';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/input/input.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/button/button.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/spinner/spinner.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/icon/icon.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/card/card.js';
import 'https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/components/divider/divider.js';

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
      background-color: var(--sl-color-neutral-0);
      border-radius: var(--sl-border-radius-medium);
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .html-content th, .html-content td {
      border: 1px solid var(--sl-color-neutral-200);
      padding: 0.75rem 1rem;
      text-align: left;
    }

    .html-content th {
      background-color: var(--sl-color-neutral-50);
      font-weight: 600;
      color: var(--sl-color-neutral-700);
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
  `;

  static properties = {
    words: { type: Array },
    selectedWord: { type: Object },
    selectedWordDetail: { type: Object },
    loading: { type: Boolean },
    detailLoading: { type: Boolean },
    searchQuery: { type: String },
    page: { type: Number },
    hasMore: { type: Boolean }
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
  }

  connectedCallback() {
    super.connectedCallback();
    this.fetchWords();
  }

  async fetchWords() {
    this.loading = true;
    try {
      const skip = this.page * this.limit;
      let url = `/api/v1/dictionary/list?skip=${skip}&limit=${this.limit}`;
      if (this.searchQuery) {
        url += `&search=${encodeURIComponent(this.searchQuery)}`;
      }

      const response = await fetch(url);
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
    await this.fetchWordDetail(word.word);
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
              <sl-icon name="search" slot="prefix"></sl-icon>
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
                      ${w.word}
                    </div>
                  `)}
                  ${this.words.length === 0 ? html`<div style="padding: 1rem; color: var(--sl-color-neutral-500); text-align: center;">No words found</div>` : ''}
                </div>
              `
          }

          <!-- Pagination -->
          ${this.page > 0 || this.hasMore ? html`
            <div class="pagination">
              <sl-button size="small" circle ?disabled=${this.page === 0} @click=${this.prevPage}>
                <sl-icon name="chevron-left"></sl-icon>
              </sl-button>
              <span style="font-size: 0.9rem; color: var(--sl-color-neutral-600);">Page ${this.page + 1}</span>
              <sl-button size="small" circle ?disabled=${!this.hasMore} @click=${this.nextPage}>
                <sl-icon name="chevron-right"></sl-icon>
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
                <div slot="header" style="font-weight: 600; color: var(--sl-color-neutral-600);">Summary</div>
                <div class="html-content" .innerHTML=${this.selectedWordDetail.summary_html} @click=${this.handleHtmlClick}></div>
              </sl-card>
            ` : ''}

            ${!this.detailLoading && this.selectedWordDetail?.dpd_html ? html`
              <sl-card style="width: 100%;">
                <div slot="header" style="font-weight: 600; color: var(--sl-color-neutral-600);">Detailed Definition (DPD)</div>
                <div class="html-content" .innerHTML=${this.selectedWordDetail.dpd_html} @click=${this.handleHtmlClick}></div>
              </sl-card>
            ` : ''}

            ${!this.detailLoading && this.selectedWordDetail && !this.selectedWordDetail.summary_html && !this.selectedWordDetail.dpd_html ? html`
              <div class="empty-state">
                <h2>No definition content</h2>
                <p>This word has no cached summary or detailed definition.</p>
              </div>
            ` : ''}
          ` : html`
            <div class="empty-state">
              <sl-icon name="journal-text"></sl-icon>
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
