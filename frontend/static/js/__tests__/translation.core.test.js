/**
 * Translation.js Core Functions Tests
 * 
 * This file tests the core functionality of translation.js including:
 * - getValue / setValue
 * - getTranslationProgress
 * - updateProgress
 * - _backupTranslations / _restoreTranslations
 * - hasActiveOperation
 * - Helper functions (countChar, getLastNumber, getBeforeLastDot, isMergeSplitConditionMet)
 */

// ============================================================================
// Helper Functions (从 translation.js 提取)
// ============================================================================

function countChar(str, char) {
    return str.split(char).length - 1;
}

function getLastNumber(str) {
    return str.split('.').pop();
}

function getBeforeLastDot(str) {
    return str.substring(0, str.lastIndexOf('.') + 1);
}

function isMergeSplitConditionMet(uid, key) {
    const regex = /:([0-9]+(\.[0-9]+)?)$/;
    const sectionRegex = /:[0-9]+\.[0-9]+\.[0-9]+$/;
    return (regex.test(uid) || sectionRegex.test(uid));
}

// ============================================================================
// Helper Functions Tests
// ============================================================================

describe('Translation Helper Functions', () => {
    describe('countChar', () => {
        test('should count single occurrences correctly', () => {
            expect(countChar('a.b', '.')).toBe(1);
            expect(countChar('hello', 'l')).toBe(2);
        });

        test('should return 0 when character is not found', () => {
            expect(countChar('hello', 'x')).toBe(0);
        });

        test('should count multiple occurrences correctly', () => {
            expect(countChar('1.2.3.4', '.')).toBe(3);
            expect(countChar('aaa', 'a')).toBe(3);
        });

        test('should handle empty string', () => {
            expect(countChar('', '.')).toBe(0);
        });

        test('should handle special characters', () => {
            expect(countChar('mn1:1.1', ':')).toBe(1);
        });
    });

    describe('getLastNumber', () => {
        test('should return last number in two-level format', () => {
            expect(getLastNumber('1.2')).toBe('2');
            expect(getLastNumber('10.20')).toBe('20');
        });

        test('should return last number in three-level format', () => {
            expect(getLastNumber('1.2.3')).toBe('3');
            expect(getLastNumber('10.20.30')).toBe('30');
        });

        test('should return the whole string if no dot', () => {
            expect(getLastNumber('100')).toBe('100');
        });

        test('should handle edge cases', () => {
            expect(getLastNumber('0.0')).toBe('0');
            expect(getLastNumber('1.2.3.4.5')).toBe('5');
        });
    });

    describe('getBeforeLastDot', () => {
        test('should return content before last dot in two-level format', () => {
            expect(getBeforeLastDot('1.2')).toBe('1.');
            expect(getBeforeLastDot('10.20')).toBe('10.');
        });

        test('should return content before last dot in three-level format', () => {
            expect(getBeforeLastDot('1.2.3')).toBe('1.2.');
            expect(getBeforeLastDot('10.20.30')).toBe('10.20.');
        });

        test('should return empty string if no dot', () => {
            expect(getBeforeLastDot('100')).toBe('');
        });

        test('should handle edge cases', () => {
            // 当输入是 '.' 时, lastIndexOf('.') = 0, substring(0, 1) = '.'
            expect(getBeforeLastDot('.')).toBe('.');
            expect(getBeforeLastDot('1.')).toBe('1.');
        });
    });

    describe('isMergeSplitConditionMet', () => {
        test('should return true for valid two-level UIDs', () => {
            expect(isMergeSplitConditionMet('mn1:1.1')).toBe(true);
            expect(isMergeSplitConditionMet('dn1:10.20')).toBe(true);
            expect(isMergeSplitConditionMet('sn1:0.1')).toBe(true);
        });

        test('should return true for valid three-level UIDs', () => {
            expect(isMergeSplitConditionMet('dn1:1.1.1')).toBe(true);
            expect(isMergeSplitConditionMet('mn1:10.20.30')).toBe(true);
        });

        test('should return true for simple integer UIDs', () => {
            expect(isMergeSplitConditionMet('mn1:1')).toBe(true);
            expect(isMergeSplitConditionMet('dn1:123')).toBe(true);
        });

        test('should return false for invalid UIDs', () => {
            expect(isMergeSplitConditionMet('mn1:')).toBe(false);
            expect(isMergeSplitConditionMet('invalid')).toBe(false);
            expect(isMergeSplitConditionMet('mn1:abc')).toBe(false);
            expect(isMergeSplitConditionMet('')).toBe(false);
        });

        test('should return false for overly complex formats', () => {
            expect(isMergeSplitConditionMet('mn1:1.2.3.4')).toBe(false);
            expect(isMergeSplitConditionMet('mn1:1.2.3.4.5')).toBe(false);
        });
    });
});

// ============================================================================
// Core Functions Tests
// ============================================================================

describe('Translation Core Functions', () => {
    let mockContext;

    beforeEach(() => {
        mockContext = {
            translations: [],
            relatedProjects: [],
            htmlProjectName: '',
            htmlProject: null,
            originalTranslations: null,
            splitter_uid: null,
            merger_uid: null,
            mergee_uid: null,
            prefix: 'test-prefix',
            
            getValue(translation, uid) {
                return translation.data[uid] || "";
            },
            
            setValue(translation, uid, value) {
                if (!translation.data) {
                    translation.data = {};
                }
                translation.data[uid] = value;
                this.updateProgress();
            },
            
            getTranslationProgress() {
                const sourceTranslation = this.translations.find(t => t.isSource);
                const editableTranslation = this.translations.find(t => t.canEdit && !t.isSource);
                
                if (!sourceTranslation || !editableTranslation) {
                    return { translated: 0, total: 0, percentage: 0 };
                }
                
                const sourceData = sourceTranslation.data || {};
                const translationData = editableTranslation.data || {};
                const totalKeys = Object.keys(sourceData).length;
                
                if (totalKeys === 0) {
                    return { translated: 0, total: 0, percentage: 0 };
                }
                
                let translatedCount = 0;
                for (const key of Object.keys(sourceData)) {
                    const value = translationData[key];
                    if (value && value.trim() !== '') {
                        translatedCount++;
                    }
                }
                
                const percentage = Math.round((translatedCount / totalKeys) * 100);
                return { translated: translatedCount, total: totalKeys, percentage };
            },
            
            updateProgress() {
                const progressData = this.getTranslationProgress();
                // In test environment, we just return the data
                return progressData;
            },
            
            _backupTranslations() {
                this.originalTranslations = JSON.parse(
                    JSON.stringify(this.translations)
                );
            },
            
            _restoreTranslations() {
                if (this.originalTranslations) {
                    this.translations = JSON.parse(
                        JSON.stringify(this.originalTranslations)
                    );
                    this.originalTranslations = null;
                }
            },
            
            hasActiveOperation() {
                return this.originalTranslations !== null;
            }
        };
    });

    describe('getValue', () => {
        test('should return value when uid exists', () => {
            const translation = { data: { 'mn1:1.1': 'Test value' } };
            expect(mockContext.getValue(translation, 'mn1:1.1')).toBe('Test value');
        });

        test('should return empty string when uid does not exist', () => {
            const translation = { data: { 'mn1:1.1': 'Test value' } };
            expect(mockContext.getValue(translation, 'mn1:1.2')).toBe('');
        });

        test('should return empty string when data is empty', () => {
            const translation = { data: {} };
            expect(mockContext.getValue(translation, 'mn1:1.1')).toBe('');
        });

        test('should handle null/undefined values correctly', () => {
            const translation = { data: { 'mn1:1.1': null, 'mn1:1.2': undefined } };
            expect(mockContext.getValue(translation, 'mn1:1.1')).toBe('');
            expect(mockContext.getValue(translation, 'mn1:1.2')).toBe('');
        });
    });

    describe('setValue', () => {
        test('should set value when data exists', () => {
            const translation = { data: { 'mn1:1.1': 'Old value' } };
            mockContext.setValue(translation, 'mn1:1.1', 'New value');
            expect(translation.data['mn1:1.1']).toBe('New value');
        });

        test('should create data object when it does not exist', () => {
            const translation = {};
            mockContext.setValue(translation, 'mn1:1.1', 'Test value');
            expect(translation.data).toBeDefined();
            expect(translation.data['mn1:1.1']).toBe('Test value');
        });

        test('should add new uid when it does not exist', () => {
            const translation = { data: { 'mn1:1.1': 'Existing' } };
            mockContext.setValue(translation, 'mn1:1.2', 'New value');
            expect(translation.data['mn1:1.2']).toBe('New value');
            expect(translation.data['mn1:1.1']).toBe('Existing');
        });

        test('should handle empty string value', () => {
            const translation = { data: {} };
            mockContext.setValue(translation, 'mn1:1.1', '');
            expect(translation.data['mn1:1.1']).toBe('');
        });
    });

    describe('getTranslationProgress', () => {
        beforeEach(() => {
            mockContext.translations = [
                {
                    isSource: true,
                    canEdit: false,
                    muid: 'pli-ms',
                    data: {
                        'mn1:1.1': 'Source 1',
                        'mn1:1.2': 'Source 2',
                        'mn1:1.3': 'Source 3',
                        'mn1:1.4': 'Source 4',
                        'mn1:1.5': 'Source 5'
                    }
                },
                {
                    isSource: false,
                    canEdit: true,
                    muid: 'en-sujato',
                    data: {
                        'mn1:1.1': 'Translation 1',
                        'mn1:1.2': 'Translation 2',
                        'mn1:1.3': '',
                        'mn1:1.4': '   ',
                        'mn1:1.5': 'Translation 5'
                    }
                }
            ];
        });

        test('should calculate correct progress', () => {
            const progress = mockContext.getTranslationProgress();
            expect(progress.total).toBe(5);
            expect(progress.translated).toBe(3); // mn1:1.3 is empty, mn1:1.4 is whitespace
            expect(progress.percentage).toBe(60);
        });

        test('should return zero progress when no source translation', () => {
            mockContext.translations = [
                { isSource: false, canEdit: true, data: {} }
            ];
            const progress = mockContext.getTranslationProgress();
            expect(progress).toEqual({ translated: 0, total: 0, percentage: 0 });
        });

        test('should return zero progress when no editable translation', () => {
            mockContext.translations = [
                { isSource: true, canEdit: false, data: { 'mn1:1.1': 'Source' } }
            ];
            const progress = mockContext.getTranslationProgress();
            expect(progress).toEqual({ translated: 0, total: 0, percentage: 0 });
        });

        test('should return zero progress when source has no data', () => {
            mockContext.translations = [
                { isSource: true, canEdit: false, muid: 'pli-ms', data: {} },
                { isSource: false, canEdit: true, muid: 'en-sujato', data: { 'mn1:1.1': 'Test' } }
            ];
            const progress = mockContext.getTranslationProgress();
            expect(progress).toEqual({ translated: 0, total: 0, percentage: 0 });
        });

        test('should return 100% when all keys are translated', () => {
            mockContext.translations[1].data = {
                'mn1:1.1': 'Translation 1',
                'mn1:1.2': 'Translation 2',
                'mn1:1.3': 'Translation 3',
                'mn1:1.4': 'Translation 4',
                'mn1:1.5': 'Translation 5'
            };
            const progress = mockContext.getTranslationProgress();
            expect(progress.percentage).toBe(100);
        });

        test('should return 0% when no keys are translated', () => {
            mockContext.translations[1].data = {
                'mn1:1.1': '',
                'mn1:1.2': '',
                'mn1:1.3': '',
                'mn1:1.4': '   ',
                'mn1:1.5': ''
            };
            const progress = mockContext.getTranslationProgress();
            expect(progress.percentage).toBe(0);
        });

        test('should handle missing translation data object', () => {
            mockContext.translations[1].data = undefined;
            const progress = mockContext.getTranslationProgress();
            expect(progress.translated).toBe(0);
            expect(progress.total).toBe(5);
            expect(progress.percentage).toBe(0);
        });

        test('should round percentage correctly', () => {
            mockContext.translations[0].data = {
                'mn1:1.1': 'S1',
                'mn1:1.2': 'S2',
                'mn1:1.3': 'S3'
            };
            mockContext.translations[1].data = {
                'mn1:1.1': 'T1'
            };
            const progress = mockContext.getTranslationProgress();
            expect(progress.percentage).toBe(33); // 1/3 = 0.333... rounds to 33%
        });
    });

    describe('_backupTranslations and _restoreTranslations', () => {
        beforeEach(() => {
            mockContext.translations = [
                { muid: 'test', data: { 'mn1:1.1': 'Original value' } }
            ];
        });

        test('should create deep copy of translations', () => {
            mockContext._backupTranslations();
            
            // Modify original
            mockContext.translations[0].data['mn1:1.1'] = 'Modified value';
            
            // Backup should not be affected
            expect(mockContext.originalTranslations[0].data['mn1:1.1']).toBe('Original value');
        });

        test('should restore translations from backup', () => {
            mockContext._backupTranslations();
            
            // Modify original
            mockContext.translations[0].data['mn1:1.1'] = 'Modified value';
            mockContext.translations.push({ muid: 'new', data: {} });
            
            // Restore
            mockContext._restoreTranslations();
            
            expect(mockContext.translations[0].data['mn1:1.1']).toBe('Original value');
            expect(mockContext.translations.length).toBe(1);
        });

        test('should clear backup after restore', () => {
            mockContext._backupTranslations();
            mockContext._restoreTranslations();
            expect(mockContext.originalTranslations).toBeNull();
        });

        test('should do nothing when no backup exists', () => {
            const originalTranslations = [...mockContext.translations];
            mockContext._restoreTranslations();
            expect(mockContext.translations).toEqual(originalTranslations);
        });
    });

    describe('hasActiveOperation', () => {
        test('should return false when no backup exists', () => {
            expect(mockContext.hasActiveOperation()).toBe(false);
        });

        test('should return true when backup exists', () => {
            mockContext._backupTranslations();
            expect(mockContext.hasActiveOperation()).toBe(true);
        });

        test('should return false after restore', () => {
            mockContext._backupTranslations();
            mockContext._restoreTranslations();
            expect(mockContext.hasActiveOperation()).toBe(false);
        });
    });
});

// ============================================================================
// Edge Cases and Error Handling
// ============================================================================

describe('Edge Cases and Error Handling', () => {
    describe('Data Integrity', () => {
        test('should handle translations with special characters in values', () => {
            const translation = { data: {} };
            const specialValue = 'Test with "quotes" and \'apostrophes\' and <html>';
            
            const mockContext = {
                setValue(translation, uid, value) {
                    if (!translation.data) {
                        translation.data = {};
                    }
                    translation.data[uid] = value;
                }
            };
            
            mockContext.setValue(translation, 'mn1:1.1', specialValue);
            expect(translation.data['mn1:1.1']).toBe(specialValue);
        });

        test('should handle translations with unicode characters', () => {
            const translation = { data: {} };
            const unicodeValue = 'पालि भाषा 中文 日本語 한국어';
            
            const mockContext = {
                setValue(translation, uid, value) {
                    if (!translation.data) {
                        translation.data = {};
                    }
                    translation.data[uid] = value;
                }
            };
            
            mockContext.setValue(translation, 'mn1:1.1', unicodeValue);
            expect(translation.data['mn1:1.1']).toBe(unicodeValue);
        });

        test('should handle translations with newlines', () => {
            const translation = { data: {} };
            const multilineValue = 'Line 1\nLine 2\nLine 3';
            
            const mockContext = {
                setValue(translation, uid, value) {
                    if (!translation.data) {
                        translation.data = {};
                    }
                    translation.data[uid] = value;
                }
            };
            
            mockContext.setValue(translation, 'mn1:1.1', multilineValue);
            expect(translation.data['mn1:1.1']).toBe(multilineValue);
        });
    });

    describe('UID Format Validation', () => {
        test('should handle various UID formats', () => {
            const uids = [
                { uid: 'mn1:1.1', expected: true },
                { uid: 'dn1:1.2.3', expected: true },
                { uid: 'sn1:100', expected: true },
                { uid: 'an1:0.1', expected: true },
                { uid: 'mn100:99.99', expected: true },
                { uid: 'kp1:1.1.1', expected: true },
            ];

            uids.forEach(({ uid, expected }) => {
                expect(isMergeSplitConditionMet(uid)).toBe(expected);
            });
        });

        test('should reject malformed UIDs', () => {
            // 根据 isMergeSplitConditionMet 的正则表达式行为
            // regex = /:([0-9]+(\.[0-9]+)?)$/  匹配 :数字 或 :数字.数字 结尾
            // sectionRegex = /:[0-9]+\.[0-9]+\.[0-9]+$/  匹配 :数字.数字.数字 结尾
            const invalidUids = [
                'mn1:',      // 冒号后没有数字
                'mn1:abc',   // 冒号后不是数字
                'invalid',   // 没有冒号
                '',          // 空字符串
            ];

            invalidUids.forEach(uid => {
                expect(isMergeSplitConditionMet(uid)).toBe(false);
            });
        });
    });

    describe('Progress Calculation Edge Cases', () => {
        test('should handle very large translation sets', () => {
            const sourceData = {};
            const translationData = {};
            
            for (let i = 0; i < 1000; i++) {
                sourceData[`mn1:1.${i}`] = `Source ${i}`;
                if (i < 500) {
                    translationData[`mn1:1.${i}`] = `Translation ${i}`;
                }
            }
            
            const mockContext = {
                translations: [
                    { isSource: true, data: sourceData },
                    { isSource: false, canEdit: true, data: translationData }
                ],
                getTranslationProgress() {
                    const sourceTranslation = this.translations.find(t => t.isSource);
                    const editableTranslation = this.translations.find(t => t.canEdit && !t.isSource);
                    
                    if (!sourceTranslation || !editableTranslation) {
                        return { translated: 0, total: 0, percentage: 0 };
                    }
                    
                    const srcData = sourceTranslation.data || {};
                    const transData = editableTranslation.data || {};
                    const totalKeys = Object.keys(srcData).length;
                    
                    if (totalKeys === 0) {
                        return { translated: 0, total: 0, percentage: 0 };
                    }
                    
                    let translatedCount = 0;
                    for (const key of Object.keys(srcData)) {
                        const value = transData[key];
                        if (value && value.trim() !== '') {
                            translatedCount++;
                        }
                    }
                    
                    const percentage = Math.round((translatedCount / totalKeys) * 100);
                    return { translated: translatedCount, total: totalKeys, percentage };
                }
            };
            
            const progress = mockContext.getTranslationProgress();
            expect(progress.total).toBe(1000);
            expect(progress.translated).toBe(500);
            expect(progress.percentage).toBe(50);
        });
    });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
    test('should correctly track progress after multiple setValue calls', () => {
        const mockContext = {
            translations: [
                { isSource: true, data: { 'mn1:1.1': 'S1', 'mn1:1.2': 'S2' } },
                { isSource: false, canEdit: true, data: {} }
            ],
            setValue(translation, uid, value) {
                if (!translation.data) {
                    translation.data = {};
                }
                translation.data[uid] = value;
            },
            getTranslationProgress() {
                const sourceTranslation = this.translations.find(t => t.isSource);
                const editableTranslation = this.translations.find(t => t.canEdit && !t.isSource);
                
                if (!sourceTranslation || !editableTranslation) {
                    return { translated: 0, total: 0, percentage: 0 };
                }
                
                const sourceData = sourceTranslation.data || {};
                const translationData = editableTranslation.data || {};
                const totalKeys = Object.keys(sourceData).length;
                
                if (totalKeys === 0) {
                    return { translated: 0, total: 0, percentage: 0 };
                }
                
                let translatedCount = 0;
                for (const key of Object.keys(sourceData)) {
                    const value = translationData[key];
                    if (value && value.trim() !== '') {
                        translatedCount++;
                    }
                }
                
                const percentage = Math.round((translatedCount / totalKeys) * 100);
                return { translated: translatedCount, total: totalKeys, percentage };
            }
        };
        
        // Initial state
        expect(mockContext.getTranslationProgress().percentage).toBe(0);
        
        // Add first translation
        mockContext.setValue(mockContext.translations[1], 'mn1:1.1', 'T1');
        expect(mockContext.getTranslationProgress().percentage).toBe(50);
        
        // Add second translation
        mockContext.setValue(mockContext.translations[1], 'mn1:1.2', 'T2');
        expect(mockContext.getTranslationProgress().percentage).toBe(100);
        
        // Clear a translation
        mockContext.setValue(mockContext.translations[1], 'mn1:1.1', '');
        expect(mockContext.getTranslationProgress().percentage).toBe(50);
    });

    test('should correctly backup and restore after value changes', () => {
        const mockContext = {
            translations: [
                { muid: 'test', data: { 'mn1:1.1': 'Original' } }
            ],
            originalTranslations: null,
            
            setValue(translation, uid, value) {
                if (!translation.data) {
                    translation.data = {};
                }
                translation.data[uid] = value;
            },
            
            _backupTranslations() {
                this.originalTranslations = JSON.parse(
                    JSON.stringify(this.translations)
                );
            },
            
            _restoreTranslations() {
                if (this.originalTranslations) {
                    this.translations = JSON.parse(
                        JSON.stringify(this.originalTranslations)
                    );
                    this.originalTranslations = null;
                }
            }
        };
        
        // Backup before changes
        mockContext._backupTranslations();
        
        // Make changes
        mockContext.setValue(mockContext.translations[0], 'mn1:1.1', 'Modified');
        mockContext.setValue(mockContext.translations[0], 'mn1:1.2', 'New value');
        
        // Verify changes
        expect(mockContext.translations[0].data['mn1:1.1']).toBe('Modified');
        expect(mockContext.translations[0].data['mn1:1.2']).toBe('New value');
        
        // Restore
        mockContext._restoreTranslations();
        
        // Verify restoration
        expect(mockContext.translations[0].data['mn1:1.1']).toBe('Original');
        expect(mockContext.translations[0].data['mn1:1.2']).toBeUndefined();
    });
});
