const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
eval(translationJsContent);

describe('Fallback Prefix Functions', () => {
    let context;

    beforeEach(() => {
        context = fetchTranslation();
    });

    describe('loadHyphenatedPrefixRanges', () => {
        let originalFetch;

        beforeEach(() => {
            originalFetch = global.fetch;
        });

        afterEach(() => {
            global.fetch = originalFetch;
        });

        test('should load ranges successfully', async () => {
            global.fetch = jest.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve(['mn1-152', 'dn1-34'])
            }));

            await context.loadHyphenatedPrefixRanges();

            expect(global.fetch).toHaveBeenCalledWith('/static/merged_sutta_ranges.json', {
                credentials: 'same-origin'
            });
            expect(context.hyphenatedPrefixRanges).toEqual(['mn1-152', 'dn1-34']);
        });

        test('should set empty array when response is not ok', async () => {
            global.fetch = jest.fn(() => Promise.resolve({
                ok: false
            }));

            await context.loadHyphenatedPrefixRanges();
            expect(context.hyphenatedPrefixRanges).toEqual([]);
        });

        test('should set empty array on fetch error', async () => {
            global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

            await context.loadHyphenatedPrefixRanges();
            expect(context.hyphenatedPrefixRanges).toEqual([]);
        });

        test('should set empty array when json is not an array', async () => {
            global.fetch = jest.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ error: 'not an array' })
            }));

            await context.loadHyphenatedPrefixRanges();
            expect(context.hyphenatedPrefixRanges).toEqual([]);
        });
    });

    describe('parseHyphenatedPrefixRange', () => {
        test('should correctly parse valid hyphenated ranges', () => {
            expect(context.parseHyphenatedPrefixRange('sn49.1-12')).toEqual({
                original: 'sn49.1-12',
                base: 'sn49.',
                start: 1,
                end: 12,
                width: 11
            });

            expect(context.parseHyphenatedPrefixRange('pdhp174-194')).toEqual({
                original: 'pdhp174-194',
                base: 'pdhp',
                start: 174,
                end: 194,
                width: 20
            });

            expect(context.parseHyphenatedPrefixRange('pli-tv-bi-vb-pc91-93')).toEqual({
                original: 'pli-tv-bi-vb-pc91-93',
                base: 'pli-tv-bi-vb-pc',
                start: 91,
                end: 93,
                width: 2
            });
        });

        test('should return null for invalid formats', () => {
            // Not a hyphenated range
            expect(context.parseHyphenatedPrefixRange('mn1')).toBeNull();

            // Missing numbers
            expect(context.parseHyphenatedPrefixRange('mn-')).toBeNull();

            // Text instead of number
            expect(context.parseHyphenatedPrefixRange('mn1-abc')).toBeNull();

            // Start greater than end
            expect(context.parseHyphenatedPrefixRange('mn152-1')).toBeNull();

            // Multiple hyphens without number start
            expect(context.parseHyphenatedPrefixRange('mn-ab-1-5')).toEqual({
                original: 'mn-ab-1-5',
                base: 'mn-ab-',
                start: 1,
                end: 5,
                width: 4
            });
        });
    });

    describe('getFallbackPrefix', () => {
        beforeEach(() => {
            context.hyphenatedPrefixRanges = [
                'an1.170-187',
                'dhp33-43',
                'sn49.1-12',
                'pli-tv-bi-vb-pc91-93',
                'pli-tv-bi-vb-as1-7',
                'sn51.55-66',
                'pdhp174-194',
                'patthana2.6-7'
            ];
        });

        test('should return null if input prefix is hyphenated or missing', () => {
            expect(context.getFallbackPrefix('mn1-50')).toBeNull();
            expect(context.getFallbackPrefix(null)).toBeNull();
            expect(context.getFallbackPrefix('')).toBeNull();
            expect(context.getFallbackPrefix('an1')).toBeNull();
        });

        test('should return null if input prefix doesn\'t end with number', () => {
            expect(context.getFallbackPrefix('mn')).toBeNull();
            expect(context.getFallbackPrefix('dn-name')).toBeNull();
            expect(context.getFallbackPrefix('pli-tv-bi-vb-pc')).toBeNull();
        });

        test('should find the most specific (narrowest) matching range', () => {
            expect(context.getFallbackPrefix('dhp43')).toBe('dhp33-43');
            expect(context.getFallbackPrefix('sn51.55')).toBe('sn51.55-66');
            expect(context.getFallbackPrefix('sn49.1')).toBe('sn49.1-12');
        });

        test('should return null if no matching range is found', () => {
            expect(context.getFallbackPrefix('sn1')).toBeNull();
            expect(context.getFallbackPrefix('dn35')).toBeNull();
            expect(context.getFallbackPrefix('mn200')).toBeNull();
            expect(context.getFallbackPrefix('sarv-sn6')).toBeNull();
        });

        test('should match edge numbers inclusively', () => {
            expect(context.getFallbackPrefix('an1.171')).toBe('an1.170-187');
            expect(context.getFallbackPrefix('dhp33')).toBe('dhp33-43');
            expect(context.getFallbackPrefix('sn49.3')).toBe('sn49.1-12');
            expect(context.getFallbackPrefix('pli-tv-bi-vb-pc92')).toBe('pli-tv-bi-vb-pc91-93');
            expect(context.getFallbackPrefix('pli-tv-bi-vb-as2')).toBe('pli-tv-bi-vb-as1-7');
            expect(context.getFallbackPrefix('patthana2.6')).toBe('patthana2.6-7');
        });
    });
});
