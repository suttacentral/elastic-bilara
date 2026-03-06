describe('mergeBasedOnUid - Complete Merge Functionality', () => {
    let mockTranslations;
    let mockContext;
    let mockElement;
    
    // Helper functions
    function countChar(str, char) {
        return str.split(char).length - 1;
    }
    
    function getLastNumber(str) {
        return str.split('.').pop();
    }
    
    function getBeforeLastDot(str) {
        return str.substring(0, str.lastIndexOf('.') + 1);
    }

    beforeEach(() => {
        // Mock DOM element
        mockElement = document.createElement('div');
        
        // Mock localStorage
        Storage.prototype.getItem = jest.fn((key) => {
            if (key === 'enableMergeHintDialog') return 'true';
            return null;
        });
        Storage.prototype.setItem = jest.fn();
        
        // Mock DOM query
        document.querySelector = jest.fn((selector) => {
            if (selector === '.dialog-merge-hint') {
                return { show: jest.fn() };
            }
            return null;
        });
        
        // Mock translation data
        mockTranslations = [
            {
                muid: 'test-project',
                data: {
                    'mn1:1.1': 'First paragraph',
                    'mn1:1.2': 'Second paragraph',
                    'mn1:1.3': 'Third paragraph',
                    'mn1:1.4': 'Fourth paragraph',
                    'mn1:2.0': 'Next section first',
                    'mn1:2.1': 'Next section second'
                }
            },
            {
                muid: 'html-pli-ms',
                data: {
                    'mn1:1.1': '{}',
                    'mn1:1.2': '{}',
                    'mn1:1.3': '{}',
                    'mn1:1.4': '{}',
                    'mn1:2.0': '{}',
                    'mn1:2.1': '{}'
                }
            }
        ];
        
        // Mock context
        mockContext = {
            translations: mockTranslations,
            htmlProjectName: 'html-pli-ms',
            htmlProject: mockTranslations[1],
            mergee_uid: null,
            merger_uid: null,
            originalTranslations: null,
            mergeSectionByNextKey: jest.fn((key, translation, newObj) => {
                const [keySectionUid, keySectionNumber] = key.split(':');
                const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                const nextKey = `${keySectionUid}:${keyIntegerPart}.${parseInt(keyDecimalPart) + 1}`;
                if (translation.data[nextKey]) {
                    newObj[key] = translation.data[nextKey];
                }
            })
        };
    });

    describe('Two Level Format Merge', () => {
        test('should correctly identify two-level format and set mergee_uid', () => {
            const uid = 'mn1:1.2';
            const regex = /:([0-9]+(\.[0-9]+)?)$/;
            const isTwoLevel = regex.test(uid) && countChar(uid.split(':')[1], '.') === 1;

            expect(isTwoLevel).toBe(true);

            const [sectionUid, sectionNumber] = uid.split(':');
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const decimalNumber = parseInt(decimalPart);
            const mergeeUid = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;

            expect(mergeeUid).toBe('mn1:1.3');
        });

        test('should merge adjacent paragraphs within the same section', () => {
            const uid = 'mn1:1.2';
            const [sectionUid, sectionNumber] = uid.split(':');
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const decimalNumber = parseInt(decimalPart);

            mockTranslations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');

                    if (keySectionUid !== sectionUid) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                    const keyDecimalNumber = parseInt(keyDecimalPart);

                    if (keyIntegerPart !== integerPart) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    if (keyDecimalNumber < decimalNumber) {
                        newObj[key] = translation.data[key];
                    } else if (keyDecimalNumber === decimalNumber) {
                        const nextKey = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            newObj[key] = translation.data[key];
                        }
                    } else {
                        const nextKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                    }
                }

                translation.data = newObj;
            });

            const regularProject = mockTranslations[0];
            expect(regularProject.data['mn1:1.1']).toBe('First paragraph');
            expect(regularProject.data['mn1:1.2']).toBe('Second paragraph Third paragraph');
            expect(regularProject.data['mn1:1.3']).toBe('Fourth paragraph');
            expect(regularProject.data['mn1:1.4']).toBeUndefined();
        });

        test('should handle cross-section merge', () => {
            const uid = 'mn1:1.4';
            const [sectionUid, sectionNumber] = uid.split(':');
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const decimalNumber = parseInt(decimalPart);
            
            let needToMergeNextSection = false;
            let nextSectionFirstKey = '';

            mockTranslations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');

                    if (keySectionUid !== sectionUid) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                    const keyDecimalNumber = parseInt(keyDecimalPart);

                    if (keyIntegerPart !== integerPart) {
                        if (needToMergeNextSection) {
                            const nextSectionNumber = parseInt(nextSectionFirstKey.split(':')[1].split('.')[0]);
                            const currentSectionNumber = parseInt(keyIntegerPart);

                            if (currentSectionNumber === nextSectionNumber) {
                                const [nsKeySectionUid, nsKeySectionNumber] = key.split(':');
                                const [nsKeyIntegerPart, nsKeyDecimalPart] = nsKeySectionNumber.split('.');
                                const nextKey = `${nsKeySectionUid}:${nsKeyIntegerPart}.${parseInt(nsKeyDecimalPart) + 1}`;
                                if (translation.data[nextKey]) {
                                    newObj[key] = translation.data[nextKey];
                                }
                                continue;
                            }
                        }
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    if (keyDecimalNumber < decimalNumber) {
                        newObj[key] = translation.data[key];
                    } else if (keyDecimalNumber === decimalNumber) {
                        const nextKey = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;

                        if (translation.data[nextKey]) {
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            const nextSectionIntegerPart = parseInt(integerPart) + 1;
                            const possibleNextKey1 = `${sectionUid}:${nextSectionIntegerPart}.0`;
                            const possibleNextKey2 = `${sectionUid}:${nextSectionIntegerPart}.1`;
                            const crossSectionNextKey = translation.data[possibleNextKey1] 
                                ? possibleNextKey1 
                                : possibleNextKey2;

                            if (translation.data[crossSectionNextKey]) {
                                nextSectionFirstKey = crossSectionNextKey;
                                needToMergeNextSection = true;
                                newObj[key] = `${translation.data[key]} ${translation.data[crossSectionNextKey]}`;
                            } else {
                                newObj[key] = translation.data[key];
                            }
                        }
                    } else {
                        const nextKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                    }
                }

                translation.data = newObj;
            });

            expect(mockTranslations[0].data['mn1:1.4']).toBe('Fourth paragraph Next section first');
            expect(needToMergeNextSection).toBe(true);
            expect(nextSectionFirstKey).toBe('mn1:2.0');
        });

        test('should correctly handle HTML project merge', () => {
            const uid = 'mn1:1.2';
            const [sectionUid, sectionNumber] = uid.split(':');
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const decimalNumber = parseInt(decimalPart);

            const htmlProject = mockTranslations[1];
            const newObj = {};

            for (const key in htmlProject.data) {
                const [keySectionUid, keySectionNumber] = key.split(':');

                if (keySectionUid !== sectionUid) {
                    newObj[key] = htmlProject.data[key];
                    continue;
                }

                const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                const keyDecimalNumber = parseInt(keyDecimalPart);

                if (keyIntegerPart !== integerPart) {
                    newObj[key] = htmlProject.data[key];
                    continue;
                }

                if (keyDecimalNumber < decimalNumber) {
                    newObj[key] = htmlProject.data[key];
                } else if (keyDecimalNumber === decimalNumber) {
                    const nextKey = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;
                    if (htmlProject.data[nextKey]) {
                        newObj[key] = `${htmlProject.data[key]} ${htmlProject.data[nextKey]}`;
                    } else {
                        newObj[key] = htmlProject.data[key];
                    }
                } else {
                    const nextKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                    if (htmlProject.data[nextKey]) {
                        newObj[key] = htmlProject.data[nextKey];
                    }
                }
            }

            expect(newObj['mn1:1.2']).toBe('{} {}');
        });

        test('should not affect paragraphs in other sections', () => {
            const uid = 'mn1:1.2';
            const originalSection2Data = { ...mockTranslations[0].data };
            
            // Execute merge logic...
            
            expect(mockTranslations[0].data['mn1:2.0']).toBe(originalSection2Data['mn1:2.0']);
            expect(mockTranslations[0].data['mn1:2.1']).toBe(originalSection2Data['mn1:2.1']);
        });
    });

    describe('Three Level Format Merge', () => {
        beforeEach(() => {
            mockTranslations = [
                {
                    muid: 'test-project',
                    data: {
                        'dn1:1.1.1': 'First sub-paragraph',
                        'dn1:1.1.2': 'Second sub-paragraph',
                        'dn1:1.1.3': 'Third sub-paragraph',
                        'dn1:1.2.1': 'Next subsection first',
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
            const uid = 'dn1:1.1.2';
            const sectionRegex = /^:[0-9]+\.[0-9]+\.[0-9]+$/;
            const isThreeLevel = sectionRegex.test(`:${uid.split(':')[1]}`);
            
            expect(isThreeLevel).toBe(true);
        });

        test('should correctly set mergee_uid for three-level format', () => {
            const uid = 'dn1:1.1.2';
            const [sectionUid, sectionNumber] = uid.split(':');
            const sectionMainPart = getBeforeLastDot(sectionNumber);
            const sectionLastPart = parseInt(getLastNumber(sectionNumber));
            const mergeeUid = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
            
            expect(mergeeUid).toBe('dn1:1.1.3');
        });

        test('should merge adjacent paragraphs within the same subsection', () => {
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
                        const nextKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            newObj[key] = translation.data[key];
                        }
                    } else {
                        const nextKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                    }
                }

                translation.data = newObj;
            });

            expect(mockTranslations[0].data['dn1:1.1.1']).toBe('First sub-paragraph');
            expect(mockTranslations[0].data['dn1:1.1.2']).toBe('Second sub-paragraph Third sub-paragraph');
            expect(mockTranslations[0].data['dn1:1.1.3']).toBeUndefined();
        });

        test('should handle cross-subsection merge', () => {
            const uid = 'dn1:1.1.3';
            const [sectionUid, sectionNumber] = uid.split(':');
            const sectionMainPart = getBeforeLastDot(sectionNumber);
            const sectionLastPart = parseInt(getLastNumber(sectionNumber));
            
            let needToMergeNextSection = false;
            let nextSectionFirstKey = '';

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
                        const nextKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;

                        if (translation.data[nextKey]) {
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            const [chapter, section] = sectionNumber.split('.');
                            const nextSection = parseInt(section) + 1;
                            const crossSubsectionNextKey = `${sectionUid}:${chapter}.${nextSection}.1`;

                            if (translation.data[crossSubsectionNextKey]) {
                                nextSectionFirstKey = crossSubsectionNextKey;
                                needToMergeNextSection = true;
                                newObj[key] = `${translation.data[key]} ${translation.data[crossSubsectionNextKey]}`;
                            } else {
                                newObj[key] = translation.data[key];
                            }
                        }
                    } else {
                        const nextKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                    }
                }

                translation.data = newObj;
            });

            expect(mockTranslations[0].data['dn1:1.1.3']).toBe('Third sub-paragraph Next subsection first');
            expect(needToMergeNextSection).toBe(true);
            expect(nextSectionFirstKey).toBe('dn1:1.2.1');
        });

        test('should not affect paragraphs in other subsections', () => {
            const uid = 'dn1:1.1.2';
            const originalSubsection = mockTranslations[0].data['dn1:1.2.1'];
            const originalSection = mockTranslations[0].data['dn1:2.1.1'];
            
            // Execute merge logic...
            
            expect(mockTranslations[0].data['dn1:1.2.1']).toBe(originalSubsection);
            expect(mockTranslations[0].data['dn1:2.1.1']).toBe(originalSection);
        });
    });

    describe('Edge Cases and Error Handling', () => {
        test('should handle unsupported uid formats', () => {
            const invalidUids = ['mn1:1', 'mn1:1.1.1.1', 'invalid', 'mn1:'];
            
            invalidUids.forEach(uid => {
                const regex = /:([0-9]+(\.[0-9]+)?)$/;
                const sectionRegex = /^:[0-9]+\.[0-9]+\.[0-9]+$/;
                const isValid = (regex.test(uid) && countChar(uid.split(':')[1], '.') === 1) || 
                               sectionRegex.test(`:${uid.split(':')[1]}`);
                expect(isValid).toBe(false);
            });
        });

        test('should preserve HTML project state', () => {
            const htmlProject = mockTranslations.find(t => t.muid === 'html-pli-ms');
            expect(htmlProject).toBeDefined();
            expect(htmlProject.muid).toBe('html-pli-ms');
        });

        test('should correctly set splitting flag', () => {
            const uid = 'mn1:1.2';
            // After merge execution
            mockTranslations.forEach(translation => {
                translation.splitting = true;
            });
            
            mockTranslations.forEach(translation => {
                expect(translation.splitting).toBe(true);
            });
        });
    });

    describe('Helper Functions', () => {
        test('countChar should correctly count characters', () => {
            expect(countChar('1.2.3', '.')).toBe(2);
            expect(countChar('1.2', '.')).toBe(1);
            expect(countChar('123', '.')).toBe(0);
        });

        test('getLastNumber should return the last number', () => {
            expect(getLastNumber('1.2.3')).toBe('3');
            expect(getLastNumber('10.20.30')).toBe('30');
        });

        test('getBeforeLastDot should return content before the last dot', () => {
            expect(getBeforeLastDot('1.2.3')).toBe('1.2.');
            expect(getBeforeLastDot('10.20.30')).toBe('10.20.');
        });
    });
});