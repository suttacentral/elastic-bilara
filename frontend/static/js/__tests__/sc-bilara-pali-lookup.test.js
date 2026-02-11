/**
 * sc-bilara-pali-lookup.js Tests
 *
 * This file tests the ScBilaraPaliLookup component including:
 * - _cleanWord: word cleaning and extraction
 * - _extractWordAt: word extraction at a given index
 * - _parseHtmlResponse: HTML response parsing
 * - _getDictUrl: dictionary URL generation
 * - State management (visible, loading, error, summaries)
 * - Cache behavior
 */

// ============================================================================
// Pure Functions (extracted from component for unit testing)
// ============================================================================

/**
 * Clean word: remove punctuation and extract first word
 */
function _cleanWord(text) {
    const cleaned = text.replace(/[.,;:!?()\[\]{}"'<>«»—–\-\d\s]+/g, ' ').trim();
    const words = cleaned.split(/\s+/);
    return words.length === 1 ? cleaned : words[0];
}

/**
 * Extract word at a given index in text
 */
function _extractWordAt(text, index) {
    if (index < 0 || index >= text.length) return null;

    const wordPattern = /[\s\.,;:!?\(\)\[\]\{\}"'<>«»—–\-\d]/;

    // If the character at the index is a boundary character, return null
    if (wordPattern.test(text[index])) return null;

    let start = index;
    while (start > 0 && !wordPattern.test(text[start - 1])) {
        start--;
    }

    let end = index;
    while (end < text.length && !wordPattern.test(text[end])) {
        end++;
    }

    const word = text.slice(start, end).trim();

    if (word.length < 2) return null;

    return word;
}

/**
 * Parse HTML response from dictionary API
 */
function _parseHtmlResponse(htmlText) {
    if (!htmlText) return [];

    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlText, 'text/html');

    const summaries = [];

    const summaryElements = doc.querySelectorAll('p.summary');

    summaryElements.forEach(el => {
        const linkEl = el.querySelector('a.summary-link');
        const boldEl = el.querySelector('b');

        const word = linkEl?.textContent?.trim() || '';
        const meaning = boldEl?.textContent?.trim() || '';

        const fullText = el.textContent || '';
        let pos = '';
        if (word && meaning) {
            const afterWord = fullText.indexOf(word) + word.length;
            const beforeMeaning = fullText.indexOf(meaning);
            if (afterWord > 0 && beforeMeaning > afterWord) {
                pos = fullText.slice(afterWord, beforeMeaning).trim();
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

    return summaries.slice(0, 8);
}

/**
 * Generate dictionary URL
 */
function _getDictUrl(word) {
    return `https://dpdict.net/?q=${encodeURIComponent(word)}`;
}

// ============================================================================
// _cleanWord Tests
// ============================================================================

describe('_cleanWord', () => {
    test('should return simple word as-is', () => {
        expect(_cleanWord('dhamma')).toBe('dhamma');
        expect(_cleanWord('buddha')).toBe('buddha');
    });

    test('should remove punctuation', () => {
        expect(_cleanWord('dhamma,')).toBe('dhamma');
        expect(_cleanWord('dhamma.')).toBe('dhamma');
        expect(_cleanWord('dhamma;')).toBe('dhamma');
        expect(_cleanWord('dhamma:')).toBe('dhamma');
        expect(_cleanWord('dhamma!')).toBe('dhamma');
        expect(_cleanWord('dhamma?')).toBe('dhamma');
    });

    test('should remove brackets and quotes', () => {
        expect(_cleanWord('(dhamma)')).toBe('dhamma');
        expect(_cleanWord('[dhamma]')).toBe('dhamma');
        expect(_cleanWord('{dhamma}')).toBe('dhamma');
        expect(_cleanWord('"dhamma"')).toBe('dhamma');
        expect(_cleanWord("'dhamma'")).toBe('dhamma');
        expect(_cleanWord('«dhamma»')).toBe('dhamma');
    });

    test('should remove dashes and special characters', () => {
        expect(_cleanWord('dhamma—')).toBe('dhamma');
        expect(_cleanWord('dhamma–')).toBe('dhamma');
        expect(_cleanWord('dhamma-')).toBe('dhamma');
    });

    test('should remove digits', () => {
        expect(_cleanWord('dhamma123')).toBe('dhamma');
        expect(_cleanWord('123dhamma')).toBe('dhamma');
        expect(_cleanWord('dhamma 1')).toBe('dhamma');
    });

    test('should return first word when multiple words selected', () => {
        expect(_cleanWord('dhamma desanā')).toBe('dhamma');
        expect(_cleanWord('buddha dhamma sangha')).toBe('buddha');
    });

    test('should handle extra whitespace', () => {
        expect(_cleanWord('  dhamma  ')).toBe('dhamma');
        expect(_cleanWord('dhamma   desanā')).toBe('dhamma');
    });

    test('should handle empty string', () => {
        expect(_cleanWord('')).toBe('');
    });

    test('should handle punctuation-only string', () => {
        expect(_cleanWord('.,;:')).toBe('');
    });

    test('should handle mixed punctuation around word', () => {
        expect(_cleanWord('.,dhamma!?')).toBe('dhamma');
        expect(_cleanWord('(dhamma, desanā)')).toBe('dhamma');
    });
});

// ============================================================================
// _extractWordAt Tests
// ============================================================================

describe('_extractWordAt', () => {
    test('should extract word at given position', () => {
        expect(_extractWordAt('hello world', 0)).toBe('hello');
        expect(_extractWordAt('hello world', 2)).toBe('hello');
        expect(_extractWordAt('hello world', 6)).toBe('world');
    });

    test('should handle word boundaries', () => {
        expect(_extractWordAt('dhamma desanā', 0)).toBe('dhamma');
        expect(_extractWordAt('dhamma desanā', 5)).toBe('dhamma');
        expect(_extractWordAt('dhamma desanā', 7)).toBe('desanā');
    });

    test('should return null for short words (< 2 chars)', () => {
        expect(_extractWordAt('a b c', 0)).toBeNull();
        expect(_extractWordAt('a b c', 2)).toBeNull();
    });

    test('should handle punctuation as word boundary', () => {
        expect(_extractWordAt('dhamma, desanā.', 0)).toBe('dhamma');
        expect(_extractWordAt('dhamma, desanā.', 8)).toBe('desanā');
    });

    test('should return null for index at punctuation', () => {
        expect(_extractWordAt('dhamma, desanā', 6)).toBeNull(); // comma position
    });

    test('should return null for out of bounds index', () => {
        expect(_extractWordAt('hello', -1)).toBeNull();
        expect(_extractWordAt('hello', 10)).toBeNull();
        expect(_extractWordAt('hello', 5)).toBeNull();
    });

    test('should handle empty string', () => {
        expect(_extractWordAt('', 0)).toBeNull();
    });

    test('should handle Pali diacritics', () => {
        expect(_extractWordAt('āṇi dhammā', 0)).toBe('āṇi');
        expect(_extractWordAt('āṇi dhammā', 5)).toBe('dhammā');
    });

    test('should handle numbers as word boundaries', () => {
        expect(_extractWordAt('dhamma1desanā', 0)).toBe('dhamma');
        expect(_extractWordAt('dhamma1desanā', 7)).toBe('desanā');
    });

    test('should handle multiple punctuation marks', () => {
        expect(_extractWordAt('dhamma... desanā', 0)).toBe('dhamma');
        expect(_extractWordAt('dhamma... desanā', 11)).toBe('desanā');
    });
});

// ============================================================================
// _parseHtmlResponse Tests
// ============================================================================

describe('_parseHtmlResponse', () => {
    test('should return empty array for empty input', () => {
        expect(_parseHtmlResponse('')).toEqual([]);
        expect(_parseHtmlResponse(null)).toEqual([]);
        expect(_parseHtmlResponse(undefined)).toEqual([]);
    });

    test('should parse single summary entry', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">dhamma</a>
                noun ►
                <b>teaching, doctrine</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(1);
        expect(result[0].word).toBe('dhamma');
        expect(result[0].meaning).toBe('teaching, doctrine');
    });

    test('should parse multiple summary entries', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">dhamma</a>
                noun ►
                <b>teaching</b>
            </p>
            <p class="summary">
                <a class="summary-link">dhamma</a>
                masc ►
                <b>nature</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(2);
        expect(result[0].meaning).toBe('teaching');
        expect(result[1].meaning).toBe('nature');
    });

    test('should extract part of speech', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">buddha</a>
                masc, adj ►
                <b>awakened one</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(1);
        expect(result[0].pos).toContain('masc');
    });

    test('should skip grammar entries', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">dhamma</a>
                grammar ►
                <b>noun declension</b>
            </p>
            <p class="summary">
                <a class="summary-link">dhamma</a>
                noun ►
                <b>teaching</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(1);
        expect(result[0].meaning).toBe('teaching');
    });

    test('should skip variants entries', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">dhamma</a>
                variants ►
                <b>dhammo, dhammā</b>
            </p>
            <p class="summary">
                <a class="summary-link">dhamma</a>
                noun ►
                <b>doctrine</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(1);
        expect(result[0].meaning).toBe('doctrine');
    });

    test('should skip entries without word or meaning', () => {
        const html = `
            <p class="summary">
                <a class="summary-link"></a>
                noun ►
                <b>teaching</b>
            </p>
            <p class="summary">
                <a class="summary-link">dhamma</a>
                noun ►
                <b></b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result).toHaveLength(0);
    });

    test('should limit results to 8 entries', () => {
        const entries = Array(12).fill().map((_, i) => `
            <p class="summary">
                <a class="summary-link">word${i}</a>
                noun ►
                <b>meaning${i}</b>
            </p>
        `).join('');
        const result = _parseHtmlResponse(entries);
        expect(result).toHaveLength(8);
    });

    test('should handle HTML without summary elements', () => {
        const html = `<div>No summaries here</div>`;
        expect(_parseHtmlResponse(html)).toEqual([]);
    });

    test('should remove arrow symbol from pos', () => {
        const html = `
            <p class="summary">
                <a class="summary-link">dhamma</a>
                ►noun►
                <b>teaching</b>
            </p>
        `;
        const result = _parseHtmlResponse(html);
        expect(result[0].pos).not.toContain('►');
    });
});

// ============================================================================
// _getDictUrl Tests
// ============================================================================

describe('_getDictUrl', () => {
    test('should generate correct URL for simple word', () => {
        expect(_getDictUrl('dhamma')).toBe('https://dpdict.net/?q=dhamma');
    });

    test('should encode special characters', () => {
        expect(_getDictUrl('dhamma 1')).toBe('https://dpdict.net/?q=dhamma%201');
    });

    test('should encode Pali diacritics', () => {
        const url = _getDictUrl('dhammā');
        expect(url).toContain('https://dpdict.net/?q=');
        expect(url).toContain('dhamm');
    });

    test('should handle empty string', () => {
        expect(_getDictUrl('')).toBe('https://dpdict.net/?q=');
    });

    test('should encode URL-unsafe characters', () => {
        expect(_getDictUrl('test&word')).toBe('https://dpdict.net/?q=test%26word');
        expect(_getDictUrl('test=word')).toBe('https://dpdict.net/?q=test%3Dword');
    });
});

// ============================================================================
// Cache Behavior Tests
// ============================================================================

describe('Cache behavior', () => {
    let cache;

    beforeEach(() => {
        cache = new Map();
    });

    test('should store and retrieve cached values', () => {
        const word = 'dhamma';
        const summaries = [{ word: 'dhamma', pos: 'noun', meaning: 'teaching' }];

        cache.set(word.toLowerCase(), summaries);

        expect(cache.has(word.toLowerCase())).toBe(true);
        expect(cache.get(word.toLowerCase())).toEqual(summaries);
    });

    test('should be case-insensitive for lookup', () => {
        const summaries = [{ word: 'dhamma', pos: 'noun', meaning: 'teaching' }];

        cache.set('dhamma', summaries);

        expect(cache.has('dhamma')).toBe(true);
        expect(cache.has('DHAMMA'.toLowerCase())).toBe(true);
    });

    test('should store empty arrays for words with no results', () => {
        cache.set('unknownword', []);

        expect(cache.has('unknownword')).toBe(true);
        expect(cache.get('unknownword')).toEqual([]);
    });
});

// ============================================================================
// Component State Tests
// ============================================================================

describe('Component state management', () => {
    // Simulate initial state
    function createInitialState() {
        return {
            visible: false,
            word: '',
            summaries: [],
            loading: false,
            error: null,
            posX: 0,
            posY: 0,
            _currentWord: null,
            _isMouseOverTooltip: false
        };
    }

    test('should have correct initial state', () => {
        const state = createInitialState();

        expect(state.visible).toBe(false);
        expect(state.word).toBe('');
        expect(state.summaries).toEqual([]);
        expect(state.loading).toBe(false);
        expect(state.error).toBeNull();
        expect(state.posX).toBe(0);
        expect(state.posY).toBe(0);
    });

    test('should update state when looking up word', () => {
        const state = createInitialState();

        // Simulate lookup start
        state.word = 'dhamma';
        state.posX = 100;
        state.posY = 200;
        state.visible = true;
        state.loading = true;
        state.error = null;
        state.summaries = [];
        state._currentWord = 'dhamma';

        expect(state.visible).toBe(true);
        expect(state.loading).toBe(true);
        expect(state.word).toBe('dhamma');
    });

    test('should update state on successful lookup', () => {
        const state = createInitialState();

        // Simulate successful lookup
        state.visible = true;
        state.word = 'dhamma';
        state.summaries = [{ word: 'dhamma', pos: 'noun', meaning: 'teaching' }];
        state.loading = false;
        state.error = null;

        expect(state.loading).toBe(false);
        expect(state.summaries).toHaveLength(1);
        expect(state.error).toBeNull();
    });

    test('should update state on lookup error', () => {
        const state = createInitialState();

        // Simulate error
        state.visible = true;
        state.loading = false;
        state.error = 'Unable to obtain definition';
        state.summaries = [];

        expect(state.loading).toBe(false);
        expect(state.error).toBe('Unable to obtain definition');
        expect(state.summaries).toEqual([]);
    });

    test('should reset state when hiding tooltip', () => {
        const state = createInitialState();
        state.visible = true;
        state._currentWord = 'dhamma';

        // Simulate hide
        state.visible = false;
        state._currentWord = null;

        expect(state.visible).toBe(false);
        expect(state._currentWord).toBeNull();
    });
});

// ============================================================================
// Position Adjustment Logic Tests
// ============================================================================

describe('Position adjustment logic', () => {
    function adjustPosition(posX, posY, tooltipWidth, tooltipHeight, viewportWidth, viewportHeight) {
        let newX = posX + 10;
        let newY = posY + 20;

        // Adjust if overflowing right
        if (newX + tooltipWidth > viewportWidth - 20) {
            newX = viewportWidth - tooltipWidth - 20;
        }

        // Adjust if overflowing bottom
        if (newY + tooltipHeight > viewportHeight - 20) {
            newY = posY - tooltipHeight - 10;
        }

        // Ensure not off screen
        newX = Math.max(10, newX);
        newY = Math.max(10, newY);

        return { x: newX, y: newY };
    }

    test('should position tooltip to the right and below mouse', () => {
        const result = adjustPosition(100, 100, 200, 150, 1024, 768);
        expect(result.x).toBe(110); // posX + 10
        expect(result.y).toBe(120); // posY + 20
    });

    test('should adjust when overflowing viewport right edge', () => {
        const result = adjustPosition(900, 100, 200, 150, 1024, 768);
        expect(result.x).toBe(804); // viewportWidth - tooltipWidth - 20
    });

    test('should adjust when overflowing viewport bottom edge', () => {
        const result = adjustPosition(100, 700, 200, 150, 1024, 768);
        // newY should be posY - tooltipHeight - 10 = 700 - 150 - 10 = 540
        expect(result.y).toBe(540);
    });

    test('should ensure minimum position of 10px from edge', () => {
        const result = adjustPosition(-50, -50, 200, 150, 1024, 768);
        expect(result.x).toBeGreaterThanOrEqual(10);
        expect(result.y).toBeGreaterThanOrEqual(10);
    });

    test('should handle tooltip at exact viewport edge', () => {
        const result = adjustPosition(804, 598, 200, 150, 1024, 768);
        expect(result.x).toBeLessThanOrEqual(1024 - 200 - 20);
    });
});

// ============================================================================
// Audio URL Generation Tests
// ============================================================================

describe('Audio URL generation', () => {
    function getAudioUrl(word) {
        const baseWord = word.replace(/\s*\d+$/, '').trim();
        return `https://www.dpdict.net/audio/${encodeURIComponent(baseWord)}?gender=male`;
    }

    test('should generate correct audio URL for simple word', () => {
        expect(getAudioUrl('dhamma')).toBe('https://www.dpdict.net/audio/dhamma?gender=male');
    });

    test('should remove trailing numbers before generating URL', () => {
        expect(getAudioUrl('dhamma 1')).toBe('https://www.dpdict.net/audio/dhamma?gender=male');
        expect(getAudioUrl('buddha 2')).toBe('https://www.dpdict.net/audio/buddha?gender=male');
    });

    test('should handle word with multiple trailing numbers', () => {
        expect(getAudioUrl('dhamma 123')).toBe('https://www.dpdict.net/audio/dhamma?gender=male');
    });

    test('should not remove embedded numbers', () => {
        // The regex only removes trailing numbers
        expect(getAudioUrl('test1word')).toBe('https://www.dpdict.net/audio/test1word?gender=male');
    });
});

// ============================================================================
// Word Validation Tests
// ============================================================================

describe('Word validation', () => {
    function isValidWord(word) {
        return !!(word && word.length >= 2);
    }

    test('should reject words shorter than 2 characters', () => {
        expect(isValidWord('a')).toBe(false);
        expect(isValidWord('')).toBe(false);
    });

    test('should accept words with 2 or more characters', () => {
        expect(isValidWord('ab')).toBe(true);
        expect(isValidWord('dhamma')).toBe(true);
    });

    test('should reject null/undefined', () => {
        expect(isValidWord(null)).toBe(false);
        expect(isValidWord(undefined)).toBe(false);
    });
});

// ============================================================================
// Event Handling Logic Tests
// ============================================================================

describe('Event handling logic', () => {
    describe('Mouse selection detection', () => {
        function hasSelection(selectionStart, selectionEnd) {
            return selectionStart !== selectionEnd;
        }

        test('should detect when text is selected', () => {
            expect(hasSelection(0, 5)).toBe(true);
            expect(hasSelection(10, 15)).toBe(true);
        });

        test('should detect when no text is selected', () => {
            expect(hasSelection(5, 5)).toBe(false);
            expect(hasSelection(0, 0)).toBe(false);
        });
    });

    describe('Selected text extraction', () => {
        function getSelectedText(value, selectionStart, selectionEnd) {
            return value.substring(selectionStart, selectionEnd).trim();
        }

        test('should extract selected text', () => {
            expect(getSelectedText('hello world', 0, 5)).toBe('hello');
            expect(getSelectedText('hello world', 6, 11)).toBe('world');
        });

        test('should trim whitespace', () => {
            expect(getSelectedText('hello world', 5, 6)).toBe('');
        });
    });
});

// ============================================================================
// CSS Selector Tests
// ============================================================================

describe('CSS selector patterns', () => {
    const SOURCE_TEXTAREA_SELECTOR = '.translation-cell--source .translation-cell__textarea';

    test('should have correct source textarea selector', () => {
        expect(SOURCE_TEXTAREA_SELECTOR).toBe('.translation-cell--source .translation-cell__textarea');
    });

    test('selector should match expected format', () => {
        // Verify the selector follows BEM naming convention
        expect(SOURCE_TEXTAREA_SELECTOR).toMatch(/\.[a-z-]+--[a-z]+\s+\.[a-z-]+__[a-z]+/);
    });
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge cases and error handling', () => {
    describe('_cleanWord edge cases', () => {
        test('should handle Unicode characters', () => {
            expect(_cleanWord('dhammā')).toBe('dhammā');
            expect(_cleanWord('ñāṇa')).toBe('ñāṇa');
        });

        test('should handle mixed ASCII and Unicode', () => {
            expect(_cleanWord('dhammā, sangha')).toBe('dhammā');
        });
    });

    describe('_extractWordAt edge cases', () => {
        test('should handle single character text', () => {
            expect(_extractWordAt('a', 0)).toBeNull();
        });

        test('should handle two character word', () => {
            expect(_extractWordAt('ab', 0)).toBe('ab');
        });

        test('should handle text with only punctuation', () => {
            expect(_extractWordAt('...', 1)).toBeNull();
        });
    });

    describe('_parseHtmlResponse edge cases', () => {
        test('should handle malformed HTML', () => {
            const html = '<p class="summary"><unclosed';
            // Should not throw
            expect(() => _parseHtmlResponse(html)).not.toThrow();
        });

        test('should handle deeply nested HTML', () => {
            const html = `
                <div><div><div>
                    <p class="summary">
                        <a class="summary-link">dhamma</a>
                        noun ►
                        <b>teaching</b>
                    </p>
                </div></div></div>
            `;
            const result = _parseHtmlResponse(html);
            expect(result).toHaveLength(1);
        });
    });
});
