/**
 * Main Application Controller
 * 
 * Handles:
 * - App initialization
 * - Page routing/navigation
 * - Back button functionality
 * - Keyboard shortcuts
 */

const App = {
    /**
     * Current page
     */
    currentPage: 'landing',

    /**
     * Global locale (from settings, used for landing page and as default)
     */
    globalLocale: 'en',

    /**
     * DOM elements
     */
    elements: {
        landingPage: null,
        detailPage: null,
        backBtn: null
    },
    
    /**
     * Translate all elements with data-i18n attributes
     */
    translatePage() {
        console.log('[App] Translating page elements...');
        
        // Translate text content
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            if (key) {
                element.textContent = i18n.t(key);
            }
        });
        
        // Translate placeholders
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            if (key) {
                element.placeholder = i18n.t(key);
            }
        });
        if (this.isDevEnvironment()) {
            this.logKeyLikeStrings();
        }

        console.log('[App] Page translation complete');
    },

    isDevEnvironment() {
        const hostname = window.location && window.location.hostname;
        return ['localhost', '127.0.0.1'].includes(hostname);
    },

    logKeyLikeStrings() {
        const keyLikePattern = /^[a-z0-9_]+(\.[a-z0-9_]+)+$/i;
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const text = (element.textContent || '').trim();
            if (text && keyLikePattern.test(text)) {
                console.warn('[i18n] Possible missing translation rendered:', text, element);
            }
        });
    },
    
    /**
     * Initialize application
     */
    async init() {
        console.log('Campaign Service Record initializing...');
        
        // Initialize i18n first
        try {
            const localeData = await API.getLocale();
            const locale = localeData.locale || 'en';
            console.log(`Initializing with locale: ${locale}`);
            await i18n.init(locale);
            // Store global locale for restoration when leaving detail pages
            this.globalLocale = locale;
        } catch (error) {
            console.warn('Failed to get locale from API, using default:', error);
            await i18n.init('en');
            this.globalLocale = 'en';
        }

        document.documentElement.lang = i18n.getLocale();
        
        // Translate page elements
        this.translatePage();
        
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
    async showLanding() {
        console.log('Navigating to landing page');

        // Restore global locale if detail page had a per-campaign override
        if (i18n.getLocale() !== this.globalLocale) {
            console.log(`[App] Restoring global locale: ${this.globalLocale}`);
            await i18n.setLocale(this.globalLocale);
            this.translatePage();
        }

        this.elements.landingPage.style.display = 'block';
        this.elements.detailPage.style.display = 'none';
        this.elements.backBtn.style.display = 'none';

        this.currentPage = 'landing';
        DetailPage.clearBackgroundState();

        // Update page title
        document.title = i18n.t('service_record.app_title');

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
        document.title = i18n.t('web.title.campaign_detail', { campaign_name: campaignName });
        
        // Load campaign details
        await DetailPage.load(campaignName);
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    await App.init();
});
