const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
const translationHtml = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');

eval(translationJsContent);

describe('translation hints root-text highlighting', () => {
    test('highlights a full token match when punctuation differs', () => {
        expect(highlightRootMatches('Evaṁ me sutaṁ.', 'Evaṁ me sutaṁ—')).toBe(
            '<mark class="translation-cell__hints-match">Evaṁ me sutaṁ</mark>.'
        );
    });

    test('highlights matching root text inside a longer hint segment', () => {
        expect(highlightRootMatches('Vuttañhetaṁ bhagavatā me sutaṁ:', 'Evaṁ me sutaṁ—')).toBe(
            'Vuttañhetaṁ bhagavatā <mark class="translation-cell__hints-match">me sutaṁ</mark>:'
        );
    });

    test('highlights a single shared token', () => {
        expect(highlightRootMatches('“Evaṁ, bhante”.', 'Evaṁ me sutaṁ—')).toBe(
            '“<mark class="translation-cell__hints-match">Evaṁ</mark>, bhante”.'
        );
    });

    test('escapes hint HTML before adding highlight markup', () => {
        const highlighted = highlightRootMatches('<img src=x> Evaṁ & me sutaṁ', 'Evaṁ me sutaṁ');

        expect(highlighted).toContain('&lt;img src=x&gt;');
        expect(highlighted).not.toContain('<img');
        expect(highlighted).toContain(
            '<mark class="translation-cell__hints-match">Evaṁ &amp; me sutaṁ</mark>'
        );
    });

    test('wires dropdown and inline hints to the highlighter', () => {
        expect(translationHtml).toContain('x-html="highlightRootMatches(hint.segment, sourceValue)"');
        expect(translationHtml).toContain('rowHintsSourceValue');
        expect(translationHtml).toContain('x-html="highlightRootMatches(hint.segment, rowHintsSourceValue)"');
    });
});
