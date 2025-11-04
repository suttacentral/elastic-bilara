describe('splitBasedOnUid - Two Level Format', () => {
    let mockTranslations;

    beforeEach(() => {
        mockTranslations = [
            {
                muid: 'test-project',
                data: {
                    'mn1:1.1': 'First paragraph',
                    'mn1:1.2': 'Second paragraph',
                    'mn1:1.3': 'Third paragraph',
                    'mn1:2.1': 'Different section'
                }
            },
            {
                muid: 'html-pli-ms',
                data: {
                    'mn1:1.1': '{}',
                    'mn1:1.2': '{}',
                    'mn1:1.3': '{}',
                    'mn1:2.1': '{}'
                }
            }
        ];
    });

    test('should correctly identify two-level format', () => {
        const sectionNumber = '1.2';
        const isTwoLevelFormat = /^[0-9]+\.[0-9]+$/.test(sectionNumber);
        expect(isTwoLevelFormat).toBe(true);
    });

    test('should reject invalid two-level format', () => {
        expect(/^[0-9]+\.[0-9]+$/.test('1')).toBe(false);
        expect(/^[0-9]+\.[0-9]+$/.test('1.2.3')).toBe(false);
        expect(/^[0-9]+\.[0-9]+$/.test('abc')).toBe(false);
    });

    test('should correctly set splitter_uid', () => {
        const sectionUid = 'mn1';
        const sectionNumber = '1.2';
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);
        const expectedUid = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;

        expect(expectedUid).toBe('mn1:1.3');
    });

    test('should insert new paragraph at split point', () => {
        const uid = 'mn1:1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);

        mockTranslations.forEach(translation => {
            const newObj = {};

            for (const key in translation.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');
                const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                const keyDecimalNumber = parseInt(keyDecimalPart);

                if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                    newObj[key] = translation.data[key];
                    continue;
                }

                if (keyDecimalNumber < splitPointNumber) {
                    newObj[key] = translation.data[key];
                } else if (keyDecimalNumber === splitPointNumber) {
                    newObj[key] = translation.data[key];
                    const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                    newObj[newKey] = translation.muid.includes('html') ? "{}" : "";
                } else {
                    const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                    newObj[newKey] = translation.data[key];
                }
            }
            translation.data = newObj;
        });

        const regularProject = mockTranslations[0];
        expect(regularProject.data['mn1:1.1']).toBe('First paragraph');
        expect(regularProject.data['mn1:1.2']).toBe('Second paragraph');
        expect(regularProject.data['mn1:1.3']).toBe('');
        expect(regularProject.data['mn1:1.4']).toBe('Third paragraph');
        expect(regularProject.data['mn1:2.1']).toBe('Different section');

        const htmlProject = mockTranslations[1];
        expect(htmlProject.data['mn1:1.3']).toBe('{}');
    });

    test('should handle edge case - split first paragraph', () => {
        const uid = 'mn1:1.1';
        const [sectionUid, sectionNumber] = uid.split(':');
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);

        const translation = mockTranslations[0];
        const newObj = {};

        for (const key in translation.data) {
            const [keySectionUid, keySectionNumber] = key.split(':');
            const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
            const keyDecimalNumber = parseInt(keyDecimalPart);

            if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                newObj[key] = translation.data[key];
                continue;
            }

            if (keyDecimalNumber < splitPointNumber) {
                newObj[key] = translation.data[key];
            } else if (keyDecimalNumber === splitPointNumber) {
                newObj[key] = translation.data[key];
                const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                newObj[newKey] = "";
            } else {
                const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                newObj[newKey] = translation.data[key];
            }
        }

        expect(newObj['mn1:1.1']).toBe('First paragraph');
        expect(newObj['mn1:1.2']).toBe('');
        expect(newObj['mn1:1.3']).toBe('Second paragraph');
        expect(newObj['mn1:1.4']).toBe('Third paragraph');
    });

    test('should maintain paragraph order', () => {
        const uid = 'mn1:1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);

        const translation = mockTranslations[0];
        const newObj = {};

        for (const key in translation.data) {
            const [keySectionUid, keySectionNumber] = key.split(':');
            const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
            const keyDecimalNumber = parseInt(keyDecimalPart);

            if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                newObj[key] = translation.data[key];
                continue;
            }

            if (keyDecimalNumber < splitPointNumber) {
                newObj[key] = translation.data[key];
            } else if (keyDecimalNumber === splitPointNumber) {
                newObj[key] = translation.data[key];
                const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                newObj[newKey] = "";
            } else {
                const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                newObj[newKey] = translation.data[key];
            }
        }

        const keys = Object.keys(newObj);
        expect(keys).toEqual(['mn1:1.1', 'mn1:1.2', 'mn1:1.3', 'mn1:1.4', 'mn1:2.1']);
    });

    test('should not affect paragraphs in other sections', () => {
        const uid = 'mn1:1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);

        const originalSection2 = mockTranslations[0].data['mn1:2.1'];

        mockTranslations.forEach(translation => {
            const newObj = {};

            for (const key in translation.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');
                const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                const keyDecimalNumber = parseInt(keyDecimalPart);

                if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                    newObj[key] = translation.data[key];
                    continue;
                }

                if (keyDecimalNumber < splitPointNumber) {
                    newObj[key] = translation.data[key];
                } else if (keyDecimalNumber === splitPointNumber) {
                    newObj[key] = translation.data[key];
                    const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                    newObj[newKey] = "";
                } else {
                    const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                    newObj[newKey] = translation.data[key];
                }
            }
            translation.data = newObj;
        });

        expect(mockTranslations[0].data['mn1:2.1']).toBe(originalSection2);
    });

    test('should handle multiple translation objects', () => {
        const uid = 'mn1:1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const [integerPart, decimalPart] = sectionNumber.split('.');
        const splitPointNumber = parseInt(decimalPart);

        mockTranslations.forEach(translation => {
            const newObj = {};

            for (const key in translation.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');
                const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                const keyDecimalNumber = parseInt(keyDecimalPart);

                if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                    newObj[key] = translation.data[key];
                    continue;
                }

                if (keyDecimalNumber < splitPointNumber) {
                    newObj[key] = translation.data[key];
                } else if (keyDecimalNumber === splitPointNumber) {
                    newObj[key] = translation.data[key];
                    const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                    newObj[newKey] = translation.muid.includes('html') ? "{}" : "";
                } else {
                    const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                    newObj[newKey] = translation.data[key];
                }
            }
            translation.data = newObj;
        });

        expect(mockTranslations).toHaveLength(2);
        expect(mockTranslations[0].data['mn1:1.3']).toBe('');
        expect(mockTranslations[1].data['mn1:1.3']).toBe('{}');
    });
});

describe('splitBasedOnUid - Three Level Format', () => {
    let mockTranslations;

    function getLastNumber(str) {
        return str.split('.').pop();
    }

    function getBeforeLastDot(str) {
        return str.substring(0, str.lastIndexOf('.') + 1);
    }

    beforeEach(() => {
        mockTranslations = [
            {
                muid: 'test-project',
                data: {
                    'dn1:1.1.1': 'First sub-paragraph',
                    'dn1:1.1.2': 'Second sub-paragraph',
                    'dn1:1.1.3': 'Third sub-paragraph',
                    'dn1:1.2.1': 'Different subsection',
                    'dn1:2.1.1': 'Different section'
                }
            },
            {
                muid: 'html-pli-ms',
                data: {
                    'dn1:1.1.1': '{}',
                    'dn1:1.1.2': '{}',
                    'dn1:1.1.3': '{}',
                    'dn1:1.2.1': '{}',
                    'dn1:2.1.1': '{}'
                }
            }
        ];
    });

    test('should correctly identify three-level format', () => {
        const sectionNumber = '1.1.2';
        const isThreeLevelFormat = /^[0-9]+\.[0-9]+\.[0-9]+$/.test(sectionNumber);
        expect(isThreeLevelFormat).toBe(true);
    });

    test('should reject invalid three-level format', () => {
        expect(/^[0-9]+\.[0-9]+\.[0-9]+$/.test('1.1')).toBe(false);
        expect(/^[0-9]+\.[0-9]+\.[0-9]+$/.test('1.1.2.3')).toBe(false);
    });

    test('should correctly extract main part and last part', () => {
        const sectionNumber = '1.1.2';
        const mainPart = getBeforeLastDot(sectionNumber);
        const lastPart = getLastNumber(sectionNumber);
        
        expect(mainPart).toBe('1.1.');
        expect(lastPart).toBe('2');
    });

    test('should correctly set splitter_uid for three-level format', () => {
        const uid = 'dn1:1.1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const sectionMainPart = getBeforeLastDot(sectionNumber);
        const sectionLastPart = parseInt(getLastNumber(sectionNumber));
        const splitterUid = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
        
        expect(splitterUid).toBe('dn1:1.1.3');
    });

    test('should insert new paragraph at split point - three-level format', () => {
        const uid = 'dn1:1.1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const sectionMainPart = getBeforeLastDot(sectionNumber);
        const sectionLastPart = parseInt(getLastNumber(sectionNumber));

        mockTranslations.forEach(translation => {
            const newObj = {};
            
            for (const key in translation.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');
                
                if (keySectionUid !== sectionUid) {
                    newObj[key] = translation.data[key];
                    continue;
                }
                
                const keyMainPart = getBeforeLastDot(keySectionNumber);
                const keyLastPart = parseInt(getLastNumber(keySectionNumber));
                
                if (keyMainPart !== sectionMainPart) {
                    newObj[key] = translation.data[key];
                    continue;
                }
                
                if (keyLastPart < sectionLastPart) {
                    newObj[key] = translation.data[key];
                } else if (keyLastPart === sectionLastPart) {
                    newObj[key] = translation.data[key];
                    const newKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                    newObj[newKey] = translation.muid.includes('html') ? "{}" : "";
                } else {
                    const newKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                    newObj[newKey] = translation.data[key];
                }
            }
            translation.data = newObj;
        });

        const regularProject = mockTranslations[0];
        expect(regularProject.data['dn1:1.1.1']).toBe('First sub-paragraph');
        expect(regularProject.data['dn1:1.1.2']).toBe('Second sub-paragraph');
        expect(regularProject.data['dn1:1.1.3']).toBe('');
        expect(regularProject.data['dn1:1.1.4']).toBe('Third sub-paragraph');
        expect(regularProject.data['dn1:1.2.1']).toBe('Different subsection');
        expect(regularProject.data['dn1:2.1.1']).toBe('Different section');

        const htmlProject = mockTranslations[1];
        expect(htmlProject.data['dn1:1.1.3']).toBe('{}');
    });

    test('should handle edge case - split first three-level paragraph', () => {
        const uid = 'dn1:1.1.1';
        const [sectionUid, sectionNumber] = uid.split(':');
        const sectionMainPart = getBeforeLastDot(sectionNumber);
        const sectionLastPart = parseInt(getLastNumber(sectionNumber));

        const translation = mockTranslations[0];
        const newObj = {};

        for (const key in translation.data) {
            const [keySectionUid, keySectionNumber] = key.split(':');
            
            if (keySectionUid !== sectionUid) {
                newObj[key] = translation.data[key];
                continue;
            }
            
            const keyMainPart = getBeforeLastDot(keySectionNumber);
            const keyLastPart = parseInt(getLastNumber(keySectionNumber));
            
            if (keyMainPart !== sectionMainPart) {
                newObj[key] = translation.data[key];
                continue;
            }
            
            if (keyLastPart < sectionLastPart) {
                newObj[key] = translation.data[key];
            } else if (keyLastPart === sectionLastPart) {
                newObj[key] = translation.data[key];
                const newKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                newObj[newKey] = "";
            } else {
                const newKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                newObj[newKey] = translation.data[key];
            }
        }

        expect(newObj['dn1:1.1.1']).toBe('First sub-paragraph');
        expect(newObj['dn1:1.1.2']).toBe('');
        expect(newObj['dn1:1.1.3']).toBe('Second sub-paragraph');
        expect(newObj['dn1:1.1.4']).toBe('Third sub-paragraph');
    });

    test('should maintain three-level paragraph order', () => {
        const uid = 'dn1:1.1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const sectionMainPart = getBeforeLastDot(sectionNumber);
        const sectionLastPart = parseInt(getLastNumber(sectionNumber));

        const translation = mockTranslations[0];
        const newObj = {};

        for (const key in translation.data) {
            const [keySectionUid, keySectionNumber] = key.split(':');
            
            if (keySectionUid !== sectionUid) {
                newObj[key] = translation.data[key];
                continue;
            }
            
            const keyMainPart = getBeforeLastDot(keySectionNumber);
            const keyLastPart = parseInt(getLastNumber(keySectionNumber));
            
            if (keyMainPart !== sectionMainPart) {
                newObj[key] = translation.data[key];
                continue;
            }
            
            if (keyLastPart < sectionLastPart) {
                newObj[key] = translation.data[key];
            } else if (keyLastPart === sectionLastPart) {
                newObj[key] = translation.data[key];
                const newKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                newObj[newKey] = "";
            } else {
                const newKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                newObj[newKey] = translation.data[key];
            }
        }

        const keys = Object.keys(newObj);
        expect(keys).toEqual([
            'dn1:1.1.1',
            'dn1:1.1.2',
            'dn1:1.1.3',
            'dn1:1.1.4',
            'dn1:1.2.1',
            'dn1:2.1.1'
        ]);
    });

    test('should not affect paragraphs in other subsections', () => {
        const uid = 'dn1:1.1.2';
        const [sectionUid, sectionNumber] = uid.split(':');
        const sectionMainPart = getBeforeLastDot(sectionNumber);
        const sectionLastPart = parseInt(getLastNumber(sectionNumber));

        const originalSubsection = mockTranslations[0].data['dn1:1.2.1'];
        const originalSection = mockTranslations[0].data['dn1:2.1.1'];

        mockTranslations.forEach(translation => {
            const newObj = {};

            for (const key in translation.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');
                
                if (keySectionUid !== sectionUid) {
                    newObj[key] = translation.data[key];
                    continue;
                }
                
                const keyMainPart = getBeforeLastDot(keySectionNumber);
                const keyLastPart = parseInt(getLastNumber(keySectionNumber));
                
                if (keyMainPart !== sectionMainPart) {
                    newObj[key] = translation.data[key];
                    continue;
                }
                
                if (keyLastPart < sectionLastPart) {
                    newObj[key] = translation.data[key];
                } else if (keyLastPart === sectionLastPart) {
                    newObj[key] = translation.data[key];
                    const newKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                    newObj[newKey] = translation.muid.includes('html') ? "{}" : "";
                } else {
                    const newKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                    newObj[newKey] = translation.data[key];
                }
            }
            translation.data = newObj;
        });

        expect(mockTranslations[0].data['dn1:1.2.1']).toBe(originalSubsection);
        expect(mockTranslations[0].data['dn1:2.1.1']).toBe(originalSection);
    });

    test('should verify helper function correctness', () => {
        expect(getBeforeLastDot('1.1.2')).toBe('1.1.');
        expect(getBeforeLastDot('10.20.30')).toBe('10.20.');
        
        expect(getLastNumber('1.1.2')).toBe('2');
        expect(getLastNumber('10.20.30')).toBe('30');
    });
});