/**
 * Detail Page Controller
 * 
 * Handles:
 * - Loading campaign details
 * - Rendering events, debriefings, summary
 * - PDF download button
 */

const t = (key, params = {}) => (
    window.I18N ? window.I18N.t(key, params) : key
);

const PreviewModal = {
    elements: {
        overlay: null,
        title: null,
        image: null,
        description: null,
        close: null
    },
    isOpen: false,

    init() {
        if (this.elements.overlay) {
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'preview-modal';
        overlay.setAttribute('aria-hidden', 'true');

        const content = document.createElement('div');
        content.className = 'preview-modal__content';

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'preview-modal__close';
        close.setAttribute('aria-label', t('service_record.preview.close_aria'));
        close.textContent = '×';

        const title = document.createElement('div');
        title.className = 'preview-modal__title';

        const image = document.createElement('img');
        image.className = 'preview-modal__image';
        image.alt = '';

        const description = document.createElement('div');
        description.className = 'preview-modal__description';

        close.addEventListener('click', () => this.close());

        content.appendChild(close);
        content.appendChild(title);
        content.appendChild(image);
        content.appendChild(description);
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        document.addEventListener('keydown', (event) => {
            if (this.isOpen && event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
            }
        }, true);

        this.elements.overlay = overlay;
        this.elements.title = title;
        this.elements.image = image;
        this.elements.description = description;
        this.elements.close = close;
    },

    open({ title, imageUrl, imageAlt, width, height, description }) {
        if (!imageUrl) {
            return;
        }
        this.elements.title.textContent = title || '';
        this.elements.image.alt = imageAlt || title || t('service_record.preview.default_alt');
        this.elements.image.src = imageUrl;
        this.elements.image.style.width = width ? `${Math.round(width)}px` : '';
        this.elements.image.style.height = height ? `${Math.round(height)}px` : '';
        this.elements.description.textContent = description || '';
        this.elements.description.classList.toggle('is-hidden', !description);

        this.elements.overlay.classList.add('is-open');
        this.elements.overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('modal-open');
        this.isOpen = true;
    },

    close() {
        if (!this.isOpen) {
            return;
        }
        this.elements.overlay.classList.remove('is-open');
        this.elements.overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('modal-open');
        this.elements.image.src = '';
        this.elements.description.textContent = '';
        this.elements.description.classList.add('is-hidden');
        this.isOpen = false;
    }
};

const EVENT_DESCRIPTIONS = {
    germany: {
        ranks: {
            Unteroffizier: 'service_record.event_desc.germany.rank.unteroffizier',
            Feldwebel: 'service_record.event_desc.germany.rank.feldwebel',
            Oberfeldwebel: 'service_record.event_desc.germany.rank.oberfeldwebel',
            Leutnant: 'service_record.event_desc.germany.rank.leutnant',
            Oberleutnant: 'service_record.event_desc.germany.rank.oberleutnant',
            Hauptmann: 'service_record.event_desc.germany.rank.hauptmann',
            Major: 'service_record.event_desc.germany.rank.major',
            Oberstleutnant: 'service_record.event_desc.germany.rank.oberstleutnant',
            Oberst: 'service_record.event_desc.germany.rank.oberst',
            Generalmajor: 'service_record.event_desc.germany.rank.generalmajor',
            Generalleutnant: 'service_record.event_desc.germany.rank.generalleutnant'
        },
        awards: {
            "Pilot's Badge": 'service_record.event_desc.germany.award.pilots_badge',
            'Iron Cross 2nd Class': 'service_record.event_desc.germany.award.iron_cross_2nd_class',
            'Iron Cross 1st Class': 'service_record.event_desc.germany.award.iron_cross_1st_class',
            'Honor Goblet': 'service_record.event_desc.germany.award.honor_goblet',
            'German Cross in Gold': 'service_record.event_desc.germany.award.german_cross_in_gold',
            "Knight's Cross of the Iron Cross": 'service_record.event_desc.germany.award.knights_cross',
            '…with Oak Leaves': 'service_record.event_desc.germany.award.knights_cross_oak_leaves',
            '…with Oak Leaves and Swords': 'service_record.event_desc.germany.award.knights_cross_oak_leaves_swords',
            '…with Oak Leaves, Swords and Diamonds': 'service_record.event_desc.germany.award.knights_cross_oak_leaves_swords_diamonds',
            '…with Golden Oak Leaves, Swords and Diamonds': 'service_record.event_desc.germany.award.knights_cross_golden_oak_leaves',
            'Front Flying Clasp (Fighters) Bronze': 'service_record.event_desc.germany.award.front_flying_clasp_bronze',
            'Front Flying Clasp (Fighters) Silver': 'service_record.event_desc.germany.award.front_flying_clasp_silver',
            'Front Flying Clasp (Fighters) Gold': 'service_record.event_desc.germany.award.front_flying_clasp_gold',
            '…Gold with Pendant': 'service_record.event_desc.germany.award.front_flying_clasp_gold_pendant',
            'Wound Badge in Black': 'service_record.event_desc.germany.award.wound_badge_black',
            'Wound Badge in Silver': 'service_record.event_desc.germany.award.wound_badge_silver',
            'Wound Badge in Gold': 'service_record.event_desc.germany.award.wound_badge_gold'
        }
    },
    britain: {
        ranks: {
            Sergeant: 'service_record.event_desc.britain.rank.sergeant',
            'Flight Sergeant': 'service_record.event_desc.britain.rank.flight_sergeant',
            'Warrant Officer': 'service_record.event_desc.britain.rank.warrant_officer',
            'Pilot Officer': 'service_record.event_desc.britain.rank.pilot_officer',
            'Flying Officer': 'service_record.event_desc.britain.rank.flying_officer',
            'Flight Lieutenant': 'service_record.event_desc.britain.rank.flight_lieutenant',
            'Squadron Leader': 'service_record.event_desc.britain.rank.squadron_leader',
            'Wing Commander': 'service_record.event_desc.britain.rank.wing_commander',
            'Group Captain': 'service_record.event_desc.britain.rank.group_captain',
            'Air Commodore': 'service_record.event_desc.britain.rank.air_commodore',
            'Air Vice Marshal': 'service_record.event_desc.britain.rank.air_vice_marshal'
        },
        awards: {
            "RAF Pilot's Badge": 'service_record.event_desc.britain.award.raf_pilots_badge',
            'Mentioned in Despatches': 'service_record.event_desc.britain.award.mentioned_in_despatches',
            'Distinguished Flying Medal (DFM)': 'service_record.event_desc.britain.award.dfm',
            'Bar to the DFM': 'service_record.event_desc.britain.award.dfm_bar',
            'Second Bar to the DFM': 'service_record.event_desc.britain.award.dfm_second_bar',
            'Distinguished Flying Cross (DFC)': 'service_record.event_desc.britain.award.dfc',
            'Bar to the DFC': 'service_record.event_desc.britain.award.dfc_bar',
            'Second Bar to the DFC': 'service_record.event_desc.britain.award.dfc_second_bar',
            'Distinguished Service Order (DSO)': 'service_record.event_desc.britain.award.dso',
            'Bar to the DSO': 'service_record.event_desc.britain.award.dso_bar',
            'Second Bar to the DSO': 'service_record.event_desc.britain.award.dso_second_bar',
            'Victoria Cross (VC)': 'service_record.event_desc.britain.award.vc',
            'Bar to the VC': 'service_record.event_desc.britain.award.vc_bar',
            'Wound Stripe': 'service_record.event_desc.britain.award.wound_stripe',
            'Second Wound Stripe': 'service_record.event_desc.britain.award.wound_stripe_second',
            'Third Wound Stripe': 'service_record.event_desc.britain.award.wound_stripe_third'
        }
    },
    usa: {
        ranks: {
            'First Sergeant': 'service_record.event_desc.usa.rank.first_sergeant',
            'Flight Officer': 'service_record.event_desc.usa.rank.flight_officer',
            'Chief Warrant Officer': 'service_record.event_desc.usa.rank.chief_warrant_officer',
            '2nd Lieutenant': 'service_record.event_desc.usa.rank.second_lieutenant',
            '1st Lieutenant': 'service_record.event_desc.usa.rank.first_lieutenant',
            Captain: 'service_record.event_desc.usa.rank.captain',
            Major: 'service_record.event_desc.usa.rank.major',
            'Lt. Colonel': 'service_record.event_desc.usa.rank.lieutenant_colonel',
            Colonel: 'service_record.event_desc.usa.rank.colonel',
            'Brigadier General': 'service_record.event_desc.usa.rank.brigadier_general',
            'Major General': 'service_record.event_desc.usa.rank.major_general'
        },
        awards: {
            "Pilot's Badge": 'service_record.event_desc.usa.award.pilots_badge',
            'Air Medal': 'service_record.event_desc.usa.award.air_medal',
            'Air Medal + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.air_medal_one_olc',
            'Air Medal + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.air_medal_two_olc',
            'Air Medal + Three Oak Leaf Clusters': 'service_record.event_desc.usa.award.air_medal_three_olc',
            'Bronze Star Medal': 'service_record.event_desc.usa.award.bronze_star',
            'Bronze Star + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.bronze_star_one_olc',
            'Bronze Star + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.bronze_star_two_olc',
            'Distinguished Flying Cross': 'service_record.event_desc.usa.award.dfc',
            'DFC + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.dfc_one_olc',
            'DFC + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.dfc_two_olc',
            'DFC + Three Oak Leaf Clusters': 'service_record.event_desc.usa.award.dfc_three_olc',
            'DFC + Four Oak Leaf Clusters': 'service_record.event_desc.usa.award.dfc_four_olc',
            'DFC + One Silver Oak Leaf Cluster': 'service_record.event_desc.usa.award.dfc_one_silver_olc',
            'Legion of Merit': 'service_record.event_desc.usa.award.legion_of_merit',
            'Silver Star Medal': 'service_record.event_desc.usa.award.silver_star',
            'Silver Star + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.silver_star_one_olc',
            'Silver Star + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.silver_star_two_olc',
            'Distinguished Service Cross': 'service_record.event_desc.usa.award.dsc',
            'DSC + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.dsc_one_olc',
            'DSC + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.dsc_two_olc',
            'DSC + Three Oak Leaf Clusters': 'service_record.event_desc.usa.award.dsc_three_olc',
            'DSC + Four Oak Leaf Clusters': 'service_record.event_desc.usa.award.dsc_four_olc',
            'Medal of Honor': 'service_record.event_desc.usa.award.medal_of_honor',
            'Medal of Honor + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.medal_of_honor_one_olc',
            'Purple Heart': 'service_record.event_desc.usa.award.purple_heart',
            'Purple Heart + One Oak Leaf Cluster': 'service_record.event_desc.usa.award.purple_heart_one_olc',
            'Purple Heart + Two Oak Leaf Clusters': 'service_record.event_desc.usa.award.purple_heart_two_olc'
        }
    },
    soviet: {
        ranks: {
            Sergeant: 'service_record.event_desc.soviet.rank.sergeant',
            'Senior Sergeant': 'service_record.event_desc.soviet.rank.senior_sergeant',
            'Junior Lieutenant': 'service_record.event_desc.soviet.rank.junior_lieutenant',
            Lieutenant: 'service_record.event_desc.soviet.rank.lieutenant',
            'Senior Lieutenant': 'service_record.event_desc.soviet.rank.senior_lieutenant',
            Captain: 'service_record.event_desc.soviet.rank.captain',
            Major: 'service_record.event_desc.soviet.rank.major',
            'Sub-Colonel': 'service_record.event_desc.soviet.rank.sub_colonel',
            Colonel: 'service_record.event_desc.soviet.rank.colonel',
            'Major General': 'service_record.event_desc.soviet.rank.major_general',
            'Lieutenant General': 'service_record.event_desc.soviet.rank.lieutenant_general'
        },
        awards: {
            'Aviation Badge': 'service_record.event_desc.soviet.award.aviation_badge',
            'Medal "For Battle Merit"': 'service_record.event_desc.soviet.award.medal_battle_merit',
            'Medal for Courage': 'service_record.event_desc.soviet.award.medal_courage',
            'Order of the Red Star': 'service_record.event_desc.soviet.award.order_red_star',
            'Order of the Red Star (2nd awarding)': 'service_record.event_desc.soviet.award.order_red_star_2',
            'Order of the Red Star (3rd awarding)': 'service_record.event_desc.soviet.award.order_red_star_3',
            'Order of the Patriotic War 2nd Class': 'service_record.event_desc.soviet.award.order_patriotic_war_2',
            'Order of the Patriotic War 1st Class': 'service_record.event_desc.soviet.award.order_patriotic_war_1',
            'Order of Alexander Nevsky': 'service_record.event_desc.soviet.award.order_alexander_nevsky',
            'Order of Suvorov 3rd Class': 'service_record.event_desc.soviet.award.order_suvorov_3',
            'Order of the Red Banner': 'service_record.event_desc.soviet.award.order_red_banner',
            'Order of the Red Banner (2nd awarding)': 'service_record.event_desc.soviet.award.order_red_banner_2',
            'Order of the Red Banner (3rd awarding)': 'service_record.event_desc.soviet.award.order_red_banner_3',
            'Hero of the Soviet Union': 'service_record.event_desc.soviet.award.hero_soviet_union',
            'Hero of the Soviet Union (2nd awarding)': 'service_record.event_desc.soviet.award.hero_soviet_union_2',
            'Hero of the Soviet Union (3rd awarding)': 'service_record.event_desc.soviet.award.hero_soviet_union_3',
            'Order of Lenin': 'service_record.event_desc.soviet.award.order_lenin',
            'Order of Lenin (2nd awarding)': 'service_record.event_desc.soviet.award.order_lenin_2',
            'Order of Lenin (3rd awarding)': 'service_record.event_desc.soviet.award.order_lenin_3',
            '5 Combat Sorties Bonus (1500 rubles)': 'service_record.event_desc.soviet.award.bonus_sorties_5',
            '15 Combat Sorties Bonus (2000 rubles)': 'service_record.event_desc.soviet.award.bonus_sorties_15',
            '25 Combat Sorties Bonus (3000 rubles)': 'service_record.event_desc.soviet.award.bonus_sorties_25',
            '40 Combat Sorties Bonus (5000 rubles)': 'service_record.event_desc.soviet.award.bonus_sorties_40',
            'Red Wound Stripe': 'service_record.event_desc.soviet.award.wound_stripe_red',
            'Yellow Wound Stripe': 'service_record.event_desc.soviet.award.wound_stripe_yellow'
        }
    }
};

const normalizeEventName = (value) => (value || '')
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .trim();

const NORMALIZED_EVENT_DESCRIPTIONS = Object.fromEntries(
    Object.entries(EVENT_DESCRIPTIONS).map(([key, data]) => {
        const normalizeMap = (map) => Object.fromEntries(
            Object.entries(map).map(([name, description]) => [
                normalizeEventName(name),
                description
            ])
        );
        return [key, {
            ranks: normalizeMap(data.ranks),
            awards: normalizeMap(data.awards)
        }];
    })
);

const getCountryKey = (country) => {
    const normalized = (country || '').trim().toLowerCase();
    if (['germany', 'deutschland'].includes(normalized)) {
        return 'germany';
    }
    if (['britain', 'uk', 'united kingdom', 'england'].includes(normalized)) {
        return 'britain';
    }
    if (['usa', 'us', 'united states', 'united states of america'].includes(normalized)) {
        return 'usa';
    }
    if (['soviet union', 'ussr', 'russia'].includes(normalized)) {
        return 'soviet';
    }
    return '';
};

const getAwardDescription = (awards, name) => {
    if (!name) {
        return '';
    }
    const normalizedName = normalizeEventName(name);
    if (awards[normalizedName]) {
        return awards[normalizedName];
    }
    const awardingMatch = normalizedName.match(/^(.*)\s+\((2nd|3rd) awarding\)$/i);
    if (awardingMatch) {
        const base = awardingMatch[1];
        const ordinal = awardingMatch[2];
        const key = normalizeEventName(`${base} (${ordinal} awarding)`);
        if (awards[key]) {
            return awards[key];
        }
    }
    if (normalizedName.startsWith("Knight's Cross of the Iron Cross")) {
        if (normalizedName.includes('Golden Oak Leaves')) {
            return awards[normalizeEventName('…with Golden Oak Leaves, Swords and Diamonds')] || '';
        }
        if (normalizedName.includes('Diamonds')) {
            return awards[normalizeEventName('…with Oak Leaves, Swords and Diamonds')] || '';
        }
        if (normalizedName.includes('Swords')) {
            return awards[normalizeEventName('…with Oak Leaves and Swords')] || '';
        }
        if (normalizedName.includes('Oak Leaves')) {
            return awards[normalizeEventName('…with Oak Leaves')] || '';
        }
    }
    if (normalizedName.includes('Front Flying Clasp') && normalizedName.includes('Gold with Pendant')) {
        return awards[normalizeEventName('…Gold with Pendant')] || '';
    }
    return '';
};

const DetailPage = {
    /**
     * DOM elements
     */
    elements: {
        page: null,
        title: null,
        country: null,
        missions: null,
        plane: null,
        insigniaLeft: null,
        insigniaRight: null,
        eventsList: null,
        debriefingsContainer: null,
        summaryContent: null,
        pilotPhoto: null,
        pilotPhotoContainer: null,
        pilotPhotoBtn: null,
        personalName: null,
        personalFirstName: null,
        personalBirthday: null,
        personalBirthPlace: null,
        personalBirthCountry: null,
        personalDisplayName: null,
        personalDisplayFirstName: null,
        personalDisplayBirthday: null,
        personalDisplayBirthPlace: null,
        personalDisplayBirthCountry: null,
        personalStatus: null,
        cropperModal: null,
        cropperImg: null,
        cropperPlaceholder: null,
        cropperCancel: null,
        cropperSave: null,
        cropperPhotoSelect: null
    },

    eventImageScale: 0.35,
    promotionPreviewScale: 1.2,
    cropper: null,
    cropperFrame: null,
    supportedImageTypes: [
        'image/png',
        'image/jpeg',
        'image/jpg',
        'image/gif',
        'image/bmp',
        'image/webp'
    ],
    backgroundByCountry: {
        germany: 'static/images/background_Germany.png',
        britain: 'static/images/background_Britain.png',
        uk: 'static/images/background_Britain.png',
        'soviet union': 'static/images/background_USSR.png',
        ussr: 'static/images/background_USSR.png',
        us: 'static/images/background_US.png',
        usa: 'static/images/background_US.png',
        'united states': 'static/images/background_US.png'
    },
    currentBackground: null,
    
    /**
     * Current campaign data
     */
    currentCampaign: null,
    
    /**
     * Initialize detail page
     */
    init() {
        this.cacheElements();
        this.ensureDetailColumns();
        this.setupPhotoHandlers();
        PreviewModal.init();
    },

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements.page = document.getElementById('detail-page');
        this.elements.title = document.getElementById('campaign-title');
        this.elements.country = document.getElementById('campaign-country');
        this.elements.missions = document.getElementById('campaign-missions');
        this.elements.plane = document.getElementById('campaign-plane');
        this.elements.insigniaLeft = document.getElementById('campaign-insignia-left');
        this.elements.insigniaRight = document.getElementById('campaign-insignia-right');
        this.elements.eventsList = document.getElementById('events-list');
        this.elements.debriefingsContainer = document.getElementById('debriefings-container');
        this.elements.summaryContent = document.getElementById('summary-content');
        this.elements.pilotPhoto = document.getElementById('detail-pilot-photo');
        this.elements.pilotPhotoContainer = document.querySelector('.personal-data-photo .pilot-photo-container');
        this.elements.pilotPhotoBtn = document.getElementById('detail-pilot-photo-btn');
        this.elements.personalName = document.getElementById('personal-name');
        this.elements.personalFirstName = document.getElementById('personal-first-name');
        this.elements.personalBirthday = document.getElementById('personal-birthday');
        this.elements.personalBirthPlace = document.getElementById('personal-birth-place');
        this.elements.personalBirthCountry = document.getElementById('personal-birth-country');
        this.elements.personalDisplayName = document.getElementById('personal-display-name');
        this.elements.personalDisplayFirstName = document.getElementById('personal-display-first-name');
        this.elements.personalDisplayBirthday = document.getElementById('personal-display-birthday');
        this.elements.personalDisplayBirthPlace = document.getElementById('personal-display-birth-place');
        this.elements.personalDisplayBirthCountry = document.getElementById('personal-display-birth-country');
        this.elements.personalStatus = document.getElementById('personal-data-status');
        this.elements.cropperModal = document.getElementById('cropper-modal');
        this.elements.cropperImg = document.getElementById('cropper-img');
        this.elements.cropperPlaceholder = document.getElementById('cropper-placeholder');
        this.elements.cropperCancel = document.getElementById('cropper-cancel');
        this.elements.cropperSave = document.getElementById('cropper-save');
        this.elements.cropperPhotoSelect = document.getElementById('cropper-photo-select');
    },

    setupPhotoHandlers() {
        if (this.elements.pilotPhotoBtn) {
            this.elements.pilotPhotoBtn.addEventListener('click', () => this.openPhotoModal());
        }

        if (this.elements.cropperPhotoSelect) {
            this.elements.cropperPhotoSelect.addEventListener('click', () => this.handlePhotoSelection());
        }

        if (this.elements.cropperCancel) {
            this.elements.cropperCancel.addEventListener('click', () => this.closeCropperModal());
        }

        if (this.elements.cropperSave) {
            this.elements.cropperSave.addEventListener('click', () => this.applyPhotoAndPersonalData());
        }

        if (this.elements.cropperModal) {
            this.elements.cropperModal.addEventListener('click', event => {
                if (event.target === this.elements.cropperModal) {
                    this.closeCropperModal();
                }
            });
        }
    },
    
    ensureDetailColumns() {
        const page = this.elements.page;
        if (!page) {
            return;
        }

        const columnsContainer = page.querySelector('.detail-columns');
        if (!columnsContainer) {
            return;
        }

        const columnSelectors = ['.column-left', '.column-middle', '.column-right'];
        const columns = columnSelectors
            .map(selector => page.querySelector(selector))
            .filter(Boolean);

        columns.forEach(column => {
            if (column.parentElement !== columnsContainer) {
                columnsContainer.appendChild(column);
            }
        });

        const leftColumn = columns.find(column => column.classList.contains('column-left'));
        if (!leftColumn) {
            return;
        }

        const eventsSection = page.querySelector('.events-section');
        if (!eventsSection) {
            return;
        }

        if (eventsSection.parentElement !== leftColumn) {
            const personalSection = leftColumn.querySelector('.personal-data-section');
            if (personalSection && personalSection.nextSibling) {
                leftColumn.insertBefore(eventsSection, personalSection.nextSibling);
            } else if (personalSection) {
                leftColumn.appendChild(eventsSection);
            } else {
                leftColumn.appendChild(eventsSection);
            }
        }
    },


    /**
     * Load and display campaign details
     */
    async load(campaignName) {
        console.log('Loading campaign details:', campaignName);
        
        try {
            // Show loading state
            this.elements.title.textContent = t('service_record.detail.loading_title');
            this.elements.eventsList.innerHTML = `<p>${this.escapeHTML(t('service_record.detail.loading_events'))}</p>`;
            this.elements.debriefingsContainer.innerHTML = `<p>${this.escapeHTML(t('service_record.detail.loading_debriefings'))}</p>`;
            this.elements.summaryContent.innerHTML = `<p>${this.escapeHTML(t('service_record.detail.loading_summary'))}</p>`;
            
            // Fetch campaign data
            const campaign = await API.getCampaignDetail(campaignName);
            
            if (!campaign) {
                throw new Error(t('service_record.detail.error_not_found'));
            }
            
            this.currentCampaign = campaign;

            this.applyBackgroundForCountry(campaign.country, { force: true });
            
            // Render components
            this.renderHeader(campaign);
            this.renderEvents(campaign.events);
            this.renderDebriefings(campaign.debriefings_html);
            this.renderSummary(campaign.summary);
            await this.loadPersonalData(campaign.name);
            await this.loadPilotPhoto(campaign.name);
            
            // Check for PDF
            this.checkPDF(campaign.name);
            
        } catch (error) {
            console.error('Failed to load campaign details:', error);
            this.showError(error.message);
        }
    },
    
    /**
     * Render campaign header
     */
    renderHeader(campaign) {
        this.elements.title.textContent = campaign.display_name;
        this.elements.country.textContent = campaign.country.toUpperCase();
        this.elements.missions.textContent = `${campaign.missions_completed} completed`;
        this.updatePlaneImage(campaign.country);
        this.updateInsigniaImages(campaign.country);
    },

    clearBackgroundState() {
        this.currentBackground = null;
    },

    applyBackgroundForCountry(country, { force = false } = {}) {
        if (!this.elements.page || this.elements.page.offsetParent === null) {
            return;
        }
        const normalized = (country || '').trim().toLowerCase();
        const background = this.backgroundByCountry[normalized];
        if (background && (force || background !== this.currentBackground)) {
            document.body.style.backgroundImage = `url('${background}')`;
            this.currentBackground = background;
        }
    },

    getPilotPhotoDesc(campaignName) {
        return `campaign:${campaignName}`;
    },

    async loadPilotPhoto(campaignName) {
        if (!campaignName) {
            return;
        }
        const desc = this.getPilotPhotoDesc(campaignName);
        try {
            const response = await API.getPilotPhoto(desc);
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

    openPhotoModal() {
        if (!this.elements.cropperModal) {
            return;
        }
        this.resetCropperPreview();
        this.showPersonalDataStatus('');
        this.elements.cropperModal.style.display = 'flex';
    },

    resetCropperPreview() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
        if (this.elements.cropperImg) {
            this.elements.cropperImg.removeAttribute('src');
            this.elements.cropperImg.style.display = 'none';
        }
        if (this.elements.cropperPlaceholder) {
            this.elements.cropperPlaceholder.style.display = 'block';
        }
        this.cropperFrame = null;
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
                alert(t('service_record.modal.unsupported_format'));
                return;
            }

            const reader = new FileReader();
            reader.onload = evt => {
                this.openCropperPreview(evt.target.result);
            };
            reader.readAsDataURL(file);
        };
        input.click();
    },

    openCropperPreview(imageSrc) {
        if (!this.elements.cropperImg) {
            return;
        }
        this.elements.cropperImg.style.display = 'block';
        if (this.elements.cropperPlaceholder) {
            this.elements.cropperPlaceholder.style.display = 'none';
        }
        this.elements.cropperImg.src = imageSrc;

        if (this.cropper) {
            this.cropper.destroy();
        }

        const frameDimensions = this.getPilotPhotoFrameDimensions();
        this.cropperFrame = frameDimensions;

        this.elements.cropperImg.onload = () => {
            const minCropBoxWidth = Math.round(frameDimensions.width * 0.6);
            const minCropBoxHeight = Math.round(frameDimensions.height * 0.6);
            this.cropper = new Cropper(this.elements.cropperImg, {
                aspectRatio: frameDimensions.aspectRatio,
                viewMode: 1,
                autoCropArea: 1,
                background: false,
                movable: true,
                zoomable: true,
                rotatable: false,
                scalable: false,
                minCropBoxWidth,
                minCropBoxHeight
            });
        };
    },

    closeCropperModal() {
        this.resetCropperPreview();
        if (this.elements.cropperModal) {
            this.elements.cropperModal.style.display = 'none';
        }
    },

    async saveCroppedPhoto() {
        if (!this.cropper || !this.currentCampaign) {
            return false;
        }

        const frame = this.cropperFrame || this.getPilotPhotoFrameDimensions();
        const canvas = this.cropper.getCroppedCanvas({
            width: frame.width,
            height: frame.height
        });

        if (!canvas) {
            throw new Error(t('service_record.modal.crop_error'));
        }

        const imageData = canvas.toDataURL('image/png');
        const desc = this.getPilotPhotoDesc(this.currentCampaign.name);
        const response = await API.savePilotPhoto(desc, imageData);
        if (response && response.path) {
            this.setPilotPhoto(`${response.path}?t=${Date.now()}`);
            return true;
        }
        throw new Error(t('service_record.modal.save_photo_error'));
    },

    async applyPhotoAndPersonalData() {
        if (!this.currentCampaign) {
            return;
        }

        const payload = this.getPersonalDataPayload();
        this.showPersonalDataStatus(t('service_record.modal.status_saving'));

        let photoError = null;
        let dataError = null;
        let savedData = null;

        if (this.cropper) {
            try {
                await this.saveCroppedPhoto();
            } catch (error) {
                photoError = error;
                console.error('Failed to save pilot photo:', error);
            }
        }

        try {
            savedData = await API.saveCampaignPersonalData(this.currentCampaign.name, payload);
        } catch (error) {
            dataError = error;
            console.error('Failed to save personal data:', error);
        }

        if (savedData) {
            this.setPersonalDataFields(savedData);
            this.setPersonalDataDisplay(savedData);
        }

        if (photoError || dataError) {
            if (photoError && dataError) {
                this.showPersonalDataStatus(t('service_record.modal.status_save_failed_both'));
            } else if (photoError) {
                this.showPersonalDataStatus(t('service_record.modal.status_save_failed_photo'));
            } else {
                this.showPersonalDataStatus(t('service_record.modal.status_save_failed_data'));
            }
            return;
        }

        this.showPersonalDataStatus(t('service_record.modal.status_saved'));
        this.closeCropperModal();
    },

    getPilotPhotoFrameDimensions() {
        const fallback = { width: 200, height: 200 };
        const container = this.elements.pilotPhotoContainer;
        const width = Math.round(container?.clientWidth || fallback.width);
        const height = Math.round(container?.clientHeight || fallback.height);
        const safeWidth = width > 0 ? width : fallback.width;
        const safeHeight = height > 0 ? height : fallback.height;
        return {
            width: safeWidth,
            height: safeHeight,
            aspectRatio: safeWidth / safeHeight
        };
    },

    async loadPersonalData(campaignName) {
        if (!campaignName) {
            return;
        }
        try {
            const data = await API.getCampaignPersonalData(campaignName);
            this.setPersonalDataFields(data || {});
            this.setPersonalDataDisplay(data || {});
            this.showPersonalDataStatus('');
        } catch (error) {
            console.error('Failed to load personal data:', error);
            this.showPersonalDataStatus(t('service_record.modal.status_load_failed'));
            this.setPersonalDataFields({});
            this.setPersonalDataDisplay({});
        }
    },

    setPersonalDataFields(data) {
        if (this.elements.personalName) {
            this.elements.personalName.value = data.name || '';
        }
        if (this.elements.personalFirstName) {
            this.elements.personalFirstName.value = data.first_name || '';
        }
        if (this.elements.personalBirthday) {
            this.elements.personalBirthday.value = data.birthday || '';
        }
        if (this.elements.personalBirthPlace) {
            this.elements.personalBirthPlace.value = data.birth_place || '';
        }
        if (this.elements.personalBirthCountry) {
            this.elements.personalBirthCountry.value = data.birth_country || '';
        }
    },

    formatPersonalDataValue(value) {
        const trimmed = typeof value === 'string' ? value.trim() : '';
        return trimmed ? trimmed : '—';
    },

    setPersonalDataDisplay(data) {
        if (this.elements.personalDisplayName) {
            this.elements.personalDisplayName.textContent = this.formatPersonalDataValue(data.name);
        }
        if (this.elements.personalDisplayFirstName) {
            this.elements.personalDisplayFirstName.textContent = this.formatPersonalDataValue(data.first_name);
        }
        if (this.elements.personalDisplayBirthday) {
            this.elements.personalDisplayBirthday.textContent = this.formatPersonalDataValue(data.birthday);
        }
        if (this.elements.personalDisplayBirthPlace) {
            this.elements.personalDisplayBirthPlace.textContent = this.formatPersonalDataValue(data.birth_place);
        }
        if (this.elements.personalDisplayBirthCountry) {
            this.elements.personalDisplayBirthCountry.textContent = this.formatPersonalDataValue(data.birth_country);
        }
    },

    getPersonalDataPayload() {
        return {
            name: this.elements.personalName?.value?.trim() || '',
            first_name: this.elements.personalFirstName?.value?.trim() || '',
            birthday: this.elements.personalBirthday?.value?.trim() || '',
            birth_place: this.elements.personalBirthPlace?.value?.trim() || '',
            birth_country: this.elements.personalBirthCountry?.value?.trim() || ''
        };
    },

    showPersonalDataStatus(message) {
        if (!this.elements.personalStatus) {
            return;
        }
        this.elements.personalStatus.textContent = message || '';
    },

    updatePlaneImage(country) {
        if (!this.elements.plane) {
            return;
        }

        const normalized = (country || '').trim().toLowerCase();
        const planeImages = {
            germany: 'static/images/BF109_1.png',
            us: 'static/images/P51_1.png',
            usa: 'static/images/P51_1.png',
            'united states': 'static/images/P51_1.png',
            britain: 'static/images/Spitfire_1.png',
            uk: 'static/images/Spitfire_1.png',
            ussr: 'static/images/yak3_1.png',
            'soviet union': 'static/images/yak3_1.png'
        };

        const imageSrc = planeImages[normalized];

        if (imageSrc) {
            this.elements.plane.src = imageSrc;
            this.elements.plane.alt = `${country} aircraft`;
            this.elements.plane.style.display = '';
        } else {
            this.elements.plane.removeAttribute('src');
            this.elements.plane.alt = '';
            this.elements.plane.style.display = 'none';
        }
    },

    updateInsigniaImages(country) {
        const insigniaElements = [this.elements.insigniaLeft, this.elements.insigniaRight];

        if (insigniaElements.some(element => !element)) {
            return;
        }

        const normalized = (country || '').trim().toLowerCase();
        const insigniaImages = {
            germany: 'static/images/German_airforce_1.png',
            britain: 'static/images/British_airforce_1.png',
            uk: 'static/images/British_airforce_1.png',
            ussr: 'static/images/USSR_Airforce_1.png',
            'soviet union': 'static/images/USSR_Airforce_1.png',
            us: 'static/images/US_airforce_1.png',
            usa: 'static/images/US_airforce_1.png',
            'united states': 'static/images/US_airforce_1.png'
        };

        const imageSrc = insigniaImages[normalized];

        insigniaElements.forEach(element => {
            if (imageSrc) {
                element.src = imageSrc;
                element.alt = t('service_record.detail.insignia_alt', { country });
                element.style.display = '';
            } else {
                element.removeAttribute('src');
                element.alt = '';
                element.style.display = 'none';
            }
        });
    },
    
    /**
     * Render events (promotions & awards)
     */
    renderEvents(events) {
        this.elements.eventsList.innerHTML = '';
        
        if (!events || events.length === 0) {
            this.elements.eventsList.innerHTML = `<p class="empty-message">${this.escapeHTML(t('service_record.events.empty'))}</p>`;
            return;
        }
        
        // Separate promotions and awards
        const promotions = events.filter(e => e.type === 'promotion');
        const awards = events.filter(e => e.type === 'award');
        
        // Render promotions
        if (promotions.length > 0) {
            const header = document.createElement('h4');
            header.textContent = t('service_record.events.promotions_heading');
            header.style.marginBottom = '0.75rem';
            header.classList.add('event-section-title', 'event-section-title--promotion');
            this.elements.eventsList.appendChild(header);
            
            promotions.forEach(promo => {
                const item = this.createEventItem(promo);
                this.elements.eventsList.appendChild(item);
            });
        }
        
        // Render awards
        if (awards.length > 0) {
            const header = document.createElement('h4');
            header.textContent = t('service_record.events.awards_heading');
            header.style.marginTop = '1.5rem';
            header.style.marginBottom = '0.75rem';
            header.classList.add('event-section-title', 'event-section-title--award');
            this.elements.eventsList.appendChild(header);
            
            awards.forEach(award => {
                const item = this.createEventItem(award);
                this.elements.eventsList.appendChild(item);
            });
        }
    },
    
    /**
     * Create event item element
     */
    createEventItem(event) {
        const item = document.createElement('div');
        item.className = `event-item ${event.type}`;

        const typeLabel = event.type === 'promotion'
            ? t('service_record.events.type_promotion')
            : t('service_record.events.type_award');
        const mainText = event.type === 'promotion' ? event.rank : event.name;
        const dateText = event.date || t('service_record.events.mission_fallback', {
            number: event.mission_number || '?'
        });
        const reasonText = event.reason || '';

        const header = document.createElement('div');
        header.className = 'event-header';
        header.textContent = typeLabel;
        item.appendChild(header);

        const content = document.createElement('div');
        content.className = 'event-content';

        let img = null;
        if (event.image_url) {
            img = document.createElement('img');
            img.className = 'event-image';
            img.alt = t('service_record.events.icon_alt', {
                name: mainText || t('service_record.events.default_name')
            });
            img.src = event.image_url;
            img.onload = () => this.scaleEventImage(img);
            img.onerror = () => {
                img.remove();
                item.dataset.previewDisabled = 'true';
                item.classList.remove('event-item--clickable');
            };
            content.appendChild(img);
        }

        const textBlock = document.createElement('div');
        textBlock.className = 'event-text';

        const name = document.createElement('div');
        name.className = 'event-name';
        name.textContent = mainText || '';
        textBlock.appendChild(name);

        const date = document.createElement('div');
        date.className = 'event-date';
        date.textContent = dateText;
        textBlock.appendChild(date);

        if (reasonText) {
            const reason = document.createElement('div');
            reason.className = 'event-reason';
            reason.textContent = reasonText;
            textBlock.appendChild(reason);
        }

        content.appendChild(textBlock);
        item.appendChild(content);

        this.bindPreviewModal(item, event, img, mainText);

        return item;
    },

    getEventDescription(event) {
        const countryKey = getCountryKey(this.currentCampaign?.country);
        if (!countryKey) {
            return '';
        }
        const descriptions = NORMALIZED_EVENT_DESCRIPTIONS[countryKey];
        if (!descriptions) {
            return '';
        }
        if (event.type === 'promotion') {
            const rankName = normalizeEventName(event.rank);
            const key = descriptions.ranks[rankName];
            return key ? t(key) : '';
        }
        if (event.type === 'award') {
            const key = getAwardDescription(descriptions.awards, event.name);
            return key ? t(key) : '';
        }
        return '';
    },

    bindPreviewModal(item, event, img, mainText) {
        const previewUrl = event.type === 'award'
            ? (event.modal_image_url || event.image_url)
            : event.image_url;

        if (!previewUrl) {
            return;
        }

        item.classList.add('event-item--clickable');

        item.addEventListener('click', () => {
            if (item.dataset.previewDisabled === 'true') {
                return;
            }
            const title = event.type === 'promotion' ? event.rank : event.name;
            const size = event.type === 'promotion' ? this.getPromotionPreviewSize(img) : null;
            const description = this.getEventDescription(event);
            PreviewModal.open({
                title: title || mainText || '',
                imageUrl: previewUrl,
                imageAlt: title || mainText || t('service_record.preview.default_alt'),
                width: size ? size.width : null,
                height: size ? size.height : null,
                description
            });
        });
    },
    
    /**
     * Render debriefings (inject HTML from Campaign Tracker)
     */
    renderDebriefings(html) {
        if (!html || html.trim() === '') {
            this.elements.debriefingsContainer.innerHTML = `<p class="empty-message">${this.escapeHTML(t('service_record.debriefings.empty'))}</p>`;
            return;
        }
        
        const cleanedHtml = html.replace(
            /^\s*<b>\s*Mission Debriefings\s*<\/b>\s*<br>\s*(?:<br>\s*)?/i,
            ''
        );

        // Direct HTML injection (safe - comes from Campaign Tracker)
        this.elements.debriefingsContainer.innerHTML = cleanedHtml;
    },
    
    /**
     * Render campaign summary
     */
    renderSummary(summary) {
        this.elements.summaryContent.innerHTML = '';
        
        if (!summary) {
            this.elements.summaryContent.innerHTML = `<p class="empty-message">${this.escapeHTML(t('service_record.summary.empty'))}</p>`;
            return;
        }
        
        const sections = [];

        if (summary.combat_results) {
            sections.push(this.createSummarySection(
                t('service_record.summary.combat_results'),
                this.renderCombatResults(summary.combat_results)
            ));
        }

        if (summary.missions_stats) {
            sections.push(this.createSummarySection(
                t('service_record.summary.missions_flown'),
                this.renderMissionsStats(summary.missions_stats)
            ));
        }

        if (summary.aircraft_usage && Object.keys(summary.aircraft_usage).length > 0) {
            sections.push(this.createSummarySection(
                t('service_record.summary.aircraft_flown'),
                this.renderAircraftUsage(summary.aircraft_usage)
            ));
        }

        if (summary.career_progression) {
            sections.push(this.createSummarySection(
                t('service_record.summary.career_progression'),
                this.renderCareerProgression(summary.career_progression)
            ));
        }

        if (summary.timeline && summary.timeline.first_mission_date) {
            sections.push(this.createSummarySection(
                t('service_record.summary.campaign_timeline'),
                this.renderTimeline(summary.timeline)
            ));
        }

        sections.forEach(section => this.elements.summaryContent.appendChild(section));
    },
    
    /**
     * Create summary section wrapper
     */
    createSummarySection(title, content) {
        const section = document.createElement('div');
        section.className = 'summary-block';
        
        const header = document.createElement('h4');
        header.className = 'summary-block-title';
        header.textContent = title;
        section.appendChild(header);
        
        section.appendChild(content);
        
        return section;
    },
    
    /**
     * Render combat results
     */
    renderCombatResults(results) {
        const container = document.createElement('div');
        container.className = 'combat-results';

        const summaryStats = document.createElement('div');
        summaryStats.className = 'combat-summary-stats';
        summaryStats.appendChild(this.createInlineStat(t('service_record.combat.overall_score'), results.total_score ?? 0));
        summaryStats.appendChild(this.createInlineStat(t('service_record.combat.total_kills'), results.total_kills ?? 0));
        container.appendChild(summaryStats);

        const categories = [
            { key: 'Aircraft', icon: 'icon_aircraft.png', label: t('service_record.combat.category.aircraft') },
            { key: 'Vehicles', icon: 'icon_vehicles.png', label: t('service_record.combat.category.vehicles') },
            { key: 'Railroad', icon: 'icon_railroad.png', label: t('service_record.combat.category.railroad') },
            { key: 'Armaments', icon: 'icon_armaments.png', label: t('service_record.combat.category.armaments') },
            { key: 'Buildings', icon: 'icon_buildings.png', label: t('service_record.combat.category.buildings') },
            { key: 'Marine', icon: 'icon_marine.png', label: t('service_record.combat.category.marine') }
        ];

        const byCategory = results.by_category || {};

        const iconRow = document.createElement('div');
        iconRow.className = 'combat-results-icons';

        categories.forEach(category => {
            const total = this.sumCategory(byCategory[category.key] || {});
            const cell = document.createElement('div');
            cell.className = 'combat-icon-cell';

            const img = document.createElement('img');
            img.src = this.getGameAssetUrl(`CampaignRanksAwards/Misc/${category.icon}`);
            img.alt = t('service_record.combat.icon_alt', { category: category.label });
            img.onerror = () => img.remove();
            cell.appendChild(img);

            const count = document.createElement('div');
            count.className = 'combat-icon-count';
            count.textContent = total;
            cell.appendChild(count);

            const label = document.createElement('div');
            label.className = 'combat-icon-label';
            label.textContent = category.label;
            cell.appendChild(label);

            iconRow.appendChild(cell);
        });

        container.appendChild(iconRow);

        const subcategoryColumns = document.createElement('div');
        subcategoryColumns.className = 'combat-subcategory-columns';

        const subcategoryMap = {
            'Aircraft': [
                { key: 'Light', label: t('service_record.combat.subcategory.aircraft.light') },
                { key: 'Medium', label: t('service_record.combat.subcategory.aircraft.medium') },
                { key: 'Heavy', label: t('service_record.combat.subcategory.aircraft.heavy') },
                { key: 'Parked', label: t('service_record.combat.subcategory.aircraft.parked') },
                { key: 'Balloons', label: t('service_record.combat.subcategory.aircraft.balloons') }
            ],
            'Vehicles': [
                { key: 'Transport', label: t('service_record.combat.subcategory.vehicles.transport') },
                { key: 'Armored (Light)', label: t('service_record.combat.subcategory.vehicles.armored_light') },
                { key: 'Armored (Medium)', label: t('service_record.combat.subcategory.vehicles.armored_medium') },
                { key: 'Armored (Heavy)', label: t('service_record.combat.subcategory.vehicles.armored_heavy') }
            ],
            'Railroad': [
                { key: 'Locomotives', label: t('service_record.combat.subcategory.railroad.locomotives') },
                { key: 'Railroad Cars', label: t('service_record.combat.subcategory.railroad.cars') },
                { key: 'Station Facilities', label: t('service_record.combat.subcategory.railroad.facilities') }
            ],
            'Armaments': [
                { key: 'Machine Guns', label: t('service_record.combat.subcategory.armaments.machine_guns') },
                { key: 'Cannons', label: t('service_record.combat.subcategory.armaments.cannons') },
                { key: 'AAA Guns', label: t('service_record.combat.subcategory.armaments.aaa_guns') },
                { key: 'Rocket Launchers', label: t('service_record.combat.subcategory.armaments.rocket_launchers') },
                { key: 'Searchlights', label: t('service_record.combat.subcategory.armaments.searchlights') },
                { key: 'Radars', label: t('service_record.combat.subcategory.armaments.radars') }
            ],
            'Buildings': [
                { key: 'Residential Buildings', label: t('service_record.combat.subcategory.buildings.residential') },
                { key: 'Facilities', label: t('service_record.combat.subcategory.buildings.facilities') },
                { key: 'Bridges', label: t('service_record.combat.subcategory.buildings.bridges') }
            ],
            'Marine': [
                { key: 'Light', label: t('service_record.combat.subcategory.marine.light') },
                { key: 'Cargo', label: t('service_record.combat.subcategory.marine.cargo') },
                { key: 'Submarines', label: t('service_record.combat.subcategory.marine.submarines') },
                { key: 'Destroyers', label: t('service_record.combat.subcategory.marine.destroyers') }
            ]
        };

        categories.forEach(category => {
            const column = document.createElement('div');
            column.className = 'combat-subcategory-column';

            (subcategoryMap[category.key] || []).forEach(subcat => {
                const row = document.createElement('div');
                row.className = 'combat-subcategory-row';

                const label = document.createElement('span');
                label.className = 'combat-subcategory-label';
                const armoredPrefix = t('service_record.combat.subcategory.armored_prefix');
                const formattedLabel = subcat.label.startsWith(armoredPrefix)
                    ? subcat.label.replace(armoredPrefix, `${armoredPrefix}\n`)
                    : subcat.label;
                label.textContent = formattedLabel;
                row.appendChild(label);

                const value = document.createElement('span');
                value.className = 'combat-subcategory-value';
                value.textContent = (byCategory[category.key] || {})[subcat.key] || 0;
                row.appendChild(value);

                column.appendChild(row);
            });

            subcategoryColumns.appendChild(column);
        });

        container.appendChild(subcategoryColumns);

        return container;
    },
    
    /**
     * Render missions stats
     */
    renderMissionsStats(stats) {
        const container = document.createElement('div');
        const totalMissions = stats.total_missions ?? stats.completed_missions ?? 0;
        const totalFlightTime = stats.total_flight_time ?? '0m';
        const averageDuration = stats.average_duration ?? '0m';

        container.appendChild(this.createStat(t('service_record.summary.missions_completed'), totalMissions));
        container.appendChild(this.createStat(t('service_record.summary.flight_time'), totalFlightTime));
        container.appendChild(this.createStat(t('service_record.summary.average_flight_time'), averageDuration));

        const landingStats = Array.isArray(stats.landings) ? stats.landings : [];
        const filteredLandings = landingStats.filter(
            landing => landing && landing.label !== undefined && Number(landing.value || 0) > 0
        );

        if (filteredLandings.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-message';
            empty.textContent = t('service_record.summary.no_status_data');
            container.appendChild(empty);
            return container;
        }

        filteredLandings.forEach(landing => {
            container.appendChild(this.createStat(landing.label, landing.value ?? 0));
        });

        return container;
    },
    
    /**
     * Render aircraft usage
     */
    renderAircraftUsage(usage) {
        const container = document.createElement('div');
        
        for (const [aircraft, data] of Object.entries(usage)) {
            const value = t('service_record.summary.aircraft_usage', {
                missions: data.missions,
                kills: data.kills
            });
            container.appendChild(this.createStat(aircraft, value));
        }
        
        return container;
    },
    
    /**
     * Render career progression
     */
    renderCareerProgression(progression) {
        const container = document.createElement('div');
        
        container.appendChild(this.createStat(t('service_record.summary.starting_rank'), progression.starting_rank));
        container.appendChild(this.createStat(t('service_record.summary.final_rank'), progression.final_rank));
        container.appendChild(this.createStat(t('service_record.summary.promotions'), progression.promotions_count));
        container.appendChild(this.createStat(t('service_record.summary.awards'), progression.awards_count));
        
        // Awards list
        if (progression.awards_list && progression.awards_list.length > 0) {
            const list = document.createElement('ul');
            list.className = 'awards-list';
            
            progression.awards_list.forEach(award => {
                const item = document.createElement('li');
                item.textContent = award;
                list.appendChild(item);
            });
            
            container.appendChild(list);
        }
        
        return container;
    },
    
    /**
     * Render timeline
     */
    renderTimeline(timeline) {
        const container = document.createElement('div');
        
        if (timeline.first_mission_date) {
            container.appendChild(this.createStat(t('service_record.summary.first_mission'), timeline.first_mission_date));
        }
        
        if (timeline.last_mission_date) {
            container.appendChild(this.createStat(t('service_record.summary.last_mission'), timeline.last_mission_date));
        }
        
        if (timeline.duration_days !== null && timeline.duration_days !== undefined) {
            container.appendChild(this.createStat(
                t('service_record.summary.duration'),
                t('service_record.summary.duration_days', { days: timeline.duration_days })
            ));
        }
        
        return container;
    },
    
    /**
     * Create stat row
     */
    createStat(label, value) {
        const stat = document.createElement('div');
        stat.className = 'summary-stat';
        
        stat.innerHTML = `
            <span class="stat-label">${this.escapeHTML(label)}:</span>
            <span class="stat-value">${this.escapeHTML(String(value))}</span>
        `;
        
        return stat;
    },

    createInlineStat(label, value) {
        const stat = document.createElement('div');
        stat.className = 'summary-inline-stat';
        stat.innerHTML = `
            <span class="stat-label">${this.escapeHTML(label)}:</span>
            <span class="stat-value">${this.escapeHTML(String(value))}</span>
        `;
        return stat;
    },

    sumCategory(categoryData) {
        if (!categoryData) {
            return 0;
        }
        return Object.values(categoryData).reduce((total, value) => total + Number(value || 0), 0);
    },

    getGameAssetUrl(relativePath) {
        const normalized = String(relativePath || '').replace(/^[/\\\\]+/, '');
        return `/api/game_assets/${normalized}`;
    },

    scaleEventImage(img) {
        if (!img || !img.naturalWidth || !img.naturalHeight) {
            return;
        }
        img.style.width = `${Math.round(img.naturalWidth * this.eventImageScale)}px`;
        img.style.height = `${Math.round(img.naturalHeight * this.eventImageScale)}px`;
    },

    getPromotionPreviewSize(img) {
        if (!img) {
            return null;
        }
        if (!img.naturalWidth || !img.naturalHeight) {
            return null;
        }

        return {
            width: img.naturalWidth * this.promotionPreviewScale,
            height: img.naturalHeight * this.promotionPreviewScale
        };
    },
    
    /**
     * Check PDF availability and show download button
     */
    async checkPDF(campaignName) {
        try {
            const pdfInfo = await API.checkPDF(campaignName);
            
            if (pdfInfo && pdfInfo.available) {
                this.addPDFDownloadButton(pdfInfo.path);
            }
        } catch (error) {
            // PDF not available - no action needed
            console.log('No PDF available for', campaignName);
        }
    },
    
    /**
     * Add PDF download button to summary
     */
    addPDFDownloadButton(pdfPath) {
        const link = document.createElement('a');
        link.href = `/${pdfPath}`;
        link.className = 'pdf-download';
        link.textContent = t('service_record.summary.pdf_download');
        link.target = '_blank';
        
        this.elements.summaryContent.appendChild(link);
    },
    
    /**
     * Show error state
     */
    showError(message) {
        this.elements.title.textContent = t('service_record.detail.error_title');
        this.elements.eventsList.innerHTML = `<p class="error-message">${this.escapeHTML(message)}</p>`;
        this.elements.debriefingsContainer.innerHTML = '';
        this.elements.summaryContent.innerHTML = '';
    },
    
    /**
     * Utility: Escape HTML
     */
    escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};
