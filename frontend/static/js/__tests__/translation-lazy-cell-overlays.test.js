const fs = require('fs');
const path = require('path');

const translationHtml = fs.readFileSync(
    path.resolve(__dirname, '../../../translation.html'),
    'utf8',
);

describe('translation cell overlays', () => {
    test('mounts the tag suggestions menu only while it is open for an editable tag cell', () => {
        expect(translationHtml).toMatch(
            /<template\s+x-if="isTag && showTagSuggestions && translation\.canEdit && \(tagSuggestions\.length > 0 \|\| \(isAdmin && isActive\)\)">[\s\S]*?class="translation-cell__hints translation-cell__tag-suggestions"[\s\S]*?<\/template>/,
        );
    });

    test('releases tag suggestions whenever the menu closes', () => {
        expect(translationHtml).toMatch(
            /closeTagSuggestions\(\)\s*\{[\s\S]*?this\.showTagSuggestions = false;[\s\S]*?this\.tagSuggestions = \[\];[\s\S]*?this\.selectedTagIndex = -1;[\s\S]*?\}/,
        );
        expect(translationHtml.match(/closeTagSuggestions\(\);/g)).toHaveLength(3);
    });

    test('mounts the translation hints dropdown only while hints are visible', () => {
        expect(translationHtml).toMatch(
            /<template\s+x-if="hints\.length > 0 && showHints && !translation\.isSource && hintStyle !== 'inline'">[\s\S]*?class="translation-cell__hints"[\s\S]*?<\/template>/,
        );
    });

    test('mounts row-level inline hints only while they are visible', () => {
        expect(translationHtml).toMatch(
            /<template\s+x-if="rowHintsShow">[\s\S]*?class="translation-cell__hints--inline"[\s\S]*?<\/template>/,
        );
    });
});
