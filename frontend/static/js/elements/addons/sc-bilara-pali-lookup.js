import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

/**
 * Pali Dictionary Lookup Component
 *
 * Displays dictionary definitions from DPDict when hovering over Pali words in source text.
 *
 * Usage:
 * <sc-bilara-pali-lookup></sc-bilara-pali-lookup>
 *
 * The component automatically attaches to elements matching the selector
 * for source/root text textareas.
 */
export class ScBilaraPaliLookup extends LitElement {
    static properties = {
        visible: { type: Boolean, state: true },
        word: { type: String, state: true },
        summaries: { type: Array, state: true },
        loading: { type: Boolean, state: true },
        error: { type: String, state: true },
        posX: { type: Number, state: true },
        posY: { type: Number, state: true }
    };

    static styles = css`
        :host {
            --lookup-bg: var(--color-background);
            --lookup-border: var(--color-border);
            --lookup-text: var(--color-text);
            --lookup-text-secondary: var(--color-text-secondary);
            --lookup-primary: var(--color-primary);
            --lookup-shadow: var(--shadow-lg);
            --lookup-radius: var(--radius-md);
        }

        .tooltip {
            position: fixed;
            z-index: 10000;
            max-width: 450px;
            max-height: 350px;
            background-color: var(--lookup-bg);
            border: 1px solid var(--lookup-border);
            border-radius: var(--lookup-radius);
            box-shadow: var(--lookup-shadow);
            overflow: hidden;
            animation: fadeIn 0.2s ease;
            display: flex;
            flex-direction: column;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(-4px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .tooltip__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            background-color: var(--lookup-primary);
            color: white;
            font-weight: 600;
            font-size: 0.95rem;
        }

        .tooltip__word {
            font-style: italic;
        }

        .tooltip__play {
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            padding: 2px 6px;
            margin-left: 8px;
            opacity: 0.9;
            transition: opacity 0.2s, transform 0.2s;
            display: flex;
            align-items: center;
        }

        .tooltip__play:hover {
            opacity: 1;
            transform: scale(1.1);
        }

        .tooltip__play.playing {
            animation: pulse 0.8s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .tooltip__play svg {
            width: 16px;
            height: 16px;
            fill: currentColor;
        }

        .tooltip__close {
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 1.1rem;
            padding: 0 4px;
            opacity: 0.8;
            transition: opacity 0.2s;
        }

        .tooltip__close:hover {
            opacity: 1;
        }

        .tooltip__content {
            padding: 12px;
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            font-size: 0.9rem;
            line-height: 1.6;
            color: var(--lookup-text);
        }

        .tooltip__loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: var(--lookup-text-secondary);
        }

        .tooltip__loading::after {
            content: '';
            width: 16px;
            height: 16px;
            margin-left: 8px;
            border: 2px solid var(--lookup-border);
            border-top-color: var(--lookup-primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .tooltip__error {
            padding: 16px;
            color: var(--color-error, #dc322f);
            text-align: center;
        }

        .tooltip__summary {
            margin-bottom: 8px;
            padding: 8px 10px;
            background-color: var(--color-background-secondary, #f5f5f5);
            border-radius: 4px;
            border-left: 3px solid var(--lookup-primary);
        }

        .tooltip__summary:last-child {
            margin-bottom: 0;
        }

        .tooltip__summary-word {
            font-weight: 600;
            color: var(--lookup-primary);
            margin-right: 6px;
        }

        .tooltip__summary-pos {
            font-style: italic;
            color: var(--lookup-text-secondary);
            margin-right: 4px;
        }

        .tooltip__summary-meaning {
            font-weight: 500;
        }

        .tooltip__not-found {
            padding: 16px;
            text-align: center;
            color: var(--lookup-text-secondary);
            font-style: italic;
        }

        .tooltip__link {
            display: block;
            text-align: right;
            padding: 8px 12px;
            font-size: 0.8rem;
            color: var(--lookup-primary);
            text-decoration: none;
            border-top: 1px solid var(--lookup-border);
            background-color: var(--lookup-bg);
            flex-shrink: 0;
        }

        .tooltip__link:hover {
            text-decoration: underline;
        }
    `;

    // Cache for dictionary lookups
    static _cache = new Map();

    constructor() {
        super();
        this.visible = false;
        this.word = '';
        this.summaries = [];
        this.loading = false;
        this.error = null;
        this.posX = 0;
        this.posY = 0;

        this._currentWord = null;
        this._boundHandleClick = this._handleClick.bind(this);
        this._boundHandleDocumentClick = this._handleDocumentClick.bind(this);
        this._isMouseOverTooltip = false;
    }

    connectedCallback() {
        super.connectedCallback();
        this._attachListeners();

        // Re-attach listeners when DOM changes (for dynamically loaded content)
        this._observer = new MutationObserver(() => this._attachListeners());
        this._observer.observe(document.body, { childList: true, subtree: true });
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this._detachListeners();
        if (this._observer) {
            this._observer.disconnect();
        }
        document.removeEventListener('click', this._boundHandleDocumentClick);
    }

    _attachListeners() {
        // Target source/root text textareas (readonly ones)
        const sourceTextareas = document.querySelectorAll(
            '.translation-cell--source .translation-cell__textarea'
        );

        sourceTextareas.forEach(textarea => {
            if (!textarea._paliLookupAttached) {
                textarea.addEventListener('click', this._boundHandleClick);
                textarea._paliLookupAttached = true;
            }
        });

        // Listen for clicks outside to close tooltip
        document.addEventListener('click', this._boundHandleDocumentClick);
    }

    _detachListeners() {
        const sourceTextareas = document.querySelectorAll(
            '.translation-cell--source .translation-cell__textarea'
        );

        sourceTextareas.forEach(textarea => {
            textarea.removeEventListener('click', this._boundHandleClick);
            textarea._paliLookupAttached = false;
        });
    }

    _handleClick(event) {
        event.stopPropagation();
        const textarea = event.target;

        // Use selectionStart which is set by the browser after click
        // This is more accurate than coordinate-based calculation
        const charIndex = textarea.selectionStart;
        const text = textarea.value;

        if (!text || charIndex < 0) return;

        const word = this._extractWordAt(text, charIndex);

        if (word && word.length >= 2) {
            this._currentWord = word;
            this._lookupWord(word, event.clientX, event.clientY);
        }
    }

    _cleanWord(text) {
        // Remove punctuation and extra spaces, get the first word if multiple
        const cleaned = text.replace(/[.,;:!?()[\]{}"'<>«»—–\-\d\s]+/g, ' ').trim();
        const words = cleaned.split(/\s+/);
        // Return the first word if user selected multiple, or the entire cleaned text if single word
        return words.length === 1 ? cleaned : words[0];
    }

    _handleDocumentClick(event) {
        // Check if click is outside the tooltip
        const tooltip = this.shadowRoot?.querySelector('.tooltip');
        if (tooltip && !tooltip.contains(event.target)) {
            // Don't hide if clicking on source textarea with selection
            const isSourceTextarea = event.target.closest('.translation-cell--source .translation-cell__textarea');
            if (!isSourceTextarea) {
                this._hideTooltip();
            }
        }
    }

    _getWordAtPoint(textarea, x, y) {
        const text = textarea.value;
        if (!text) return null;

        const rect = textarea.getBoundingClientRect();
        const style = window.getComputedStyle(textarea);
        const paddingLeft = parseFloat(style.paddingLeft);
        const paddingTop = parseFloat(style.paddingTop);
        const paddingRight = parseFloat(style.paddingRight);
        const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.2;
        const fontSize = parseFloat(style.fontSize);

        // Calculate content width (textarea width minus padding)
        const contentWidth = textarea.clientWidth - paddingLeft - paddingRight;

        // Approximate character width
        const charWidth = fontSize * 0.55;

        // Calculate how many characters fit per visual line
        const charsPerLine = Math.floor(contentWidth / charWidth);

        // Calculate relative position within the textarea
        const relX = x - rect.left - paddingLeft + textarea.scrollLeft;
        const relY = y - rect.top - paddingTop + textarea.scrollTop;

        if (relX < 0 || relY < 0) return null;

        // Estimate visual line and character position within that line
        const visualLineIndex = Math.floor(relY / lineHeight);
        const charInLine = Math.floor(relX / charWidth);

        // Calculate the absolute character index in the text
        // Account for word wrapping by calculating position based on visual lines
        let charIndex = visualLineIndex * charsPerLine + charInLine;

        // Clamp to text length
        if (charIndex >= text.length) {
            charIndex = text.length - 1;
        }
        if (charIndex < 0) return null;

        // Find the word at this position
        return this._extractWordAt(text, charIndex);
    }

    _extractWordAt(text, index) {
        if (index < 0 || index >= text.length) return null;

        // Define word boundaries (space, punctuation, etc.)
        const wordPattern = /[\s\.,;:!?\(\)\[\]\{\}"'<>«»—–\-\d]/;

        // Find word start
        let start = index;
        while (start > 0 && !wordPattern.test(text[start - 1])) {
            start--;
        }

        // Find word end
        let end = index;
        while (end < text.length && !wordPattern.test(text[end])) {
            end++;
        }

        const word = text.slice(start, end).trim();

        // Filter out very short words and common punctuation
        if (word.length < 2) return null;

        return word;
    }

    async _lookupWord(word, x, y) {
        this.word = word;
        this.posX = x;
        this.posY = y;
        this.visible = true;

        // Check cache first
        const cacheKey = word.toLowerCase();
        if (ScBilaraPaliLookup._cache.has(cacheKey)) {
            this.summaries = ScBilaraPaliLookup._cache.get(cacheKey);
            this.loading = false;
            this.error = null;
            this._adjustPosition();
            return;
        }

        this.loading = true;
        this.error = null;
        this.summaries = [];

        try {
            const response = await fetch(
                `/api/v1/dictionary/${encodeURIComponent(word)}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            const summaryHtml = data.summary_html || '';
            const summaries = this._parseHtmlResponse(summaryHtml);

            // Cache the result
            ScBilaraPaliLookup._cache.set(cacheKey, summaries);

            this.summaries = summaries;
            this.loading = false;
            this._adjustPosition();
        } catch (err) {
            this.loading = false;
            this.error = 'Unable to obtain definition';
            console.error('Pali lookup error:', err);
        }
    }

    _parseHtmlResponse(htmlText) {
        if (!htmlText) return [];

        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');

        const summaries = [];

        const summaryElements = doc.querySelectorAll('p.summary');

        summaryElements.forEach(el => {
            const linkEl = el.querySelector('a.summary-link');
            const boldEl = el.querySelector('b');

            // Get the word from the link
            const word = linkEl?.textContent?.trim() || '';

            // Get the meaning from the bold element
            const meaning = boldEl?.textContent?.trim() || '';

            // Get the part of speech (text between link and bold, roughly)
            const fullText = el.textContent || '';
            let pos = '';
            if (word && meaning) {
                const afterWord = fullText.indexOf(word) + word.length;
                const beforeMeaning = fullText.indexOf(meaning);
                if (afterWord > 0 && beforeMeaning > afterWord) {
                    pos = fullText.slice(afterWord, beforeMeaning).trim();
                    // Clean up pos - remove the arrow symbol if present
                    pos = pos.replace(/►/g, '').trim();
                }
            }

            if (pos.includes('grammar') || pos.includes('variants')) {
                return;
            }

            if (word && meaning) {
                summaries.push({ word, pos, meaning });
            }
        });

        // Limit to first 8 results
        return summaries.slice(0, 8);
    }

    _adjustPosition() {
        // Adjust position to keep tooltip within viewport
        this.updateComplete.then(() => {
            const tooltip = this.shadowRoot?.querySelector('.tooltip');
            if (!tooltip) return;

            const rect = tooltip.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            let newX = this.posX + 10;
            let newY = this.posY + 20;

            // Adjust if overflowing right
            if (newX + rect.width > viewportWidth - 20) {
                newX = viewportWidth - rect.width - 20;
            }

            // Adjust if overflowing bottom
            if (newY + rect.height > viewportHeight - 20) {
                newY = this.posY - rect.height - 10;
            }

            // Ensure not off screen
            newX = Math.max(10, newX);
            newY = Math.max(10, newY);

            this.posX = newX;
            this.posY = newY;
        });
    }

    _hideTooltip() {
        this.visible = false;
        this._currentWord = null;
    }

    _handleTooltipMouseEnter() {
        this._isMouseOverTooltip = true;
    }

    _handleTooltipMouseLeave() {
        this._isMouseOverTooltip = false;
    }

    async _playAudio(event) {
        event.stopPropagation();

        // Get the base word without number suffix (e.g., "dhamma 1" -> "dhamma")
        const baseWord = this.word.replace(/\s*\d+$/, '').trim();
        const audioUrl = `https://www.dpdict.net/audio/${encodeURIComponent(baseWord)}?gender=male`;

        try {
            // Create or reuse audio element
            if (!this._audioElement) {
                this._audioElement = new Audio();
            }

            this._audioElement.src = audioUrl;
            this._isPlaying = true;
            this.requestUpdate();

            await this._audioElement.play();

            this._audioElement.onended = () => {
                this._isPlaying = false;
                this.requestUpdate();
            };
        } catch (err) {
            console.error('Audio playback error:', err);
            this._isPlaying = false;
            this.requestUpdate();
        }
    }

    _getDictUrl() {
        return `https://dpdict.net/?q=${encodeURIComponent(this.word)}`;
    }

    render() {
        if (!this.visible) {
            return html``;
        }

        return html`
            <div
                class="tooltip"
                style="left: ${this.posX}px; top: ${this.posY}px;"
                @mouseenter=${this._handleTooltipMouseEnter}
                @mouseleave=${this._handleTooltipMouseLeave}>
                <div class="tooltip__header">
                    <span class="tooltip__word">${this.word}</span>
                    <div style="display: flex; align-items: center;">
                        <button class="tooltip__play ${this._isPlaying ? 'playing' : ''}" @click=${this._playAudio} title="播放发音">
                            <svg viewBox="0 0 24 24">
                                <path d="M8 5v14l11-7z"></path>
                            </svg>
                        </button>
                        <button class="tooltip__close" @click=${this._hideTooltip}>×</button>
                    </div>
                </div>
                <div class="tooltip__content">
                    ${this.loading ? html`
                        <div class="tooltip__loading">Loading...</div>
                    ` : this.error ? html`
                        <div class="tooltip__error">${this.error}</div>
                    ` : this.summaries.length === 0 ? html`
                        <div class="tooltip__not-found">No definition found</div>
                    ` : this.summaries.map(item => html`
                        <div class="tooltip__summary">
                            <span class="tooltip__summary-word">${item.word}</span>
                            <span class="tooltip__summary-pos">${item.pos}</span>
                            <span class="tooltip__summary-meaning">${item.meaning}</span>
                        </div>
                    `)}
                </div>
                ${!this.loading && !this.error && this.summaries.length > 0 ? html`
                    <a class="tooltip__link" href=${this._getDictUrl()} target="_blank">
                        See more in DPDict →
                    </a>
                ` : ''}
            </div>
        `;
    }
}

customElements.define('sc-bilara-pali-lookup', ScBilaraPaliLookup);
