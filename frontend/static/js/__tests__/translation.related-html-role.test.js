const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(
    path.resolve(__dirname, '../translation.js'),
    'utf8',
);
eval(translationJsContent);

describe('HTML related project visibility by role', () => {
    let getItemSpy;

    function createContext(role) {
        const context = fetchTranslation();

        context.resolveSource = jest.fn().mockResolvedValue('root-pli-ms');
        context.loadHyphenatedPrefixRanges = jest.fn().mockResolvedValue();
        context.findOrCreateObject = jest.fn(async (muid, prefix, isSource = false) => {
            const project = { muid, prefix, data: {}, canEdit: false };
            if (isSource) project.isSource = true;
            context.translations.push(project);
            return project;
        });
        context.fetchRelatedProjects = jest.fn().mockResolvedValue([
            'root-pli-ms',
            'translation-en-user',
            'translation-de-user',
            'html-pli-ms',
        ]);
        context.createObject = jest.fn(async (muid, prefix) => ({
            muid,
            prefix,
            data: {},
            canEdit: true,
        }));
        context.loadAvailableTags = jest.fn().mockResolvedValue();
        context.fetchRemarkUsers = jest.fn().mockResolvedValue([]);
        context.getSavedRelatedProjects = jest.fn().mockReturnValue([]);
        context.restoreRelatedProjectsInOrder = jest.fn().mockResolvedValue([]);
        context.updateProgress = jest.fn();

        requestWithTokenRetry.mockResolvedValue({
            ok: true,
            json: async () => ({
                role,
                github_id: 123,
                username: 'user',
            }),
        });

        return context;
    }

    beforeEach(() => {
        jest.clearAllMocks();
        getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
        window.history.replaceState(
            null,
            '',
            '/translation.html?prefix=mn1&muid=translation-en-user&source=root-pli-ms',
        );
    });

    afterEach(() => {
        getItemSpy.mockRestore();
    });

    test('shows the HTML project to an administrator', async () => {
        const context = createContext('administrator');

        await context.initialize();

        expect(context.relatedProjects).toContain('html-pli-ms');
    });

    test('shows the HTML project to a superuser', async () => {
        const context = createContext('superuser');

        await context.initialize();

        expect(context.relatedProjects).toContain('html-pli-ms');
    });

    test.each(['writer', 'reviewer'])(
        'hides the HTML project from a %s',
        async (role) => {
            const context = createContext(role);

            await context.initialize();

            expect(context.relatedProjects).not.toContain('html-pli-ms');
        },
    );
});
