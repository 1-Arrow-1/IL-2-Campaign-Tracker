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
            const { campaignName } = event.detail;
            this.showDetail(campaignName);
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
        
        // Update page title
        document.title = 'IL-2 Campaign Service Record';
    },
    
    /**
     * Show detail page
     */
    async showDetail(campaignName) {
        console.log('Navigating to detail page:', campaignName);
        
        this.elements.landingPage.style.display = 'none';
        this.elements.detailPage.style.display = 'block';
        this.elements.backBtn.style.display = 'inline-block';
        
        this.currentPage = 'detail';
        
        // Update page title
        document.title = `${campaignName} - Campaign Service Record`;
        
        // Load campaign details
        await DetailPage.load(campaignName);
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
