const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(
    path.resolve(__dirname, '../translation.js'),
    'utf8',
);
eval(translationJsContent);

describe('incremental translation progress', () => {
    let context;
    let dispatchEventSpy;

    beforeEach(() => {
        context = fetchTranslation();
        context.translations = [
            {
                isSource: true,
                canEdit: false,
                muid: 'root-pli-ms',
                data: {
                    'mn1:1.1': 'Source one',
                    'mn1:1.2': 'Source two',
                },
            },
            {
                isSource: false,
                canEdit: true,
                muid: 'translation-en-tester',
                data: {
                    'mn1:1.1': 'Existing translation',
                    'mn1:1.2': '',
                },
            },
        ];
        dispatchEventSpy = jest.spyOn(window, 'dispatchEvent');
        context.updateProgress();
        dispatchEventSpy.mockClear();
    });

    afterEach(() => {
        dispatchEventSpy.mockRestore();
    });

    test('does not publish progress when non-empty text remains non-empty', () => {
        const translation = context.translations[1];

        context.setValue(translation, 'mn1:1.1', 'Updated translation');

        expect(translation.data['mn1:1.1']).toBe('Updated translation');
        expect(dispatchEventSpy).not.toHaveBeenCalled();
    });

    test('increments progress when empty text becomes non-empty', () => {
        const translation = context.translations[1];

        context.setValue(translation, 'mn1:1.2', 'New translation');

        expect(dispatchEventSpy).toHaveBeenCalledTimes(1);
        expect(dispatchEventSpy.mock.calls[0][0].detail).toEqual({
            translated: 2,
            total: 2,
            percentage: 100,
        });
    });

    test('decrements progress when non-empty text becomes whitespace', () => {
        const translation = context.translations[1];

        context.setValue(translation, 'mn1:1.1', '   ');

        expect(dispatchEventSpy).toHaveBeenCalledTimes(1);
        expect(dispatchEventSpy.mock.calls[0][0].detail).toEqual({
            translated: 0,
            total: 2,
            percentage: 0,
        });
    });

    test('ignores edits in a column not used for translation progress', () => {
        const remarks = {
            isSource: false,
            canEdit: true,
            muid: 'remarks:123',
            data: { 'mn1:1.2': '' },
        };
        context.translations.push(remarks);

        context.setValue(remarks, 'mn1:1.2', 'A remark');

        expect(dispatchEventSpy).not.toHaveBeenCalled();
    });

    test('ignores a translation UID that is absent from the source text', () => {
        const translation = context.translations[1];

        context.setValue(translation, 'mn1:9.9', 'Unmatched translation');

        expect(dispatchEventSpy).not.toHaveBeenCalled();
    });

    test('rebuilds the baseline after the source structure changes', () => {
        context.translations[0].data['mn1:1.3'] = 'Source three';
        context.translations[1].data['mn1:1.3'] = 'Translation three';

        context.updateProgress();

        expect(dispatchEventSpy).toHaveBeenCalledTimes(1);
        expect(dispatchEventSpy.mock.calls[0][0].detail).toEqual({
            translated: 2,
            total: 3,
            percentage: 67,
        });
    });
});
