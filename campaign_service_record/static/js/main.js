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

async function loadI18n() {
    try {
        const response = await fetch('locales/en.json', { cache: 'no-store' });
        if (!response.ok) {
            console.warn('Failed to load locale file:', response.status);
            return;
        }
        const data = await response.json();
        if (data && typeof data === 'object') {
            I18N.messages = data;
        }
    } catch (error) {
        console.warn('Unable to load locale file:', error);
    }
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
    loadI18n().finally(() => {
        App.init();
    });
});
