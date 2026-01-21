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
        'static/images/background_Britain.png',
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

    getFallbackBackground() {
        return this.backgroundImages[0] || '';
    },

    isLandingVisible() {
        if (!this.elements.page) {
            return false;
        }
        return this.elements.page.offsetParent !== null;
    },

    applyBackground({ defer = false } = {}) {
        if (defer) {
            window.requestAnimationFrame(() => this.applyBackground());
            return;
        }

        if (window.App && App.currentPage !== 'landing') {
            return;
        }

        if (!this.selectedBackground) {
            this.selectBackground();
        }

        const background = this.selectedBackground || this.getFallbackBackground();
        if (!background || !this.isLandingVisible()) {
            return;
        }

        document.body.style.backgroundImage = `url('${background}')`;
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
        const localizedCountry = this.getLocalizedCountryName(campaign.country);

        // Build stats HTML
        const statsHTML = `
            <span class="stat-item">
                <span class="stat-label">${i18n.t('web.label.missions')}:</span>
                <span class="stat-value">${campaign.missions_completed}</span>
            </span>
            <span class="stat-item">
                <span class="stat-label">${i18n.t('web.label.promotions')}:</span>
                <span class="stat-value">${campaign.promotions_count}</span>
            </span>
            <span class="stat-item">
                <span class="stat-label">${i18n.t('web.label.awards')}:</span>
                <span class="stat-value">${campaign.awards_count}</span>
            </span>
        `;

        const content = document.createElement('div');
        content.className = 'campaign-item__content';
        content.innerHTML = `
            <div class="campaign-name">
                ${this.escapeHTML(campaign.display_name)}
                <span class="campaign-country">${this.escapeHTML(localizedCountry || campaign.country)}</span>
            </div>
            <div class="campaign-stats">
                ${statsHTML}
            </div>
        `;

        const flagContainer = document.createElement('div');
        flagContainer.className = 'campaign-flag';
        const flagSrc = this.getFlagForCountry(campaign.country);
        if (flagSrc) {
            const flagImg = document.createElement('img');
            flagImg.src = flagSrc;
            flagImg.alt = localizedCountry ? `${localizedCountry} flag` : `${campaign.country} flag`;
            flagContainer.appendChild(flagImg);
        }

        item.appendChild(content);
        item.appendChild(flagContainer);

        // Click handler
        item.addEventListener('click', () => {
            this.navigateToDetail(campaign.name, campaign.country);
        });

        return item;
    },

    getCountryTranslationKey(country) {
        const normalized = (country || '').trim().toLowerCase();
        if (['germany', 'deutschland'].includes(normalized)) {
            return 'germany';
        }
        if (['britain', 'uk', 'united kingdom', 'england', 'great britain'].includes(normalized)) {
            return 'britain';
        }
        if (['usa', 'us', 'united states', 'united states of america'].includes(normalized)) {
            return 'usa';
        }
        if (['soviet union', 'ussr', 'russia'].includes(normalized)) {
            return 'soviet_union';
        }
        return '';
    },

    getLocalizedCountryName(country) {
        if (!country) {
            return '';
        }
        const key = this.getCountryTranslationKey(country);
        return key ? i18n.t(`country.${key}`) : country;
    },
    
    getFlagForCountry(country) {
        const normalized = (country || '').trim().toLowerCase();
        const flagMap = {
            germany: 'static/images/Germany_flag.png',
            britain: 'static/images/UK_flag.png',
            uk: 'static/images/UK_flag.png',
            'united kingdom': 'static/images/UK_flag.png',
            'soviet union': 'static/images/USSR_flag.png',
            ussr: 'static/images/USSR_flag.png',
            us: 'static/images/US_flag.png',
            usa: 'static/images/US_flag.png',
            'united states': 'static/images/US_flag.png'
        };
        return flagMap[normalized] || '';
    },

    /**
     * Navigate to campaign detail page
     */
    navigateToDetail(campaignName, campaignCountry) {
        console.log('Navigating to campaign:', campaignName);
        
        // Dispatch custom event for app-level navigation
        const event = new CustomEvent('navigate-to-detail', {
            detail: { campaignName, campaignCountry }
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
