/**
 * Translation.js Related Projects Persistence Tests
 *
 * Tests for the localStorage persistence of related project selections:
 * - getSavedRelatedProjects
 * - saveRelatedProjects
 * - toggleRelatedProject (with persistence)
 * - init() restoration of saved related projects
 */

// ============================================================================
// getSavedRelatedProjects / saveRelatedProjects
// ============================================================================

describe('Related Projects Persistence Helpers', () => {
    let mockContext;
    let getItemSpy;
    let setItemSpy;

    beforeEach(() => {
        localStorage.clear();
        getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
        setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

        mockContext = {
            prefix: 'mn1',
            muid: 'en-sujato',
            getSavedRelatedProjects() {
                try {
                    const key = `relatedProjects_${this.muid}`;
                    return JSON.parse(localStorage.getItem(key)) || [];
                } catch {
                    return [];
                }
            },
            saveRelatedProjects(projects) {
                const key = `relatedProjects_${this.muid}`;
                localStorage.setItem(key, JSON.stringify(projects));
            },
        };
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    describe('getSavedRelatedProjects', () => {
        test('should return saved projects from localStorage', () => {
            getItemSpy.mockReturnValue(JSON.stringify(['pli-ms', 'de-sabbamitta']));
            const result = mockContext.getSavedRelatedProjects();
            expect(result).toEqual(['pli-ms', 'de-sabbamitta']);
            expect(getItemSpy).toHaveBeenCalledWith('relatedProjects_en-sujato');
        });

        test('should return empty array when nothing is saved', () => {
            getItemSpy.mockReturnValue(null);
            expect(mockContext.getSavedRelatedProjects()).toEqual([]);
        });

        test('should return empty array when localStorage has invalid JSON', () => {
            getItemSpy.mockReturnValue('not-valid-json{{{');
            expect(mockContext.getSavedRelatedProjects()).toEqual([]);
        });

        test('should use prefix and muid to construct key', () => {
            mockContext.prefix = 'dn2';
            mockContext.muid = 'zh-sujato';
            getItemSpy.mockReturnValue(null);
            mockContext.getSavedRelatedProjects();
            expect(getItemSpy).toHaveBeenCalledWith('relatedProjects_zh-sujato');
        });
    });

    describe('saveRelatedProjects', () => {
        test('should save projects to localStorage as JSON', () => {
            mockContext.saveRelatedProjects(['pli-ms', 'de-sabbamitta']);
            expect(setItemSpy).toHaveBeenCalledWith(
                'relatedProjects_en-sujato',
                JSON.stringify(['pli-ms', 'de-sabbamitta'])
            );
        });

        test('should save empty array', () => {
            mockContext.saveRelatedProjects([]);
            expect(setItemSpy).toHaveBeenCalledWith(
                'relatedProjects_en-sujato',
                '[]'
            );
        });

        test('should use prefix and muid to construct key', () => {
            mockContext.prefix = 'sn3';
            mockContext.muid = 'fr-noeismet';
            mockContext.saveRelatedProjects(['pli-ms']);
            expect(setItemSpy).toHaveBeenCalledWith(
                'relatedProjects_fr-noeismet',
                JSON.stringify(['pli-ms'])
            );
        });
    });
});

// ============================================================================
// toggleRelatedProject with persistence
// ============================================================================

describe('toggleRelatedProject with persistence', () => {
    let mockContext;
    let getItemSpy;
    let setItemSpy;

    beforeEach(() => {
        localStorage.clear();
        getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
        setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

        mockContext = {
            prefix: 'mn1',
            muid: 'en-sujato',
            translations: [
                { muid: 'pli-ms', isSource: true, data: { 'mn1:1.1': 'source' } },
                { muid: 'en-sujato', canEdit: true, data: {} },
            ],
            async findOrCreateObject(key, prefix) {
                const obj = { canEdit: false, muid: key, prefix, data: { 'mn1:1.1': `data-${key}` } };
                this.translations.push(obj);
                return obj;
            },
            getSavedRelatedProjects() {
                try {
                    const key = `relatedProjects_${this.muid}`;
                    return JSON.parse(localStorage.getItem(key)) || [];
                } catch {
                    return [];
                }
            },
            saveRelatedProjects(projects) {
                const key = `relatedProjects_${this.muid}`;
                localStorage.setItem(key, JSON.stringify(projects));
            },
            async toggleRelatedProject(project) {
                const index = this.translations.findIndex(t => t.muid === project);
                if (index > -1) {
                    this.translations.splice(index, 1);
                    const saved = this.getSavedRelatedProjects().filter(p => p !== project);
                    this.saveRelatedProjects(saved);
                } else {
                    try {
                        await this.findOrCreateObject(project, this.prefix);
                        const saved = this.getSavedRelatedProjects();
                        if (!saved.includes(project)) {
                            saved.push(project);
                            this.saveRelatedProjects(saved);
                        }
                    } catch (error) {
                        throw new Error(error);
                    }
                }
            },
        };
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('should add project to translations and save to localStorage', async () => {
        getItemSpy.mockReturnValue('[]');
        await mockContext.toggleRelatedProject('de-sabbamitta');

        expect(mockContext.translations).toHaveLength(3);
        expect(mockContext.translations[2].muid).toBe('de-sabbamitta');
        expect(setItemSpy).toHaveBeenCalledWith(
            'relatedProjects_en-sujato',
            JSON.stringify(['de-sabbamitta'])
        );
    });

    test('should remove project from translations and localStorage', async () => {
        mockContext.translations.push({ muid: 'de-sabbamitta', data: {} });
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta', 'fr-noeismet']));

        await mockContext.toggleRelatedProject('de-sabbamitta');

        expect(mockContext.translations.find(t => t.muid === 'de-sabbamitta')).toBeUndefined();
        expect(setItemSpy).toHaveBeenCalledWith(
            'relatedProjects_en-sujato',
            JSON.stringify(['fr-noeismet'])
        );
    });

    test('should not duplicate project in localStorage if already saved', async () => {
        // Project not in translations but already in localStorage
        getItemSpy.mockReturnValue(JSON.stringify(['fr-noeismet']));
        await mockContext.toggleRelatedProject('fr-noeismet');

        // fr-noeismet is not in translations initially, so findOrCreateObject adds it.
        // Then getSavedRelatedProjects returns ['fr-noeismet'], includes check is true.
        // So setItem should NOT be called.
        expect(setItemSpy).not.toHaveBeenCalled();
    });

    test('should handle adding multiple projects sequentially', async () => {
        getItemSpy
            .mockReturnValueOnce('[]')                                    // first toggle read
            .mockReturnValueOnce(JSON.stringify(['de-sabbamitta']));      // second toggle read

        await mockContext.toggleRelatedProject('de-sabbamitta');
        await mockContext.toggleRelatedProject('fr-noeismet');

        expect(mockContext.translations).toHaveLength(4);
        expect(setItemSpy).toHaveBeenCalledTimes(2);
        expect(setItemSpy).toHaveBeenNthCalledWith(1,
            'relatedProjects_en-sujato',
            JSON.stringify(['de-sabbamitta'])
        );
        expect(setItemSpy).toHaveBeenNthCalledWith(2,
            'relatedProjects_en-sujato',
            JSON.stringify(['de-sabbamitta', 'fr-noeismet'])
        );
    });

    test('should save empty array when last related project is removed', async () => {
        mockContext.translations.push({ muid: 'de-sabbamitta', data: {} });
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta']));

        await mockContext.toggleRelatedProject('de-sabbamitta');

        expect(setItemSpy).toHaveBeenCalledWith(
            'relatedProjects_en-sujato',
            '[]'
        );
    });
});

// ============================================================================
// init() restoration of saved related projects
// ============================================================================

describe('init() restoration of saved related projects', () => {
    let mockContext;
    let dispatchedEvents;
    let getItemSpy;
    let setItemSpy;

    beforeEach(() => {
        localStorage.clear();
        getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
        setItemSpy = jest.spyOn(Storage.prototype, 'setItem');
        dispatchedEvents = [];

        // Capture dispatched events
        jest.spyOn(window, 'dispatchEvent').mockImplementation((event) => {
            dispatchedEvents.push(event);
        });

        mockContext = {
            translations: [],
            relatedProjects: [],
            htmlProjectName: '',
            htmlProject: null,
            originalTranslations: null,
            splitter_uid: null,
            merger_uid: null,
            mergee_uid: null,
            prefix: null,
            muid: null,

            async findOrCreateObject(key, prefix, source = false) {
                const obj = { canEdit: false, muid: key, prefix, data: { 'mn1:1.1': `data-${key}` } };
                if (source) obj.isSource = true;
                this.translations.push(obj);
                return obj;
            },
            async createObject(key, prefix) {
                return { canEdit: false, muid: key, prefix, data: {} };
            },
            async fetchRelatedProjects() {
                return ['pli-ms', 'en-sujato', 'de-sabbamitta', 'fr-noeismet', 'html-pli-ms'];
            },
            getSavedRelatedProjects() {
                try {
                    const key = `relatedProjects_${this.muid}`;
                    return JSON.parse(localStorage.getItem(key)) || [];
                } catch {
                    return [];
                }
            },
            saveRelatedProjects(projects) {
                const key = `relatedProjects_${this.muid}`;
                localStorage.setItem(key, JSON.stringify(projects));
            },
            updateProgress() {},

            async init() {
                const prefix = 'mn1';
                const muid = 'en-sujato';
                const source = 'pli-ms';

                this.prefix = prefix;
                this.muid = muid;

                await this.findOrCreateObject(source, this.prefix, true);
                if (muid) {
                    await this.findOrCreateObject(muid, this.prefix);
                }
                const projects = await this.fetchRelatedProjects(this.prefix);
                this.relatedProjects = projects.filter(project => project !== muid && project !== source);

                this.htmlProjectName = projects.find(project => project.includes('html'));
                if (this.htmlProjectName) {
                    this.htmlProject = await this.createObject(this.htmlProjectName, this.prefix);
                }

                const savedRelated = this.getSavedRelatedProjects();
                const validSaved = savedRelated.filter(p => this.relatedProjects.includes(p));
                for (const project of validSaved) {
                    try {
                        await this.findOrCreateObject(project, this.prefix);
                    } catch (error) {
                        console.error(`Failed to restore related project ${project}:`, error);
                    }
                }
                if (validSaved.length !== savedRelated.length) {
                    this.saveRelatedProjects(validSaved);
                }
                window.dispatchEvent(new CustomEvent('restore-related-projects', { detail: { projects: validSaved } }));

                this.updateProgress();
            },
        };
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('should restore saved related projects on init', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta']));

        await mockContext.init();

        // Source + muid + restored project = 3 translations
        expect(mockContext.translations).toHaveLength(3);
        expect(mockContext.translations[2].muid).toBe('de-sabbamitta');
    });

    test('should dispatch restore-related-projects event with valid projects', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta', 'fr-noeismet']));

        await mockContext.init();

        const restoreEvent = dispatchedEvents.find(e => e.type === 'restore-related-projects');
        expect(restoreEvent).toBeDefined();
        expect(restoreEvent.detail.projects).toEqual(['de-sabbamitta', 'fr-noeismet']);
    });

    test('should filter out invalid projects and update localStorage', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta', 'nonexistent-project']));

        await mockContext.init();

        expect(mockContext.translations).toHaveLength(3);
        expect(mockContext.translations[2].muid).toBe('de-sabbamitta');

        expect(setItemSpy).toHaveBeenCalledWith(
            'relatedProjects_en-sujato',
            JSON.stringify(['de-sabbamitta'])
        );
    });

    test('should not call saveRelatedProjects when all saved projects are valid', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta']));

        await mockContext.init();

        expect(setItemSpy).not.toHaveBeenCalled();
    });

    test('should handle empty saved projects gracefully', async () => {
        getItemSpy.mockReturnValue(null);

        await mockContext.init();

        expect(mockContext.translations).toHaveLength(2);
        const restoreEvent = dispatchedEvents.find(e => e.type === 'restore-related-projects');
        expect(restoreEvent.detail.projects).toEqual([]);
    });

    test('should store muid on context', async () => {
        getItemSpy.mockReturnValue(null);

        await mockContext.init();

        expect(mockContext.muid).toBe('en-sujato');
    });

    test('should continue restoring even if one project fails', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['de-sabbamitta', 'fr-noeismet']));

        const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const originalFindOrCreate = mockContext.findOrCreateObject.bind(mockContext);
        mockContext.findOrCreateObject = async function (key, prefix, source) {
            if (key === 'de-sabbamitta') throw new Error('Network error');
            return originalFindOrCreate(key, prefix, source);
        };

        await mockContext.init();

        // source + muid + fr-noeismet (de-sabbamitta failed) = 3
        expect(mockContext.translations).toHaveLength(3);
        expect(mockContext.translations.find(t => t.muid === 'fr-noeismet')).toBeDefined();
        expect(mockContext.translations.find(t => t.muid === 'de-sabbamitta')).toBeUndefined();
        expect(consoleSpy).toHaveBeenCalled();

        consoleSpy.mockRestore();
    });

    test('should restore multiple projects in order', async () => {
        getItemSpy.mockReturnValue(JSON.stringify(['fr-noeismet', 'de-sabbamitta']));

        await mockContext.init();

        // source(0) + muid(1) + fr-noeismet(2) + de-sabbamitta(3) = 4
        expect(mockContext.translations).toHaveLength(4);
        expect(mockContext.translations[2].muid).toBe('fr-noeismet');
        expect(mockContext.translations[3].muid).toBe('de-sabbamitta');
    });
});
