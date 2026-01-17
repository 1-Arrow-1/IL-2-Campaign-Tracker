/**
 * Main Application Controller
 * 
 * Handles:
 * - App initialization
 * - Page routing/navigation
 * - Back button functionality
 * - Keyboard shortcuts
 */

const I18N = {
    messages: {},
    t(key, params = {}) {
        const template = this.messages[key] || key;
        return template.replace(/\{(\w+)\}/g, (match, name) => {
            if (Object.prototype.hasOwnProperty.call(params, name)) {
                return String(params[name]);
            }
            return match;
        });
    }
};
window.I18N = I18N;

async function fetchSettings() {
    try {
        const response = await fetch('/api/settings', { cache: 'no-store' });
        if (!response.ok) {
            return { locale: 'en', fallback_locale: 'en' };
        }
        const data = await response.json();
        return {
            locale: typeof data.locale === 'string' ? data.locale : 'en',
            fallback_locale: typeof data.fallback_locale === 'string' ? data.fallback_locale : 'en'
        };
    } catch (error) {
        console.warn('Unable to load settings:', error);
        return { locale: 'en', fallback_locale: 'en' };
    }
}

async function loadLocaleFile(path) {
    try {
        const response = await fetch(path, { cache: 'no-store' });
        if (!response.ok) {
            console.warn('Failed to load locale file:', response.status);
            return {};
        }
        const data = await response.json();
        if (data && typeof data === 'object') {
            return data;
        }
        return {};
    } catch (error) {
        console.warn('Unable to load locale file:', error);
        return {};
    }
}

async function loadI18n() {
    const settings = await fetchSettings();
    const preferred = (settings.locale || settings.fallback_locale || 'en').trim().toLowerCase();
    const baseMessages = await loadLocaleFile('/static/locales/en.json');
    let merged = { ...baseMessages };

    if (preferred && preferred !== 'en') {
        const overrides = await loadLocaleFile(`/static/locales/${preferred}.json`);
        merged = { ...baseMessages, ...overrides };
    }

    I18N.messages = merged;
}

function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = I18N.t(element.dataset.i18n);
    });

    document.querySelectorAll('[data-i18n-html]').forEach(element => {
        element.innerHTML = I18N.t(element.dataset.i18nHtml);
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        element.setAttribute('placeholder', I18N.t(element.dataset.i18nPlaceholder));
    });

    document.querySelectorAll('[data-i18n-alt]').forEach(element => {
        element.setAttribute('alt', I18N.t(element.dataset.i18nAlt));
    });

    document.querySelectorAll('[data-i18n-aria-label]').forEach(element => {
        element.setAttribute('aria-label', I18N.t(element.dataset.i18nAriaLabel));
    });
}

const App = {
    /**
     * Current page
     */
    currentPage: 'landing',
    
    /**
     * DOM elements
     */
    elements: {
        landingPage: null,
        detailPage: null,
        backBtn: null
    },
    
    /**
     * Initialize application
     */
    init() {
        console.log('Campaign Service Record initializing...');
        
        this.cacheElements();
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        
        // Initialize pages
        LandingPage.init();
        DetailPage.init();
        
        // Show landing page
        this.showLanding();
        
        console.log('Campaign Service Record ready');
    },
    
    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements.landingPage = document.getElementById('landing-page');
        this.elements.detailPage = document.getElementById('detail-page');
        this.elements.backBtn = document.getElementById('back-btn');
    },
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Back button
        this.elements.backBtn.addEventListener('click', () => {
            this.showLanding();
        });
        
        // Custom navigation event from landing page
        document.addEventListener('navigate-to-detail', (event) => {
            const { campaignName, campaignCountry } = event.detail;
            this.showDetail(campaignName, campaignCountry);
        });
    },
    
    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            // ESC: Back to landing
            if (event.key === 'Escape' && this.currentPage === 'detail') {
                this.showLanding();
            }
        });
    },
    
    /**
     * Show landing page
     */
    showLanding() {
        console.log('Navigating to landing page');
        
        this.elements.landingPage.style.display = 'block';
        this.elements.detailPage.style.display = 'none';
        this.elements.backBtn.style.display = 'none';
        
        this.currentPage = 'landing';
        DetailPage.clearBackgroundState();
        
        // Update page title
        document.title = I18N.t('service_record.title');

        const fallbackBackground = LandingPage.getFallbackBackground();
        if (fallbackBackground) {
            document.body.style.backgroundImage = `url('${fallbackBackground}')`;
        }

        LandingPage.applyBackground({ defer: true });
    },
    
    /**
     * Show detail page
     */
    async showDetail(campaignName, campaignCountry) {
        console.log('Navigating to detail page:', campaignName);
        
        this.elements.landingPage.style.display = 'none';
        this.elements.detailPage.style.display = 'block';
        this.elements.backBtn.style.display = 'inline-block';
        
        this.currentPage = 'detail';

        DetailPage.clearBackgroundState();
        DetailPage.applyBackgroundForCountry(campaignCountry, { force: true });
        
        // Update page title
        document.title = I18N.t('service_record.detail_title', { campaign: campaignName });
        
        // Load campaign details
        await DetailPage.load(campaignName);
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const init = async () => {
        await loadI18n();
        applyI18n();
        App.init();
    };
    init();
});
