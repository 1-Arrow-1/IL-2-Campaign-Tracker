/**
 * Landing Page Controller
 * 
 * Handles:
 * - Loading campaign list
 * - Rendering campaign items
 * - Navigation to detail page
 * - Background selection per session
 */

const LandingPage = {
    /**
     * DOM elements
     */
    elements: {
        page: null,
        loadingState: null,
        emptyState: null,
        errorState: null,
        errorText: null,
        campaignsList: null
    },
    
    /**
     * Current campaigns data
     */
    campaigns: [],

    backgroundImages: [
        'static/images/backgroound_Britain.png',
        'static/images/background_Germany.png',
        'static/images/background_USSR.png',
        'static/images/background_US.png'
    ],
    selectedBackground: null,
    
    /**
     * Initialize landing page
     */
    init() {
        this.cacheElements();
        this.selectBackground();
        this.applyBackground();
        this.loadCampaigns();
    },
    
    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements.page = document.getElementById('landing-page');
        this.elements.loadingState = document.getElementById('campaigns-loading');
        this.elements.emptyState = document.getElementById('campaigns-empty');
        this.elements.errorState = document.getElementById('campaigns-error');
        this.elements.errorText = document.getElementById('error-text');
        this.elements.campaignsList = document.getElementById('campaigns-list');
    },

    selectBackground() {
        if (this.backgroundImages.length === 0) {
            return;
        }
        const index = Math.floor(Math.random() * this.backgroundImages.length);
        this.selectedBackground = this.backgroundImages[index];
    },

    applyBackground() {
        if (!this.selectedBackground) {
            return;
        }
        document.body.style.backgroundImage = `url('${this.selectedBackground}')`;
    },
    
    /**
     * Load campaigns from API
     */
    async loadCampaigns() {
        this.showLoading();
        
        try {
            const campaigns = await API.getCampaigns();
            
            if (!campaigns || campaigns.length === 0) {
                this.showEmpty();
                return;
            }
            
            this.campaigns = campaigns;
            this.renderCampaigns();
            
        } catch (error) {
            console.error('Failed to load campaigns:', error);
            this.showError(error.message);
        }
    },
    
    /**
     * Render campaign list
     */
    renderCampaigns() {
        this.elements.campaignsList.innerHTML = '';
        
        this.campaigns.forEach(campaign => {
            const item = this.createCampaignItem(campaign);
            this.elements.campaignsList.appendChild(item);
        });
        
        this.showList();
    },
    
    /**
     * Create campaign list item element
     */
    createCampaignItem(campaign) {
        const item = document.createElement('div');
        item.className = 'campaign-item';
        item.dataset.campaignName = campaign.name;
        
        // Build stats HTML
        const statsHTML = `
            <span class="stat-item">
                <span class="stat-label">Missions:</span>
                <span class="stat-value">${campaign.missions_completed}</span>
            </span>
            <span class="stat-item">
                <span class="stat-label">Promotions:</span>
                <span class="stat-value">${campaign.promotions_count}</span>
            </span>
            <span class="stat-item">
                <span class="stat-label">Awards:</span>
                <span class="stat-value">${campaign.awards_count}</span>
            </span>
        `;    
        
        item.innerHTML = `
            <div class="campaign-name">
                ${this.escapeHTML(campaign.display_name)}
                <span class="campaign-country">${this.escapeHTML(campaign.country)}</span>
            </div>
            <div class="campaign-stats">
                ${statsHTML}
            </div>
        `;
        
        // Click handler
        item.addEventListener('click', () => {
            this.navigateToDetail(campaign.name);
        });
        
        return item;
    },
    
    /**
     * Navigate to campaign detail page
     */
    navigateToDetail(campaignName) {
        console.log('Navigating to campaign:', campaignName);
        
        // Dispatch custom event for app-level navigation
        const event = new CustomEvent('navigate-to-detail', {
            detail: { campaignName }
        });
        document.dispatchEvent(event);
    },
    
    /**
     * Show/hide states
     */
    showLoading() {
        this.elements.loadingState.style.display = 'block';
        this.elements.emptyState.style.display = 'none';
        this.elements.errorState.style.display = 'none';
        this.elements.campaignsList.style.display = 'none';
    },
    
    showEmpty() {
        this.elements.loadingState.style.display = 'none';
        this.elements.emptyState.style.display = 'block';
        this.elements.errorState.style.display = 'none';
        this.elements.campaignsList.style.display = 'none';
    },
    
    showError(message) {
        this.elements.errorText.textContent = message;
        this.elements.loadingState.style.display = 'none';
        this.elements.emptyState.style.display = 'none';
        this.elements.errorState.style.display = 'block';
        this.elements.campaignsList.style.display = 'none';
    },
    
    showList() {
        this.elements.loadingState.style.display = 'none';
        this.elements.emptyState.style.display = 'none';
        this.elements.errorState.style.display = 'none';
        this.elements.campaignsList.style.display = 'flex';
    },
    
    /**
     * Utility: Escape HTML to prevent XSS
     */
    escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};
