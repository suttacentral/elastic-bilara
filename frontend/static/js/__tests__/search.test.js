/**
 * Search Tests
 *
 * This file tests the search.js functionality including:
 * - State initialization
 * - Project suggestions (updateSuggestions)
 * - Project selection (toggleSelectedProjects)
 * - Query parameter construction (constructQueryParams)
 * - UID prefix extraction (getPrefixFromUid)
 * - Editable check (canEditMuid)
 * - Edit permissions fetching (_fetchEditPermissions)
 * - Result entries building (_buildResultEntries)
 * - Search result focus snapshotting (searchResultFocus)
 * - Search result input updating (searchResultInput)
 * - Search result saving (searchResultSave)
 * - Search-and-replace: replaceSegment, submitReplacement
 * - Highlight: getHighlightedSegment, _escapeHtml
 */

// ============================================================================
// Mock Setup
// ============================================================================

global.fetch = jest.fn();
global.requestWithTokenRetry = jest.fn();
global.displayBadge = jest.fn();
global.BadgeStatus = { PENDING: 'PENDING', COMMITTED: 'COMMITTED', ERROR: 'ERROR' };

// ============================================================================
// Helper function to create mock search instance
// ============================================================================

function createMockSearch(overrides = {}) {
    const instance = {
        closed: true,
        projects: [],
        suggestions: [],
        projectQuery: '',
        selectedProjects: {},
        size: 100,
        page: 0,
        currentPage: 0,
        isNextPage: false,
        fields: { uid: '' },
        results: {},
        editableMusids: {},
        originalValues: {},
        resultEntries: [],
        // Search-and-replace support
        replacementText: '',
        replacedItems: {},
        submittedItems: {},

        updateSuggestions() {
            if (!this.projectQuery) {
                this.suggestions = [];
                return;
            }
            this.suggestions = this.projects.filter(project =>
                project.toLowerCase().startsWith(this.projectQuery.toLowerCase()),
            );
        },

        toggleSelectedProjects(project) {
            this.selectedProjects[project] = !this.selectedProjects[project];
            if (project in this.fields) {
                return delete this.fields[project];
            }
            this.fields[project] = '';
        },

        constructQueryParams() {
            const params = new URLSearchParams();
            this.size = this.size <= 100 ? this.size : 10;
            params.set('size', this.size);
            params.set('page', this.currentPage);
            for (const [key, value] of Object.entries(this.fields)) {
                params.set(key, value);
            }
            return params;
        },

        getPrefixFromUid(uid) {
            return uid.split(':')[0];
        },

        canEditMuid(muid, isAdmin) {
            return !!isAdmin && !!this.editableMusids[muid];
        },

        async _fetchEditPermissions(results) {
            const muids = new Set();
            for (const segments of Object.values(results)) {
                for (const muid of Object.keys(segments)) {
                    if (!(muid in this.editableMusids)) {
                        muids.add(muid);
                    }
                }
            }
            const promises = [...muids].map(async (muid) => {
                try {
                    const resp = await requestWithTokenRetry(`projects/${muid}/can-edit/`);
                    const data = await resp.json();
                    this.editableMusids[muid] = !!data.can_edit;
                } catch {
                    this.editableMusids[muid] = false;
                }
            });
            await Promise.all(promises);
        },

        _buildResultEntries() {
            this.resultEntries = Object.entries(this.results).map(([uid, muidSegments]) => ({
                uid,
                segments: Object.entries(muidSegments).map(([muid, segment]) => ({
                    muid,
                    segment,
                })),
            }));
        },

        searchResultFocus(uid, muid) {
            const key = uid + '::' + muid;
            if (!(key in this.originalValues)) {
                this.originalValues[key] = this.results[uid]?.[muid] || '';
            }
        },

        searchResultInput(uid, muid, value) {
            if (this.results[uid]) {
                this.results[uid][muid] = value;
            }
            const entry = this.resultEntries.find(e => e.uid === uid);
            if (entry) {
                const seg = entry.segments.find(s => s.muid === muid);
                if (seg) seg.segment = value;
            }
        },

        async searchResultSave(uid, muid, currentValue) {
            const key = uid + '::' + muid;
            const original = this.originalValues[key];
            if (currentValue === original) return;
            this.originalValues[key] = currentValue;

            const prefix = this.getPrefixFromUid(uid);
            const badgeId = `search-badge-${muid}-${uid}`;

            try {
                const textarea = document.getElementById(`search-textarea-${muid}-${uid}`);
                if (textarea) {
                    let badge = document.getElementById(badgeId);
                    if (!badge) {
                        badge = document.createElement('sc-bilara-translation-edit-status');
                        badge.id = badgeId;
                        badge.className = 'search__results-status';
                        textarea.parentElement.appendChild(badge);
                    }
                }

                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${prefix}/`, {
                    credentials: 'include',
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ [uid]: currentValue }),
                });
                await response.json();
                displayBadge(badgeId, BadgeStatus.COMMITTED);
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw new Error(error);
            }
        },

        /** Return HTML with search/replacement keywords wrapped in <mark> tags */
        getHighlightedSegment(segment, uid, muid) {
            if (!segment) return '';
            const key = uid + '::' + muid;
            let term;
            if (this.replacedItems[key]) {
                term = this.replacementText;
            } else {
                term = this.fields[muid];
                if (!term) {
                    for (const [k, v] of Object.entries(this.fields)) {
                        if (k !== 'uid' && v) { term = v; break; }
                    }
                }
            }
            const escaped = this._escapeHtml(segment);
            if (!term) return escaped;
            const escapedTerm = this._escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedTerm, 'gi');
            return escaped.replace(regex, '<mark class="search__highlight">$&</mark>');
        },
        _escapeHtml(text) {
            const el = document.createElement('span');
            el.textContent = text;
            return el.innerHTML;
        },

        /** Replace search keyword in a single segment with replacementText */
        replaceSegment(uid, muid, seg) {
            let searchTerm = this.fields[muid];
            if (!searchTerm) {
                for (const [key, value] of Object.entries(this.fields)) {
                    if (key !== 'uid' && value) {
                        searchTerm = value;
                        break;
                    }
                }
            }
            if (!searchTerm) return;

            const newValue = seg.segment.replaceAll(searchTerm, this.replacementText);
            seg.segment = newValue;
            if (this.results[uid]) {
                this.results[uid][muid] = newValue;
            }
            this.replacedItems[uid + '::' + muid] = true;
        },

        /** Submit a single replaced segment to the server */
        async submitReplacement(uid, muid, currentValue) {
            const key = uid + '::' + muid;
            const prefix = this.getPrefixFromUid(uid);
            const badgeId = `search-badge-${muid}-${uid}`;

            try {
                const textarea = document.getElementById(`search-textarea-${muid}-${uid}`);
                if (textarea) {
                    let badge = document.getElementById(badgeId);
                    if (!badge) {
                        badge = document.createElement('sc-bilara-translation-edit-status');
                        badge.id = badgeId;
                        badge.className = 'search__results-status';
                        textarea.parentElement.appendChild(badge);
                    }
                }

                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${prefix}/`, {
                    credentials: 'include',
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ [uid]: currentValue }),
                });
                await response.json();
                displayBadge(badgeId, BadgeStatus.COMMITTED);
                this.submittedItems[key] = true;
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw new Error(error);
            }
        },

        scrollTop(selector) {
            document.querySelector(selector).scrollTop = 0;
        },

        ...overrides,
    };
    return instance;
}

// ============================================================================
// State Initialization Tests
// ============================================================================

describe('Search State Initialization', () => {
    test('should have correct default state', () => {
        const s = createMockSearch();
        expect(s.closed).toBe(true);
        expect(s.projects).toEqual([]);
        expect(s.suggestions).toEqual([]);
        expect(s.projectQuery).toBe('');
        expect(s.selectedProjects).toEqual({});
        expect(s.size).toBe(100);
        expect(s.page).toBe(0);
        expect(s.currentPage).toBe(0);
        expect(s.isNextPage).toBe(false);
    });

    test('should have correct default fields', () => {
        const s = createMockSearch();
        expect(s.fields).toEqual({ uid: '' });
    });

    test('should have correct default editable results state', () => {
        const s = createMockSearch();
        expect(s.editableMusids).toEqual({});
        expect(s.originalValues).toEqual({});
        expect(s.resultEntries).toEqual([]);
        expect(s.results).toEqual({});
    });

    test('should have correct default search-and-replace state', () => {
        const s = createMockSearch();
        expect(s.replacementText).toBe('');
        expect(s.replacedItems).toEqual({});
        expect(s.submittedItems).toEqual({});
    });
});

// ============================================================================
// updateSuggestions Tests
// ============================================================================

describe('updateSuggestions', () => {
    test('should return empty suggestions when projectQuery is empty', () => {
        const s = createMockSearch();
        s.projects = ['translation-en-sujato', 'root-pli-ms'];
        s.projectQuery = '';
        s.updateSuggestions();
        expect(s.suggestions).toEqual([]);
    });

    test('should filter projects by prefix match', () => {
        const s = createMockSearch();
        s.projects = ['translation-en-sujato', 'translation-de-sabbamitta', 'root-pli-ms'];
        s.projectQuery = 'trans';
        s.updateSuggestions();
        expect(s.suggestions).toEqual(['translation-en-sujato', 'translation-de-sabbamitta']);
    });

    test('should be case-insensitive', () => {
        const s = createMockSearch();
        s.projects = ['translation-en-sujato', 'Root-pli-ms'];
        s.projectQuery = 'ROOT';
        s.updateSuggestions();
        expect(s.suggestions).toEqual(['Root-pli-ms']);
    });

    test('should return no suggestions when nothing matches', () => {
        const s = createMockSearch();
        s.projects = ['translation-en-sujato'];
        s.projectQuery = 'xyz';
        s.updateSuggestions();
        expect(s.suggestions).toEqual([]);
    });

    test('should match from start of string only', () => {
        const s = createMockSearch();
        s.projects = ['translation-en-sujato', 'root-pli-ms'];
        s.projectQuery = 'en';
        s.updateSuggestions();
        expect(s.suggestions).toEqual([]);
    });
});

// ============================================================================
// toggleSelectedProjects Tests
// ============================================================================

describe('toggleSelectedProjects', () => {
    test('should add project to selectedProjects and fields', () => {
        const s = createMockSearch();
        s.toggleSelectedProjects('translation-en-sujato');
        expect(s.selectedProjects['translation-en-sujato']).toBe(true);
        expect(s.fields['translation-en-sujato']).toBe('');
    });

    test('should remove project from fields on second toggle', () => {
        const s = createMockSearch();
        s.toggleSelectedProjects('translation-en-sujato');
        expect('translation-en-sujato' in s.fields).toBe(true);
        s.toggleSelectedProjects('translation-en-sujato');
        expect('translation-en-sujato' in s.fields).toBe(false);
    });

    test('should handle uid field specially (already in fields)', () => {
        const s = createMockSearch();
        // 'uid' is already in fields by default
        s.toggleSelectedProjects('uid');
        expect(s.selectedProjects['uid']).toBe(true);
        expect('uid' in s.fields).toBe(false); // deleted because it was in fields
    });

    test('should handle multiple projects independently', () => {
        const s = createMockSearch();
        s.toggleSelectedProjects('proj-a');
        s.toggleSelectedProjects('proj-b');
        expect(s.fields['proj-a']).toBe('');
        expect(s.fields['proj-b']).toBe('');
    });
});

// ============================================================================
// constructQueryParams Tests
// ============================================================================

describe('constructQueryParams', () => {
    test('should include size and page', () => {
        const s = createMockSearch();
        s.size = 50;
        s.currentPage = 2;
        const params = s.constructQueryParams();
        expect(params.get('size')).toBe('50');
        expect(params.get('page')).toBe('2');
    });

    test('should include all fields', () => {
        const s = createMockSearch();
        s.fields = { uid: 'mn1', 'translation-en-sujato': 'hello' };
        const params = s.constructQueryParams();
        expect(params.get('uid')).toBe('mn1');
        expect(params.get('translation-en-sujato')).toBe('hello');
    });

    test('should cap size to 10 when over 100', () => {
        const s = createMockSearch();
        s.size = 200;
        const params = s.constructQueryParams();
        expect(params.get('size')).toBe('10');
        expect(s.size).toBe(10);
    });

    test('should allow size up to 100', () => {
        const s = createMockSearch();
        s.size = 100;
        const params = s.constructQueryParams();
        expect(params.get('size')).toBe('100');
    });

    test('should return URLSearchParams instance', () => {
        const s = createMockSearch();
        const params = s.constructQueryParams();
        expect(params).toBeInstanceOf(URLSearchParams);
    });
});

// ============================================================================
// getPrefixFromUid Tests
// ============================================================================

describe('getPrefixFromUid', () => {
    test('should extract prefix from simple uid', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('mn1:1.1')).toBe('mn1');
    });

    test('should extract prefix from compound uid', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('an1.1:0.1')).toBe('an1.1');
    });

    test('should extract prefix from uid with multiple colons', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('dn1:1.1:2')).toBe('dn1');
    });

    test('should return entire string if no colon', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('mn1')).toBe('mn1');
    });

    test('should handle empty string', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('')).toBe('');
    });

    test('should handle uid starting with colon', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid(':1.1')).toBe('');
    });
});

// ============================================================================
// canEditMuid Tests
// ============================================================================

describe('canEditMuid', () => {
    test('should return true when isAdmin and muid is editable', () => {
        const s = createMockSearch();
        s.editableMusids['translation-en-sujato'] = true;
        expect(s.canEditMuid('translation-en-sujato', true)).toBe(true);
    });

    test('should return false when not admin', () => {
        const s = createMockSearch();
        s.editableMusids['translation-en-sujato'] = true;
        expect(s.canEditMuid('translation-en-sujato', false)).toBe(false);
    });

    test('should return false when muid is not editable', () => {
        const s = createMockSearch();
        s.editableMusids['translation-en-sujato'] = false;
        expect(s.canEditMuid('translation-en-sujato', true)).toBe(false);
    });

    test('should return false when muid is not in cache', () => {
        const s = createMockSearch();
        expect(s.canEditMuid('unknown-muid', true)).toBe(false);
    });

    test('should return false when isAdmin is null/undefined', () => {
        const s = createMockSearch();
        s.editableMusids['translation-en-sujato'] = true;
        expect(s.canEditMuid('translation-en-sujato', null)).toBe(false);
        expect(s.canEditMuid('translation-en-sujato', undefined)).toBe(false);
    });

    test('should return false when both are falsy', () => {
        const s = createMockSearch();
        expect(s.canEditMuid('x', false)).toBe(false);
    });
});

// ============================================================================
// _fetchEditPermissions Tests
// ============================================================================

describe('_fetchEditPermissions', () => {
    beforeEach(() => {
        requestWithTokenRetry.mockReset();
    });

    test('should fetch permissions for all unique muids', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({ can_edit: true }),
        });

        const results = {
            'mn1:1.1': { 'translation-en-sujato': 'text1', 'root-pli-ms': 'pali1' },
            'mn1:1.2': { 'translation-en-sujato': 'text2', 'root-pli-ms': 'pali2' },
        };

        await s._fetchEditPermissions(results);

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(2);
        expect(requestWithTokenRetry).toHaveBeenCalledWith('projects/translation-en-sujato/can-edit/');
        expect(requestWithTokenRetry).toHaveBeenCalledWith('projects/root-pli-ms/can-edit/');
        expect(s.editableMusids['translation-en-sujato']).toBe(true);
        expect(s.editableMusids['root-pli-ms']).toBe(true);
    });

    test('should skip already-cached muids', async () => {
        const s = createMockSearch();
        s.editableMusids['root-pli-ms'] = false; // already cached
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({ can_edit: true }),
        });

        const results = {
            'mn1:1.1': { 'translation-en-sujato': 'text1', 'root-pli-ms': 'pali1' },
        };

        await s._fetchEditPermissions(results);

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(requestWithTokenRetry).toHaveBeenCalledWith('projects/translation-en-sujato/can-edit/');
        // root-pli-ms should remain unchanged
        expect(s.editableMusids['root-pli-ms']).toBe(false);
    });

    test('should set muid to false on fetch error', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockRejectedValue(new Error('Network error'));

        const results = {
            'mn1:1.1': { 'translation-en-sujato': 'text' },
        };

        await s._fetchEditPermissions(results);

        expect(s.editableMusids['translation-en-sujato']).toBe(false);
    });

    test('should handle empty results', async () => {
        const s = createMockSearch();
        await s._fetchEditPermissions({});
        expect(requestWithTokenRetry).not.toHaveBeenCalled();
    });

    test('should handle can_edit false response', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({ can_edit: false }),
        });

        const results = {
            'mn1:1.1': { 'translation-en-sujato': 'text' },
        };

        await s._fetchEditPermissions(results);

        expect(s.editableMusids['translation-en-sujato']).toBe(false);
    });
});

// ============================================================================
// _buildResultEntries Tests
// ============================================================================

describe('_buildResultEntries', () => {
    test('should build entries from results', () => {
        const s = createMockSearch();
        s.results = {
            'mn1:1.1': { 'translation-en-sujato': 'Hello', 'root-pli-ms': 'Namo' },
            'mn1:1.2': { 'translation-en-sujato': 'World' },
        };

        s._buildResultEntries();

        expect(s.resultEntries).toHaveLength(2);
        expect(s.resultEntries[0].uid).toBe('mn1:1.1');
        expect(s.resultEntries[0].segments).toHaveLength(2);
        expect(s.resultEntries[0].segments[0]).toEqual({ muid: 'translation-en-sujato', segment: 'Hello' });
        expect(s.resultEntries[0].segments[1]).toEqual({ muid: 'root-pli-ms', segment: 'Namo' });
        expect(s.resultEntries[1].uid).toBe('mn1:1.2');
        expect(s.resultEntries[1].segments).toHaveLength(1);
    });

    test('should handle empty results', () => {
        const s = createMockSearch();
        s.results = {};
        s._buildResultEntries();
        expect(s.resultEntries).toEqual([]);
    });

    test('should handle uid with empty segments', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': {} };
        s._buildResultEntries();
        expect(s.resultEntries).toHaveLength(1);
        expect(s.resultEntries[0].segments).toEqual([]);
    });

    test('should overwrite previous resultEntries', () => {
        const s = createMockSearch();
        s.resultEntries = [{ uid: 'old', segments: [] }];
        s.results = { 'mn1:1.1': { 'root-pli-ms': 'text' } };
        s._buildResultEntries();
        expect(s.resultEntries).toHaveLength(1);
        expect(s.resultEntries[0].uid).toBe('mn1:1.1');
    });
});

// ============================================================================
// searchResultFocus Tests
// ============================================================================

describe('searchResultFocus', () => {
    test('should snapshot current value on first focus', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'Hello' } };

        s.searchResultFocus('mn1:1.1', 'translation-en-sujato');

        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('Hello');
    });

    test('should not overwrite existing snapshot on subsequent focus', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'Modified' } };
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'Original';

        s.searchResultFocus('mn1:1.1', 'translation-en-sujato');

        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('Original');
    });

    test('should default to empty string if result not found', () => {
        const s = createMockSearch();
        s.results = {};

        s.searchResultFocus('mn1:1.1', 'translation-en-sujato');

        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('');
    });

    test('should handle different uid/muid combinations independently', () => {
        const s = createMockSearch();
        s.results = {
            'mn1:1.1': { 'translation-en-sujato': 'A', 'root-pli-ms': 'B' },
        };

        s.searchResultFocus('mn1:1.1', 'translation-en-sujato');
        s.searchResultFocus('mn1:1.1', 'root-pli-ms');

        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('A');
        expect(s.originalValues['mn1:1.1::root-pli-ms']).toBe('B');
    });
});

// ============================================================================
// searchResultInput Tests
// ============================================================================

describe('searchResultInput', () => {
    test('should update results in-memory', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'old' } };
        s.resultEntries = [{ uid: 'mn1:1.1', segments: [{ muid: 'translation-en-sujato', segment: 'old' }] }];

        s.searchResultInput('mn1:1.1', 'translation-en-sujato', 'new');

        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('new');
    });

    test('should update reactive resultEntries', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'old' } };
        s.resultEntries = [{ uid: 'mn1:1.1', segments: [{ muid: 'translation-en-sujato', segment: 'old' }] }];

        s.searchResultInput('mn1:1.1', 'translation-en-sujato', 'new');

        expect(s.resultEntries[0].segments[0].segment).toBe('new');
    });

    test('should not throw when uid not in results', () => {
        const s = createMockSearch();
        s.results = {};
        s.resultEntries = [];

        expect(() => s.searchResultInput('unknown:1.1', 'muid', 'value')).not.toThrow();
    });

    test('should not throw when muid not in entry segments', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'text' } };
        s.resultEntries = [{ uid: 'mn1:1.1', segments: [{ muid: 'translation-en-sujato', segment: 'text' }] }];

        expect(() => s.searchResultInput('mn1:1.1', 'unknown-muid', 'value')).not.toThrow();
    });

    test('should handle empty string value', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'old' } };
        s.resultEntries = [{ uid: 'mn1:1.1', segments: [{ muid: 'translation-en-sujato', segment: 'old' }] }];

        s.searchResultInput('mn1:1.1', 'translation-en-sujato', '');

        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('');
        expect(s.resultEntries[0].segments[0].segment).toBe('');
    });
});

// ============================================================================
// searchResultSave Tests
// ============================================================================

describe('searchResultSave', () => {
    beforeEach(() => {
        requestWithTokenRetry.mockReset();
        displayBadge.mockReset();
        document.getElementById = jest.fn().mockReturnValue(null);
    });

    test('should skip save when value unchanged', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'same';

        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'same');

        expect(requestWithTokenRetry).not.toHaveBeenCalled();
        expect(displayBadge).not.toHaveBeenCalled();
    });

    test('should call API with correct params when value changed', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'new');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/translation-en-sujato/mn1/',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ 'mn1:1.1': 'new' }),
            }),
        );
    });

    test('should display PENDING badge then COMMITTED on success', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'new');

        const badgeId = 'search-badge-translation-en-sujato-mn1:1.1';
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.PENDING);
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.COMMITTED);
    });

    test('should display ERROR badge on failure', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';
        requestWithTokenRetry.mockRejectedValue(new Error('Network error'));

        await expect(
            s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'new'),
        ).rejects.toThrow();

        const badgeId = 'search-badge-translation-en-sujato-mn1:1.1';
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.PENDING);
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.ERROR);
    });

    test('should update originalValues after save', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'new');

        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('new');
    });

    test('should use correct prefix for compound uid', async () => {
        const s = createMockSearch();
        s.originalValues['an1.1:0.1::translation-en-sujato'] = 'old';
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.searchResultSave('an1.1:0.1', 'translation-en-sujato', 'new');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/translation-en-sujato/an1.1/',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ 'an1.1:0.1': 'new' }),
            }),
        );
    });

    test('should create badge element if textarea exists but badge does not', async () => {
        const s = createMockSearch();
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';

        const mockParent = { appendChild: jest.fn() };
        const mockTextarea = { parentElement: mockParent };
        let callCount = 0;

        document.getElementById = jest.fn((id) => {
            if (id.startsWith('search-textarea-')) return mockTextarea;
            if (id.startsWith('search-badge-')) {
                // First call returns null (badge doesn't exist), subsequent calls return the badge
                return callCount++ === 0 ? null : { id };
            }
            return null;
        });
        const originalCreateElement = document.createElement.bind(document);
        document.createElement = jest.fn(() => ({
            id: '',
            className: '',
        }));

        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'new');

        expect(document.createElement).toHaveBeenCalledWith('sc-bilara-translation-edit-status');
        expect(mockParent.appendChild).toHaveBeenCalled();
        document.createElement = originalCreateElement;
    });
});

// ============================================================================
// scrollTop Tests
// ============================================================================

describe('scrollTop', () => {
    test('should set scrollTop to 0 on selected element', () => {
        const s = createMockSearch();
        const mockEl = { scrollTop: 100 };
        document.querySelector = jest.fn().mockReturnValue(mockEl);

        s.scrollTop('.container');

        expect(document.querySelector).toHaveBeenCalledWith('.container');
        expect(mockEl.scrollTop).toBe(0);
    });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Edge Cases', () => {
    test('should handle special characters in uid', () => {
        const s = createMockSearch();
        expect(s.getPrefixFromUid('thag1.1:1.1')).toBe('thag1.1');
        expect(s.getPrefixFromUid('snp1.1:0.1')).toBe('snp1.1');
    });

    test('searchResultFocus handles uid with no muid in results gracefully', () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'root-pli-ms': 'text' } };
        s.searchResultFocus('mn1:1.1', 'nonexistent-muid');
        expect(s.originalValues['mn1:1.1::nonexistent-muid']).toBe('');
    });

    test('should handle concurrent _fetchEditPermissions calls', async () => {
        const s = createMockSearch();
        let resolveCount = 0;
        requestWithTokenRetry.mockImplementation(() => {
            resolveCount++;
            return Promise.resolve({
                json: () => Promise.resolve({ can_edit: resolveCount % 2 === 0 }),
            });
        });

        const results1 = { 'mn1:1.1': { 'muid-a': 'a' } };
        const results2 = { 'mn1:1.2': { 'muid-b': 'b' } };

        await Promise.all([
            s._fetchEditPermissions(results1),
            s._fetchEditPermissions(results2),
        ]);

        expect('muid-a' in s.editableMusids).toBe(true);
        expect('muid-b' in s.editableMusids).toBe(true);
    });

    test('_buildResultEntries preserves segment order', () => {
        const s = createMockSearch();
        s.results = {
            'mn1:1.1': {
                'root-pli-ms': 'pali',
                'translation-en-sujato': 'english',
                'comment-en-sujato': 'note',
            },
        };
        s._buildResultEntries();
        const muids = s.resultEntries[0].segments.map(seg => seg.muid);
        expect(muids).toEqual(['root-pli-ms', 'translation-en-sujato', 'comment-en-sujato']);
    });

    test('searchResultInput with multiple segments only updates target', () => {
        const s = createMockSearch();
        s.results = {
            'mn1:1.1': { 'root-pli-ms': 'pali', 'translation-en-sujato': 'english' },
        };
        s.resultEntries = [{
            uid: 'mn1:1.1',
            segments: [
                { muid: 'root-pli-ms', segment: 'pali' },
                { muid: 'translation-en-sujato', segment: 'english' },
            ],
        }];

        s.searchResultInput('mn1:1.1', 'translation-en-sujato', 'updated');

        expect(s.results['mn1:1.1']['root-pli-ms']).toBe('pali'); // unchanged
        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('updated');
        expect(s.resultEntries[0].segments[0].segment).toBe('pali'); // unchanged
        expect(s.resultEntries[0].segments[1].segment).toBe('updated');
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    beforeEach(() => {
        requestWithTokenRetry.mockReset();
        displayBadge.mockReset();
        document.getElementById = jest.fn().mockReturnValue(null);
    });

    test('full edit workflow: build → focus → input → save', async () => {
        const s = createMockSearch();
        s.results = {
            'mn1:1.1': { 'translation-en-sujato': 'original text' },
        };

        // 1. Build entries
        s._buildResultEntries();
        expect(s.resultEntries).toHaveLength(1);

        // 2. Focus (snapshot)
        s.searchResultFocus('mn1:1.1', 'translation-en-sujato');
        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('original text');

        // 3. Input (modify)
        s.searchResultInput('mn1:1.1', 'translation-en-sujato', 'modified text');
        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('modified text');
        expect(s.resultEntries[0].segments[0].segment).toBe('modified text');

        // 4. Save
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });
        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'modified text');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/translation-en-sujato/mn1/',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ 'mn1:1.1': 'modified text' }),
            }),
        );
        expect(s.originalValues['mn1:1.1::translation-en-sujato']).toBe('modified text');
    });

    test('second save without change should be skipped', async () => {
        const s = createMockSearch();
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'text' } };
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        // First save
        s.originalValues['mn1:1.1::translation-en-sujato'] = 'old';
        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'text');
        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);

        // Second save with same value — should skip
        requestWithTokenRetry.mockReset();
        await s.searchResultSave('mn1:1.1', 'translation-en-sujato', 'text');
        expect(requestWithTokenRetry).not.toHaveBeenCalled();
    });

    test('permissions + canEdit workflow', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockImplementation((url) => {
            if (url.includes('translation-en-sujato')) {
                return Promise.resolve({ json: () => Promise.resolve({ can_edit: true }) });
            }
            return Promise.resolve({ json: () => Promise.resolve({ can_edit: false }) });
        });

        const results = {
            'mn1:1.1': { 'translation-en-sujato': 'text', 'root-pli-ms': 'pali' },
        };

        await s._fetchEditPermissions(results);

        expect(s.canEditMuid('translation-en-sujato', true)).toBe(true);
        expect(s.canEditMuid('root-pli-ms', true)).toBe(false);
        expect(s.canEditMuid('translation-en-sujato', false)).toBe(false);
    });

    test('constructQueryParams reflects toggled projects', () => {
        const s = createMockSearch();
        s.toggleSelectedProjects('translation-en-sujato');
        s.fields['translation-en-sujato'] = 'monks';
        s.fields.uid = 'mn1';
        s.size = 20;
        s.currentPage = 0;

        const params = s.constructQueryParams();
        expect(params.get('uid')).toBe('mn1');
        expect(params.get('translation-en-sujato')).toBe('monks');
        expect(params.get('size')).toBe('20');
        expect(params.get('page')).toBe('0');
    });
});

// ============================================================================
// replaceSegment Tests
// ============================================================================

describe('replaceSegment', () => {
    test('should replace search term in segment with replacementText', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };
        s.replacementText = 'world';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'say hello to hello' } };
        const seg = { muid: 'translation-en-sujato', segment: 'say hello to hello' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('say world to world');
        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('say world to world');
        expect(s.replacedItems['mn1:1.1::translation-en-sujato']).toBe(true);
    });

    test('should use fallback field when muid not in fields', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-zh-site': 'hello' };
        s.replacementText = 'world';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'hello there' } };
        const seg = { muid: 'translation-en-sujato', segment: 'hello there' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('world there');
    });

    test('should do nothing when no search term found', () => {
        const s = createMockSearch();
        s.fields = { uid: '' };
        s.replacementText = 'world';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'hello' } };
        const seg = { muid: 'translation-en-sujato', segment: 'hello' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('hello');
        expect(s.replacedItems).toEqual({});
    });

    test('should replace with empty string when replacementText is empty', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };
        s.replacementText = '';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'say hello' } };
        const seg = { muid: 'translation-en-sujato', segment: 'say hello' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('say ');
        expect(s.replacedItems['mn1:1.1::translation-en-sujato']).toBe(true);
    });

    test('should not modify results if uid not in results', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };
        s.replacementText = 'world';
        s.results = {};
        const seg = { muid: 'translation-en-sujato', segment: 'hello' };

        s.replaceSegment('unknown:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('world');
        expect(s.replacedItems['unknown:1.1::translation-en-sujato']).toBe(true);
    });

    test('should handle case-sensitive replacement', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'Hello' };
        s.replacementText = 'World';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'Hello hello HELLO' } };
        const seg = { muid: 'translation-en-sujato', segment: 'Hello hello HELLO' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        // replaceAll is case-sensitive
        expect(seg.segment).toBe('World hello HELLO');
    });
});

// ============================================================================
// submitReplacement Tests
// ============================================================================

describe('submitReplacement', () => {
    beforeEach(() => {
        requestWithTokenRetry.mockReset();
        displayBadge.mockReset();
        document.getElementById = jest.fn().mockReturnValue(null);
    });

    test('should call API with correct params and mark as submitted', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.submitReplacement('mn1:1.1', 'translation-en-sujato', 'new text');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/translation-en-sujato/mn1/',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ 'mn1:1.1': 'new text' }),
            }),
        );
        expect(s.submittedItems['mn1:1.1::translation-en-sujato']).toBe(true);
    });

    test('should display PENDING then COMMITTED badge on success', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.submitReplacement('mn1:1.1', 'translation-en-sujato', 'text');

        const badgeId = 'search-badge-translation-en-sujato-mn1:1.1';
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.PENDING);
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.COMMITTED);
    });

    test('should display ERROR badge and throw on failure', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockRejectedValue(new Error('Network error'));

        await expect(
            s.submitReplacement('mn1:1.1', 'translation-en-sujato', 'text'),
        ).rejects.toThrow();

        const badgeId = 'search-badge-translation-en-sujato-mn1:1.1';
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.PENDING);
        expect(displayBadge).toHaveBeenCalledWith(badgeId, BadgeStatus.ERROR);
        expect(s.submittedItems['mn1:1.1::translation-en-sujato']).toBeUndefined();
    });

    test('should use correct prefix for compound uid', async () => {
        const s = createMockSearch();
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });

        await s.submitReplacement('an1.1:0.1', 'translation-zh-site', 'replaced');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/translation-zh-site/an1.1/',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ 'an1.1:0.1': 'replaced' }),
            }),
        );
    });
});

// ============================================================================
// _escapeHtml Tests
// ============================================================================

describe('_escapeHtml', () => {
    test('should escape HTML special characters', () => {
        const s = createMockSearch();
        expect(s._escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;',
        );
    });

    test('should escape ampersand', () => {
        const s = createMockSearch();
        expect(s._escapeHtml('a & b')).toBe('a &amp; b');
    });

    test('should return empty string for empty input', () => {
        const s = createMockSearch();
        expect(s._escapeHtml('')).toBe('');
    });

    test('should not modify plain text', () => {
        const s = createMockSearch();
        expect(s._escapeHtml('hello world')).toBe('hello world');
    });
});

// ============================================================================
// getHighlightedSegment Tests
// ============================================================================

describe('getHighlightedSegment', () => {
    test('should wrap search term in <mark> tags', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };

        const result = s.getHighlightedSegment('say hello world', 'mn1:1.1', 'translation-en-sujato');

        expect(result).toBe('say <mark class="search__highlight">hello</mark> world');
    });

    test('should highlight all occurrences case-insensitively', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };

        const result = s.getHighlightedSegment('Hello hello HELLO', 'mn1:1.1', 'translation-en-sujato');

        expect(result).toBe(
            '<mark class="search__highlight">Hello</mark> <mark class="search__highlight">hello</mark> <mark class="search__highlight">HELLO</mark>',
        );
    });

    test('should highlight replacement text after replace', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'hello' };
        s.replacementText = 'world';
        s.replacedItems['mn1:1.1::translation-en-sujato'] = true;

        const result = s.getHighlightedSegment('say world to world', 'mn1:1.1', 'translation-en-sujato');

        expect(result).toBe(
            'say <mark class="search__highlight">world</mark> to <mark class="search__highlight">world</mark>',
        );
    });

    test('should return escaped text when no search term', () => {
        const s = createMockSearch();
        s.fields = { uid: '' };

        const result = s.getHighlightedSegment('hello <b>world</b>', 'mn1:1.1', 'unknown-muid');

        expect(result).toBe('hello &lt;b&gt;world&lt;/b&gt;');
    });

    test('should return empty string for empty segment', () => {
        const s = createMockSearch();
        expect(s.getHighlightedSegment('', 'mn1:1.1', 'muid')).toBe('');
    });

    test('should return empty string for null/undefined segment', () => {
        const s = createMockSearch();
        expect(s.getHighlightedSegment(null, 'mn1:1.1', 'muid')).toBe('');
        expect(s.getHighlightedSegment(undefined, 'mn1:1.1', 'muid')).toBe('');
    });

    test('should escape HTML in segment before highlighting', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'test' };

        const result = s.getHighlightedSegment('<script>test</script>', 'mn1:1.1', 'translation-en-sujato');

        expect(result).toContain('<mark class="search__highlight">');
        expect(result).not.toContain('<script>');
        expect(result).toContain('&lt;script&gt;');
    });

    test('should handle regex special characters in search term', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'a.b' };

        const result = s.getHighlightedSegment('a.b and axb', 'mn1:1.1', 'translation-en-sujato');

        // Only "a.b" should be highlighted, not "axb"
        expect(result).toBe('<mark class="search__highlight">a.b</mark> and axb');
    });

    test('should use fallback field when muid not in fields', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-zh-site': 'hello' };

        const result = s.getHighlightedSegment('hello world', 'mn1:1.1', 'root-pli-ms');

        expect(result).toBe('<mark class="search__highlight">hello</mark> world');
    });
});

// ============================================================================
// Replace + Submit Integration Tests
// ============================================================================

describe('Replace + Submit Integration', () => {
    beforeEach(() => {
        requestWithTokenRetry.mockReset();
        displayBadge.mockReset();
        document.getElementById = jest.fn().mockReturnValue(null);
    });

    test('full replace → submit workflow', async () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'old' };
        s.replacementText = 'new';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'the old text' } };
        s._buildResultEntries();
        const seg = s.resultEntries[0].segments[0];

        // 1. Replace
        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);
        expect(seg.segment).toBe('the new text');
        expect(s.replacedItems['mn1:1.1::translation-en-sujato']).toBe(true);
        expect(s.submittedItems['mn1:1.1::translation-en-sujato']).toBeUndefined();

        // 2. Highlight should use replacement text
        const highlighted = s.getHighlightedSegment(seg.segment, 'mn1:1.1', 'translation-en-sujato');
        expect(highlighted).toContain('<mark class="search__highlight">new</mark>');

        // 3. Submit
        requestWithTokenRetry.mockResolvedValue({
            json: () => Promise.resolve({}),
        });
        await s.submitReplacement('mn1:1.1', 'translation-en-sujato', seg.segment);
        expect(s.submittedItems['mn1:1.1::translation-en-sujato']).toBe(true);
    });

    test('replace updates both seg object and results dict', () => {
        const s = createMockSearch();
        s.fields = { uid: '', 'translation-en-sujato': 'abc' };
        s.replacementText = 'xyz';
        s.results = { 'mn1:1.1': { 'translation-en-sujato': 'abc def abc' } };
        const seg = { muid: 'translation-en-sujato', segment: 'abc def abc' };

        s.replaceSegment('mn1:1.1', 'translation-en-sujato', seg);

        expect(seg.segment).toBe('xyz def xyz');
        expect(s.results['mn1:1.1']['translation-en-sujato']).toBe('xyz def xyz');
    });
});
