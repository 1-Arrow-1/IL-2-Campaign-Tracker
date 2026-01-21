/**
 * IL-2 Campaign Tracker - JavaScript i18n Helper
 * 
 * Provides translation functionality for the web frontend (Campaign Service Record).
 * 
 * Usage:
 *     // Initialize (once at startup)
 *     await i18n.init('de');  // or 'en', etc.
 *     
 *     // Translate strings
 *     i18n.t('web.stat.total_kills');  
 *     // → "Gesamt-Abschüsse" (de) or "Total Kills" (en fallback)
 *     
 *     // With parameters
 *     i18n.t('web.title.campaign_detail', {campaign_name: 'Stalingrad'});
 *     // → "Stalingrad - Kampagnen-Dienstakte"
 *     
 *     // Get current locale
 *     const locale = i18n.getLocale();  // → 'de'
 */

const i18n = {
    currentLocale: 'en',
    translations: {},
    initialized: false,
    initInProgress: false,
    _initSequence: 0,
    missingTranslationPlaceholder: '[missing translation]',
    
    /**
     * Initialize i18n with given locale.
     * Loads fallback (en) and requested locale.
     * 
     * @param {string} locale - Locale code ('en', 'de', etc.)
     * @returns {Promise<void>}
     */
    async init(locale = 'en') {
        console.log(`[i18n] Initializing with locale: ${locale}`);
        const initToken = ++this._initSequence;
        this.initInProgress = true;
        
        try {
            // Load fallback (English) first
            this.translations.en = await this.loadLocale('en');
            
            if (!this.translations.en) {
                console.error('[i18n] CRITICAL: Failed to load English fallback!');
            }
            
            // Load requested locale (if different from fallback)
            if (locale !== 'en') {
                this.translations[locale] = await this.loadLocale(locale);
                
                if (!this.translations[locale]) {
                    console.warn(`[i18n] Locale '${locale}' not available, using 'en' fallback`);
                    locale = 'en';
                }
            }
            
            if (initToken !== this._initSequence) {
                console.warn('[i18n] Initialization superseded by a newer request');
                return;
            }

            this.currentLocale = locale;
            this.initialized = true;
            console.log(`[i18n] Initialized successfully with locale: ${locale}`);
        } catch (error) {
            console.error('[i18n] Initialization error:', error);
            if (initToken !== this._initSequence) {
                console.warn('[i18n] Initialization error superseded by a newer request');
                return;
            }
            this.currentLocale = 'en';
            this.initialized = true;
        } finally {
            if (initToken === this._initSequence) {
                this.initInProgress = false;
            }
        }
    },
    
    /**
     * Load translation file for given locale.
     * 
     * @param {string} locale - Locale code
     * @returns {Promise<object>} Translation data
     */
    async loadLocale(locale) {
        try {
            // Try campaign_service_record/static/locales first (symlink)
            let response = await fetch(`/static/locales/${locale}.json`);
            
            // Fallback to root locales directory
            if (!response.ok) {
                response = await fetch(`/locales/${locale}.json`);
            }
            
            if (!response.ok) {
                console.warn(`[i18n] Failed to load locale: ${locale} (${response.status})`);
                return null;
            }
            
            const data = await response.json();
            console.log(`[i18n] Loaded locale: ${locale}`);
            return data;
        } catch (error) {
            console.error(`[i18n] Error loading locale ${locale}:`, error);
            return null;
        }
    },
    
    /**
     * Set current locale.
     * Loads the locale if not already loaded.
     * 
     * @param {string} locale - Locale code
     * @returns {Promise<void>}
     */
    async setLocale(locale) {
        console.log(`[i18n] Setting locale to: ${locale}`);
        
        // Ensure fallback is always loaded
        if (!this.translations.en) {
            this.translations.en = await this.loadLocale('en');
        }
        
        // Load requested locale if not already loaded
        if (!this.translations[locale]) {
            this.translations[locale] = await this.loadLocale(locale);
            
            if (!this.translations[locale]) {
                console.warn(`[i18n] Locale '${locale}' not available, staying with '${this.currentLocale}'`);
                return;
            }
        }
        
        this.currentLocale = locale;
        console.log(`[i18n] Locale set to: ${locale}`);
    },
    
    /**
     * Get current locale code.
     * 
     * @returns {string} Current locale code
     */
    getLocale() {
        return this.currentLocale;
    },
    
    /**
     * Navigate nested object using key parts.
     * 
     * @param {object} data - Object to navigate
     * @param {Array<string>} keyParts - Array of key parts
     * @returns {*} Value at nested location, or null if not found
     */
    _getNestedValue(data, keyParts) {
        let current = data;
        
        for (const part of keyParts) {
            if (current && typeof current === 'object' && part in current) {
                current = current[part];
            } else {
                return null;
            }
        }
        
        return current;
    },

    _isKeyLike(value) {
        return /^[a-z0-9_]+(\.[a-z0-9_]+)+$/i.test(value);
    },

    _resolveKey(key, params = {}) {
        if (!this.initialized) {
            return {
                found: false,
                text: this.missingTranslationPlaceholder,
                localeUsed: this.currentLocale,
                fallbackUsed: false,
                key
            };
        }

        const keyParts = key.split('.');
        let trans = this._getNestedValue(this.translations[this.currentLocale], keyParts);
        let localeUsed = this.currentLocale;
        let fallbackUsed = false;

        if (typeof trans !== 'string' || trans.trim() === '') {
            trans = this._getNestedValue(this.translations.en, keyParts);
            localeUsed = 'en';
            fallbackUsed = true;
        }

        if (typeof trans !== 'string' || trans.trim() === '') {
            return {
                found: false,
                text: this.missingTranslationPlaceholder,
                localeUsed: this.currentLocale,
                fallbackUsed: false,
                key
            };
        }

        let text = trans;
        if (Object.keys(params).length > 0) {
            try {
                text = trans.replace(/\{(\w+)\}/g, (match, param) => {
                    if (param in params) {
                        return params[param];
                    }
                    console.warn(`[i18n] Missing parameter '${param}' for key '${key}'`);
                    return match;
                });
            } catch (error) {
                console.error(`[i18n] Error substituting parameters for key '${key}':`, error);
            }
        }

        return {
            found: true,
            text,
            localeUsed,
            fallbackUsed,
            key
        };
    },

    hasKey(key, locale = null) {
        if (!this.initialized) {
            return false;
        }
        const keyParts = key.split('.');
        const selectedLocale = locale || this.currentLocale;
        const trans = this._getNestedValue(this.translations[selectedLocale], keyParts);
        return typeof trans === 'string' && trans.trim() !== '';
    },
    
    /**
     * Translate key with optional parameters.
     * 
     * Fallback chain: current_locale → 'en' → '[key]'
     * 
     * @param {string} key - Translation key (dot-separated)
     * @param {object} params - Named parameters for string substitution
     * @returns {string} Translated string
     * 
     * @example
     * i18n.t('web.stat.total_kills')
     * // → "Total Kills"
     * 
     * @example
     * i18n.t('web.title.campaign_detail', {campaign_name: 'Stalingrad'})
     * // → "Stalingrad - Campaign Service Record"
     */
    t(key, params = {}) {
        // Ensure initialized
        if (!this.initialized) {
            console.warn('[i18n] Not initialized, using key as-is:', key);
            return this.missingTranslationPlaceholder;
        }

        const resolved = this._resolveKey(key, params);
        if (!resolved.found) {
            console.debug(`[i18n] Translation key not found: ${key}`);
        }
        return resolved.text;
    },

    tr(value, { params = {}, defaultText = null, forceKey = false, returnMeta = false } = {}) {
        if (value === null || value === undefined) {
            return returnMeta ? { text: '', meta: null } : '';
        }

        const rawValue = String(value);
        let keyUsed = null;
        let resolved = null;

        const shouldTreatAsKey = forceKey || (this._isKeyLike(rawValue) && (this.hasKey(rawValue) || this.hasKey(rawValue, 'en')));

        if (shouldTreatAsKey) {
            keyUsed = rawValue;
            resolved = this._resolveKey(rawValue, params);
        }

        if (!resolved || !resolved.found) {
            const text = defaultText !== null
                ? defaultText
                : (keyUsed ? this.missingTranslationPlaceholder : rawValue);
            const meta = {
                keyUsed,
                resolvedText: text,
                locale: this.currentLocale,
                fallbackUsed: false,
                missing: Boolean(keyUsed)
            };
            return returnMeta ? { text, meta } : text;
        }

        const meta = {
            keyUsed,
            resolvedText: resolved.text,
            locale: resolved.localeUsed,
            fallbackUsed: resolved.fallbackUsed,
            missing: false
        };

        return returnMeta ? { text: resolved.text, meta } : resolved.text;
    },
    
    /**
     * Get list of available locales.
     * 
     * @returns {Array<string>} Array of locale codes
     */
    getAvailableLocales() {
        return Object.keys(this.translations);
    },
    
    /**
     * Check if a locale is available.
     * 
     * @param {string} locale - Locale code to check
     * @returns {boolean} True if available
     */
    isLocaleAvailable(locale) {
        return locale in this.translations;
    }
};

// Auto-initialize with English on load (async)
(async () => {
    try {
        if (i18n.initialized || i18n.initInProgress) {
            return;
        }
        await i18n.init('en');
    } catch (error) {
        console.error('[i18n] Auto-initialization failed:', error);
    }
})();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = i18n;
}
