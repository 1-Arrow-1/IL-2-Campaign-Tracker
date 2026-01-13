/**
 * Landing Page Controller
 * 
 * Handles:
 * - Loading campaign list
 * - Rendering campaign items
 * - Navigation to detail page
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
        campaignsList: null,
        pilotPhoto: null,
        pilotPhotoBtn: null,
        cropperModal: null,
        cropperImg: null,
        cropperCancel: null,
        cropperSave: null
    },
    
    /**
     * Current campaigns data
     */
    campaigns: [],

    cropper: null,
    pilotPhotoDesc: 'campaign_pilot',
    supportedImageTypes: [
        'image/png',
        'image/jpeg',
        'image/jpg',
        'image/gif',
        'image/bmp',
        'image/webp'
    ],
    
    /**
     * Initialize landing page
     */
    init() {
        this.cacheElements();
        this.setupPhotoHandlers();
        this.loadPilotPhoto();
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
        this.elements.pilotPhoto = document.getElementById('pilot-photo');
        this.elements.pilotPhotoBtn = document.getElementById('pilot-photo-btn');
        this.elements.cropperModal = document.getElementById('cropper-modal');
        this.elements.cropperImg = document.getElementById('cropper-img');
        this.elements.cropperCancel = document.getElementById('cropper-cancel');
        this.elements.cropperSave = document.getElementById('cropper-save');
    },

    setupPhotoHandlers() {
        if (this.elements.pilotPhotoBtn) {
            this.elements.pilotPhotoBtn.addEventListener('click', () => this.handlePhotoSelection());
        }

        if (this.elements.cropperCancel) {
            this.elements.cropperCancel.addEventListener('click', () => this.closeCropperModal());
        }

        if (this.elements.cropperSave) {
            this.elements.cropperSave.addEventListener('click', () => this.saveCroppedPhoto());
        }
    },

    async loadPilotPhoto() {
        try {
            const response = await API.getPilotPhoto(this.pilotPhotoDesc);
            if (response && response.path) {
                this.setPilotPhoto(`${response.path}?t=${Date.now()}`);
            } else {
                this.setPilotPhoto('static/images/placeholder_pilot.png');
            }
        } catch (error) {
            console.warn('Failed to load pilot photo:', error);
            this.setPilotPhoto('static/images/placeholder_pilot.png');
        }
    },

    setPilotPhoto(src) {
        if (!this.elements.pilotPhoto) {
            return;
        }
        this.elements.pilotPhoto.onerror = () => {
            this.elements.pilotPhoto.src = 'static/images/placeholder_pilot.png';
        };
        this.elements.pilotPhoto.src = src;
    },

    handlePhotoSelection() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = this.supportedImageTypes.join(',');
        input.onchange = event => {
            const file = event.target.files[0];
            if (!file) {
                return;
            }
            if (!this.supportedImageTypes.includes(file.type)) {
                alert('Unsupported image format. Please select a PNG, JPG, GIF, BMP, or WebP file.');
                return;
            }

            const reader = new FileReader();
            reader.onload = evt => {
                this.openCropperModal(evt.target.result);
            };
            reader.readAsDataURL(file);
        };
        input.click();
    },

    openCropperModal(imageSrc) {
        if (!this.elements.cropperModal || !this.elements.cropperImg) {
            return;
        }
        this.elements.cropperImg.src = imageSrc;
        this.elements.cropperModal.style.display = 'flex';

        if (this.cropper) {
            this.cropper.destroy();
        }

        this.elements.cropperImg.onload = () => {
            this.cropper = new Cropper(this.elements.cropperImg, {
                aspectRatio: 180 / 220,
                viewMode: 1,
                autoCropArea: 1,
                background: false,
                movable: true,
                zoomable: true,
                rotatable: false,
                scalable: false,
                minCropBoxWidth: 90,
                minCropBoxHeight: 110
            });
        };
    },

    closeCropperModal() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
        if (this.elements.cropperModal) {
            this.elements.cropperModal.style.display = 'none';
        }
    },

    async saveCroppedPhoto() {
        if (!this.cropper) {
            return;
        }

        const canvas = this.cropper.getCroppedCanvas({ width: 180, height: 220 });
        const imageData = canvas.toDataURL('image/png');

        try {
            const response = await API.savePilotPhoto(this.pilotPhotoDesc, imageData);
            if (response && response.path) {
                this.setPilotPhoto(`${response.path}?t=${Date.now()}`);
            } else {
                console.error('Pilot photo save returned unexpected response:', response);
                alert('Unable to save pilot photo. Please try again.');
            }
        } catch (error) {
            console.error('Failed to save pilot photo:', error);
            alert('Unable to save pilot photo. Please try again.');
        } finally {
            this.closeCropperModal();
        }
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
