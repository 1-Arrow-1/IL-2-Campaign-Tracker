/**
 * Detail Page Controller
 * 
 * Handles:
 * - Loading campaign details
 * - Rendering events, debriefings, summary
 * - PDF download button
 */

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
        close.setAttribute('aria-label', i18n.t('ui.button.close'));
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
        this.elements.image.alt = imageAlt || title || 'Event preview';
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

const normalizeEventName = (value) => (value || '')
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .trim();

const isKeyLike = (value) => /^[a-z0-9_]+(\.[a-z0-9_]+)+$/i.test(value || '');

const isDevEnvironment = () => {
    if (typeof window === 'undefined') {
        return false;
    }
    const hostname = window.location && window.location.hostname;
    return ['localhost', '127.0.0.1'].includes(hostname);
};

// ============================================================================
// i18n TRANSLATION HELPERS
// ============================================================================

/**
 * Convert award/rank name to i18n key
 * e.g. "Iron Cross 2nd Class" -> "iron_cross_2nd_class"
 */
const nameToI18nKey = (name) => {
    if (!name) return "";
    return name
        .toLowerCase()
        .replace(/['']/g, "'")
        .replace(/['"]/g, "")
        .replace(/&/g, "and")
        .replace(/\+/g, "and")
        .replace(/[,\.]/g, "")
        .replace(/\s*\(\s*/g, "_")
        .replace(/\s*\)\s*/g, "")
        .replace(/…/g, "")
        .replace(/[-\s]+/g, "_")
        .replace(/_+/g, "_")
        .replace(/^_|_$/g, "");
};

const getNarrativeKeyForRank = (countryKey, rankCode) => {
    if (!countryKey || !rankCode) {
        return '';
    }
    return `narratives.${countryKey}.ranks.${rankCode}`;
};

const getNarrativeKeyForAward = (countryKey, awardCode) => {
    if (!countryKey || !awardCode) {
        return '';
    }
    return `narratives.${countryKey}.awards.${awardCode}`;
};

const normalizeSovietRankNarrativeCode = (code) => {
    if (!code) {
        return code;
    }
    let normalized = code.replace(/_(early|late)$/i, '');
    const map = {
        serzhant: 'sergeant',
        starshiy_serzhant: 'senior_sergeant',
        mladshiy_leytenant: 'junior_lieutenant',
        leytenant: 'lieutenant',
        starshiy_leytenant: 'senior_lieutenant',
        kapitan: 'captain',
        mayor: 'major',
        podpolkovnik: 'sub_colonel',
        polkovnik: 'colonel',
        general_mayor: 'major_general',
        general_leytenant: 'lieutenant_general'
    };
    return map[normalized] || normalized;
};

const getRankNarrativeCode = (event) => {
    const rawCode = event?.rank_code || event?.rankCode || event?.rank;
    if (!rawCode) {
        return '';
    }
    let key = nameToI18nKey(rawCode);
    const countryKey = getCountryKey(event?.country || event?.nation);
    if (countryKey === 'soviet') {
        key = normalizeSovietRankNarrativeCode(key);
    }
    return key;
};

const getAwardNarrativeCodeFromName = (countryKey, awardName) => {
    if (!countryKey || !awardName) {
        return '';
    }

    const normalizedName = normalizeEventName(awardName);
    let key = nameToI18nKey(normalizedName);

    if (countryKey === 'germany' && normalizedName.includes("Knight's Cross of the Iron Cross")) {
        if (normalizedName.includes('Golden Oak Leaves')) {
            key = 'with_golden_oak_leaves_swords_and_diamonds';
        } else if (normalizedName.includes('Oak Leaves, Swords and Diamonds')) {
            key = 'with_oak_leaves_swords_and_diamonds';
        } else if (normalizedName.includes('Oak Leaves and Swords')) {
            key = 'with_oak_leaves_and_swords';
        } else if (normalizedName.includes('Oak Leaves')) {
            key = 'with_oak_leaves';
        }
    }

    if (countryKey === 'usa') {
        key = normalizeUSAwardNarrativeKey(key);
    } else if (countryKey === 'britain') {
        key = normalizeBritainAwardNarrativeKey(key);
    }

    return key;
};

const getAwardNarrativeCode = (event, countryKey) => {
    const rawCode = event?.award_code || event?.awardCode;
    if (rawCode) {
        let key = nameToI18nKey(rawCode);
        if (countryKey === 'usa') {
            key = normalizeUSAwardNarrativeKey(key);
        } else if (countryKey === 'britain') {
            key = normalizeBritainAwardNarrativeKey(key);
        }
        return key;
    }
    return getAwardNarrativeCodeFromName(countryKey, event?.name);
};

const normalizeBritainAwardNarrativeKey = (key) => {
    if (!key) {
        return key;
    }
    const mappings = {
        distinguished_flying_cross: 'distinguished_flying_cross_dfc',
        distinguished_flying_medal: 'distinguished_flying_medal_dfm',
        distinguished_service_order: 'distinguished_service_order_dso',
        victoria_cross: 'victoria_cross_vc',
        bar_to_the_victoria_cross: 'bar_to_the_vc',
        bar_to_the_distinguished_flying_cross: 'bar_to_the_dfc',
        bar_to_the_distinguished_flying_medal: 'bar_to_the_dfm',
        bar_to_the_distinguished_service_order: 'bar_to_the_dso',
        second_bar_to_the_distinguished_flying_cross: 'second_bar_to_the_dfc',
        second_bar_to_the_distinguished_flying_medal: 'second_bar_to_the_dfm',
        second_bar_to_the_distinguished_service_order: 'second_bar_to_the_dso'
    };
    return mappings[key] || key;
};

const normalizeUSAwardNarrativeKey = (key) => {
    if (!key) {
        return key;
    }
    const oakLeafMappings = [
        { prefix: 'air_medal_and', replacement: 'air_medal_plus' },
        { prefix: 'bronze_star_and', replacement: 'bronze_star_plus' },
        { prefix: 'bronze_star_medal_and', replacement: 'bronze_star_plus' },
        { prefix: 'dfc_and', replacement: 'dfc_plus' },
        { prefix: 'dsc_and', replacement: 'dsc_plus' },
        { prefix: 'distinguished_service_cross_and', replacement: 'dsc_plus' },
        { prefix: 'medal_of_honor_and', replacement: 'medal_of_honor_plus' },
        { prefix: 'purple_heart_and', replacement: 'purple_heart_plus' },
        { prefix: 'silver_star_and', replacement: 'silver_star_plus' },
        { prefix: 'silver_star_medal_and', replacement: 'silver_star_plus' }
    ];

    for (const mapping of oakLeafMappings) {
        if (key.startsWith(mapping.prefix)) {
            return key.replace(mapping.prefix, mapping.replacement);
        }
    }

    return key;
};

/**
 * Translate award name using i18n
 */
const translateAwardName = (name) => {
    if (!name) return "";
    // Check if i18n is ready
    if (!i18n || !i18n.translations || Object.keys(i18n.translations).length === 0) {
        return name;  // i18n not loaded yet, return original
    }

    let resolvedText = name;
    let keyUsed = null;
    let fallbackUsed = false;

    if (isKeyLike(name)) {
        const { text, meta } = i18n.tr(name, { returnMeta: true, forceKey: true });
        resolvedText = text;
        keyUsed = name;
        fallbackUsed = meta?.fallbackUsed || false;
        if (meta?.missing) {
            console.warn('[i18n] Missing award translation key:', name);
        }
    } else {
        const key = `progression.awards.${nameToI18nKey(name)}`;
        const { text, meta } = i18n.tr(key, { returnMeta: true, forceKey: true, defaultText: name });
        resolvedText = text;
        keyUsed = key;
        fallbackUsed = meta?.fallbackUsed || false;
        if (meta?.missing) {
            console.warn('[i18n] Missing award translation key:', key);
        }
    }

    if (isDevEnvironment()) {
        console.debug('[i18n] Award translation', {
            keyUsed,
            resolvedText,
            locale: i18n.getLocale(),
            fallbackUsed
        });
    }

    return resolvedText;
};

/**
 * Translate rank name using i18n
 */
const translateRankName = (name, country) => {
    if (!name) return "";
    // Check if i18n is ready
    if (!i18n || !i18n.translations || Object.keys(i18n.translations).length === 0) {
        return name;  // i18n not loaded yet, return original
    }
    const baseKey = nameToI18nKey(name);
    
    if (country) {
        const countryCode = getCountryCode(country);
        if (countryCode) {
            const countryKey = `progression.ranks.${countryCode}_${baseKey}`;
            // Check if the key exists in current locale (not just fallback)
            if (i18n.hasKey(countryKey, i18n.currentLocale)) {
                const { text } = i18n.tr(countryKey, { returnMeta: true, forceKey: true });
                return text;
            }
        }
    }
    
    // Try generic key
    const genericKey = `progression.ranks.${baseKey}`;
    const { text, meta } = i18n.tr(genericKey, { returnMeta: true, forceKey: true, defaultText: name });
    return meta?.missing ? name : text;
};

/**
 * Get country code for rank translation
 */
const getCountryCode = (country) => {
    const normalized = (country || "").toLowerCase().trim();
    if (normalized === "germany") return "ger";
    if (["britain", "uk", "great britain"].includes(normalized)) return "raf";
    if (["usa", "united states"].includes(normalized)) return "usaaf";
    if (["soviet union", "ussr", "russia"].includes(normalized)) return "vvs";
    return "";
};


const loggedNarrativeKeys = new Set();
const POPUP_NARRATIVE_PLACEHOLDER = '[missing narrative]';

const logMissingNarrative = (key, context) => {
    if (!key || loggedNarrativeKeys.has(key)) {
        return;
    }
    loggedNarrativeKeys.add(key);
    console.warn('[i18n] Missing narrative translation', {
        key,
        locale: i18n?.currentLocale || 'unknown',
        ...context
    });
};

const getPopupNarrative = ({ type, nation, code, locale, params = {} }) => {
    if (!type || !nation || !code) {
        logMissingNarrative('narratives.missing_context', {
            eventType: type,
            nation,
            code,
            locale: locale || i18n?.getLocale?.()
        });
        return POPUP_NARRATIVE_PLACEHOLDER;
    }

    const narrativeKey = type === 'promotion'
        ? getNarrativeKeyForRank(nation, code)
        : getNarrativeKeyForAward(nation, code);

    if (!narrativeKey) {
        logMissingNarrative('narratives.invalid_key', {
            eventType: type,
            nation,
            code,
            locale: locale || i18n?.getLocale?.()
        });
        return POPUP_NARRATIVE_PLACEHOLDER;
    }

    if (!i18n || !i18n.tr) {
        logMissingNarrative(narrativeKey, {
            eventType: type,
            nation,
            code,
            locale: locale || 'unknown'
        });
        return POPUP_NARRATIVE_PLACEHOLDER;
    }

    const { text, meta } = i18n.tr(narrativeKey, {
        params,
        forceKey: true,
        returnMeta: true,
        defaultText: ''
    });

    if (isDevEnvironment()) {
        const requestedLocale = locale || i18n.getLocale();
        const fallbackLocale = 'en';
        const narrativeCatalog = i18n.translations?.[requestedLocale]?.narratives;
        console.debug('[i18n] Narrative resolution', {
            key: narrativeKey,
            locale: requestedLocale,
            fallbackLocale,
            hasKeyInLocale: i18n.hasKey(narrativeKey, requestedLocale),
            hasKeyInEn: i18n.hasKey(narrativeKey, fallbackLocale),
            resolvedLocale: meta?.locale,
            fallbackUsed: meta?.fallbackUsed,
            missing: meta?.missing,
            returnedText: text,
            narrativesCatalogAvailable: Boolean(narrativeCatalog),
            narrativesTopLevelKeys: narrativeCatalog ? Object.keys(narrativeCatalog) : []
        });
    }

    if (!meta?.missing && text.trim()) {
        return text;
    }

    logMissingNarrative(narrativeKey, {
        eventType: type,
        nation,
        code,
        locale: locale || i18n.getLocale()
    });
    return POPUP_NARRATIVE_PLACEHOLDER;
};

const getCountryKey = (country) => {
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
        return 'soviet';
    }
    return '';
};

const getCountryTranslationKey = (country) => {
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
};

const getLocalizedCountryName = (country) => {
    if (!country) {
        return '';
    }
    const key = getCountryTranslationKey(country);
    return key ? i18n.t(`country.${key}`) : country;
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
        stamp: null,
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
        cropperPhotoSelect: null,
        additionalNotesDisplay: null,
        additionalNotesEditor: null,
        additionalNotesTextarea: null,
        additionalNotesEditBtn: null,
        additionalNotesSaveBtn: null,
        additionalNotesCancelBtn: null,
        additionalNotesEmpty: null
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
        this.setupAdditionalNotesHandlers();
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
        this.elements.stamp = document.getElementById('campaign-stamp');
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
        this.elements.additionalNotesDisplay = document.getElementById('additional-notes-display');
        this.elements.additionalNotesEditor = document.getElementById('additional-notes-editor');
        this.elements.additionalNotesTextarea = document.getElementById('additional-notes-textarea');
        this.elements.additionalNotesEditBtn = document.getElementById('additional-notes-edit-btn');
        this.elements.additionalNotesSaveBtn = document.getElementById('additional-notes-save-btn');
        this.elements.additionalNotesCancelBtn = document.getElementById('additional-notes-cancel-btn');
        this.elements.additionalNotesEmpty = document.querySelector('.additional-notes-empty');
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

    /**
     * Set up additional notes handlers
     */
    setupAdditionalNotesHandlers() {
        if (this.elements.additionalNotesEditBtn) {
            this.elements.additionalNotesEditBtn.addEventListener('click', () => this.openAdditionalNotesEditor());
        }
        if (this.elements.additionalNotesSaveBtn) {
            this.elements.additionalNotesSaveBtn.addEventListener('click', () => this.saveAdditionalNotes());
        }
        if (this.elements.additionalNotesCancelBtn) {
            this.elements.additionalNotesCancelBtn.addEventListener('click', () => this.cancelAdditionalNotesEdit());
        }
    },

    /**
     * Open additional notes editor
     */
    openAdditionalNotesEditor() {
        if (!this.elements.additionalNotesDisplay || !this.elements.additionalNotesEditor) {
            return;
        }
        // Get current notes text (excluding the empty placeholder)
        const currentText = this.currentAdditionalNotes || '';
        this.elements.additionalNotesTextarea.value = currentText;
        this.elements.additionalNotesDisplay.style.display = 'none';
        this.elements.additionalNotesEditBtn.style.display = 'none';
        this.elements.additionalNotesEditor.style.display = 'block';
        this.elements.additionalNotesTextarea.focus();
    },

    /**
     * Cancel additional notes edit
     */
    cancelAdditionalNotesEdit() {
        if (!this.elements.additionalNotesDisplay || !this.elements.additionalNotesEditor) {
            return;
        }
        this.elements.additionalNotesEditor.style.display = 'none';
        this.elements.additionalNotesDisplay.style.display = 'block';
        this.elements.additionalNotesEditBtn.style.display = 'inline-block';
    },

    /**
     * Save additional notes
     */
    async saveAdditionalNotes() {
        if (!this.currentCampaign) {
            console.error('No current campaign');
            return;
        }

        const newNotes = this.elements.additionalNotesTextarea.value.trim();

        try {
            // Get existing personal data first
            const existingData = await API.getCampaignPersonalData(this.currentCampaign.name);

            // Merge with new notes
            const updatedData = {
                ...existingData,
                additional_notes: newNotes
            };

            // Save back
            await API.saveCampaignPersonalData(this.currentCampaign.name, updatedData);

            // Update local state
            this.currentAdditionalNotes = newNotes;

            // Update display
            this.displayAdditionalNotes(newNotes);

            // Close editor
            this.cancelAdditionalNotesEdit();

        } catch (error) {
            console.error('Failed to save additional notes:', error);
        }
    },

    /**
     * Display additional notes in view mode
     */
    displayAdditionalNotes(notes) {
        if (!this.elements.additionalNotesDisplay) {
            return;
        }

        // Clear existing content
        this.elements.additionalNotesDisplay.innerHTML = '';

        if (notes && notes.trim()) {
            // Create text node to display notes (preserves formatting)
            const textSpan = document.createElement('span');
            textSpan.textContent = notes;
            this.elements.additionalNotesDisplay.appendChild(textSpan);
        } else {
            // Show empty placeholder
            const emptySpan = document.createElement('span');
            emptySpan.className = 'additional-notes-empty';
            emptySpan.setAttribute('data-i18n', 'web.message.no_entries');
            emptySpan.textContent = i18n.t('web.message.no_entries');
            this.elements.additionalNotesDisplay.appendChild(emptySpan);
        }
    },

    /**
     * Load additional notes for current campaign
     */
    async loadAdditionalNotes() {
        if (!this.currentCampaign) {
            return;
        }

        try {
            const personalData = await API.getCampaignPersonalData(this.currentCampaign.name);
            this.currentAdditionalNotes = personalData.additional_notes || '';
            this.displayAdditionalNotes(this.currentAdditionalNotes);
        } catch (error) {
            console.error('Failed to load additional notes:', error);
            this.currentAdditionalNotes = '';
            this.displayAdditionalNotes('');
        }
    },

    /**
     * Current additional notes text
     */
    currentAdditionalNotes: '',

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

        const personalSection = leftColumn.querySelector('.personal-data-section');
        const additionalNotesSection = page.querySelector('.additional-notes-section');
        const eventsSection = page.querySelector('.events-section');

        // Ensure correct order in left column:
        // 1. Personal Data Section
        // 2. Additional Notes Section
        // 3. Events Section (Promotions & Awards)

        if (additionalNotesSection && additionalNotesSection.parentElement !== leftColumn) {
            if (personalSection) {
                personalSection.after(additionalNotesSection);
            } else {
                leftColumn.prepend(additionalNotesSection);
            }
        }

        if (eventsSection && eventsSection.parentElement !== leftColumn) {
            if (additionalNotesSection) {
                additionalNotesSection.after(eventsSection);
            } else if (personalSection) {
                personalSection.after(eventsSection);
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
            this.elements.title.textContent = 'Loading...';
            this.elements.eventsList.innerHTML = '<p>Loading events...</p>';
            this.elements.debriefingsContainer.innerHTML = '<p>Loading debriefings...</p>';
            this.elements.summaryContent.innerHTML = '<p>Loading summary...</p>';
            
            // Fetch campaign data
            const campaign = await API.getCampaignDetail(campaignName);
            
            if (!campaign) {
                throw new Error('Campaign not found');
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
        const localizedCountry = getLocalizedCountryName(campaign.country);
        this.elements.country.textContent = localizedCountry || campaign.country;
        this.elements.missions.textContent = i18n.t('service_record.header.missions_completed', {
            count: campaign.missions_completed
        });
        this.updatePlaneImage(campaign.country);
        this.updateInsigniaImages(campaign.country);
        this.updateStampImage(campaign.country);
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
                alert('Unsupported image format. Please select a PNG, JPG, GIF, BMP, or WebP file.');
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
            throw new Error('Unable to crop the selected image. Please try again.');
        }

        const imageData = canvas.toDataURL('image/png');
        const desc = this.getPilotPhotoDesc(this.currentCampaign.name);
        const response = await API.savePilotPhoto(desc, imageData);
        if (response && response.path) {
            this.setPilotPhoto(`${response.path}?t=${Date.now()}`);
            return true;
        }
        throw new Error('Unable to save pilot photo. Please try again.');
    },

    async applyPhotoAndPersonalData() {
        if (!this.currentCampaign) {
            return;
        }

        const payload = this.getPersonalDataPayload();
        this.showPersonalDataStatus('Saving...');

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
                this.showPersonalDataStatus('Unable to save photo or personal data.');
            } else if (photoError) {
                this.showPersonalDataStatus('Unable to save photo.');
            } else {
                this.showPersonalDataStatus('Unable to save personal data.');
            }
            return;
        }

        this.showPersonalDataStatus('Saved.');
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
            // Load additional notes
            this.currentAdditionalNotes = (data && data.additional_notes) || '';
            this.displayAdditionalNotes(this.currentAdditionalNotes);
        } catch (error) {
            console.error('Failed to load personal data:', error);
            this.showPersonalDataStatus('Unable to load personal data.');
            this.setPersonalDataFields({});
            this.setPersonalDataDisplay({});
            // Reset additional notes on error
            this.currentAdditionalNotes = '';
            this.displayAdditionalNotes('');
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

    stampByCountry: {
        // US / UK use the default stamp
        us: 'static/images/stamp_extra_II.png',
        usa: 'static/images/stamp_extra_II.png',
        'united states': 'static/images/stamp_extra_II.png',
        britain: 'static/images/stamp_extra_II.png',
        uk: 'static/images/stamp_extra_II.png',
        'united kingdom': 'static/images/stamp_extra_II.png',
        england: 'static/images/stamp_extra_II.png',
        'great britain': 'static/images/stamp_extra_II.png',

        // Germany
        germany: 'static/images/stamp_extra_II_ger.png',
        deutschland: 'static/images/stamp_extra_II_ger.png',

        // USSR
        ussr: 'static/images/stamp_extra_II_rus.png',
        'soviet union': 'static/images/stamp_extra_II_rus.png',
        russia: 'static/images/stamp_extra_II_rus.png'
    },

    updateStampImage(country) {
        if (!this.elements.stamp) {
            return;
        }

        const normalized = (country || '').trim().toLowerCase();
        const stampSrc = this.stampByCountry[normalized] || 'static/images/stamp_extra_II.png';

        // Avoid unnecessary DOM updates
        if (this.elements.stamp.getAttribute('src') !== stampSrc) {
            this.elements.stamp.src = stampSrc;
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
                element.alt = `${country} air force insignia`;
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
            this.elements.eventsList.innerHTML = `<p class="empty-message">${this.escapeHTML(i18n.t('web.message.no_events'))}</p>`;
            return;
        }
        
        // Separate promotions and awards
        const promotions = events.filter(e => e.type === 'promotion');
        const awards = events.filter(e => e.type === 'award');
        
        // Render promotions
        if (promotions.length > 0) {
            const header = document.createElement('h4');
            header.textContent = i18n.t('web.label.promotions');
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
            header.textContent = i18n.t('web.label.awards');
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
            ? i18n.t('web.label.promotion')
            : i18n.t('web.label.award');
        const mainText = event.type === 'promotion' ? translateRankName(event.rank, event.country) : translateAwardName(event.name);
        const dateText = event.date || `Mission ${event.mission_number || '?'}`;
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
            img.alt = `${mainText || 'Event'} icon`;
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

        this.bindPreviewModal(item, event, mainText);

        return item;
    },

    getEventDescription(event) {
        const countryKey = getCountryKey(this.currentCampaign?.country);
        if (!event) {
            return '';
        }

        const dateText = event.date || i18n.t('ui.popup.mission_label', { mission: event.mission_number || '?' });
        const rankText = event.type === 'promotion' ? translateRankName(event.rank, event.country) : '';
        const awardText = event.type === 'award' ? translateAwardName(event.name) : '';
        const params = {
            date: dateText,
            rank: rankText,
            name: awardText
        };

        const narrativeCode = event.type === 'promotion'
            ? getRankNarrativeCode(event)
            : getAwardNarrativeCode(event, countryKey);

        return getPopupNarrative({
            type: event.type,
            nation: countryKey,
            code: narrativeCode,
            locale: i18n.getLocale(),
            params
        });
    },

    bindPreviewModal(item, event, mainText) {
        // Use large modal image URL for both awards and promotions (512x512 insignias)
        const previewUrl = event.modal_image_url || event.image_url;

        if (!previewUrl) {
            return;
        }

        item.classList.add('event-item--clickable');

        item.addEventListener('click', () => {
            if (item.dataset.previewDisabled === 'true') {
                return;
            }
            const title = event.type === 'promotion' ? translateRankName(event.rank, event.country) : translateAwardName(event.name);
            const description = this.getEventDescription(event);
            PreviewModal.open({
                title: title || mainText || '',
                imageUrl: previewUrl,
                imageAlt: title || mainText || 'Event preview',
                description
            });
        });
    },
    
    /**
     * Render debriefings (inject HTML from Campaign Tracker)
     */
    renderDebriefings(html) {
        if (!html || html.trim() === '') {
            this.elements.debriefingsContainer.innerHTML = `<p class="empty-message">${this.escapeHTML(i18n.t('web.message.no_debriefings'))}</p>`;
            return;
        }
        
        // Remove the "Mission Debriefings" header from the HTML since we already have an <h3> title
        // This handles various formats: <b>Mission Debriefings</b>, localized versions, etc.
        let cleanedHtml = html
            // Remove English header
            .replace(/^\s*<b>\s*Mission Debriefings\s*<\/b>\s*<br>\s*(?:<br>\s*)?/i, '')
            // Remove any remaining standalone Mission Debriefings headers (including localized)
            .replace(/<b>\s*Mission Debriefings\s*<\/b>\s*<br>\s*(?:<br>\s*)?/gi, '')
            // Remove span-wrapped headers (from step3_generate_events.py)
            .replace(/<span[^>]*style="display:none"[^>]*>.*?<\/span>\s*<span[^>]*class="section-header"[^>]*>\s*<b>[^<]*<\/b>\s*<\/span>\s*<br>\s*(?:<br>\s*)?/gi, '')
            // Clean up any leading <br> tags
            .replace(/^(\s*<br>\s*)+/i, '');

        // Direct HTML injection (safe - comes from Campaign Tracker)
        this.elements.debriefingsContainer.innerHTML = this.localizeDebriefingsHtml(cleanedHtml);
    },

    localizeDebriefingsHtml(html) {
        let output = html;
        const replacements = [
            // Note: Mission Debriefings header is already removed in renderDebriefings()
            { pattern: /\bMISSION\b/gi, replacement: i18n.t('flightlog.mission') },
            { pattern: /\bFLIGHT LOG\b/gi, replacement: i18n.t('flightlog.flight_log') },
            { pattern: /\bEvents\b/gi, replacement: i18n.t('flightlog.events') },
            { pattern: /\bAircraft\b:/gi, replacement: `${i18n.t('flightlog.aircraft')}:` },
            { pattern: /\bDuration\b:/gi, replacement: `${i18n.t('flightlog.duration')}:` },
            { pattern: /\bStatus\b:/gi, replacement: `${i18n.t('flightlog.status_label')}:` },
            { pattern: /\bAircraft Dmg\b:/gi, replacement: `${i18n.t('flightlog.aircraft_damage')}:` },
            { pattern: /\bPilot Dmg\b:/gi, replacement: `${i18n.t('flightlog.pilot_damage')}:` },
            { pattern: /\bTakeoff\b/gi, replacement: i18n.t('flightlog.event.takeoff') },
            { pattern: /\bPilot Touchdown\b/gi, replacement: i18n.t('flightlog.event.pilot_touchdown') },
            { pattern: /\bLanding Damage\b/gi, replacement: i18n.t('flightlog.event.landing_damage') },
            { pattern: /\bLanding\b/gi, replacement: i18n.t('flightlog.event.landing') },
            { pattern: /\bCrash\b/gi, replacement: i18n.t('flightlog.event.crash') },
            { pattern: /\bBailout\b/gi, replacement: i18n.t('flightlog.event.bailout') },
            { pattern: /\bdestroyed\b/gi, replacement: i18n.t('flightlog.event.destroyed') },
            { pattern: /\bDamage taken\b/gi, replacement: i18n.t('flightlog.event.damage_taken') },
            { pattern: /\bdamaged\b/gi, replacement: i18n.t('flightlog.event.damaged') },
            { pattern: /\bHit by\b/gi, replacement: i18n.t('flightlog.event.hit_by') },
            { pattern: /\(Alt:/gi, replacement: `(${i18n.t('flightlog.altitude')}:` },
            { pattern: /\bBefore First Mission\b/gi, replacement: i18n.t('flightlog.timeline.before_first_mission') },
            { pattern: /\bAwarded\b/gi, replacement: i18n.t('flightlog.timeline.awarded') },
            { pattern: /\bPromoted to\b/gi, replacement: i18n.t('flightlog.timeline.promoted_to') },
            { pattern: /\bStarted as\b/gi, replacement: i18n.t('flightlog.timeline.started_as') }
        ];

        // Complete status string map - match full status for single i18n lookup
        // Order matters: longer/more specific patterns first
        const fullStatusMap = {
            // Landed variants
            'Landed (Hard Landing, Wounded)': i18n.t('flightlog.status.landed_hard_landing_wounded'),
            'Landed (Hard Landing)': i18n.t('flightlog.status.landed_hard_landing'),
            'Landed (Wounded)': i18n.t('flightlog.status.landed_wounded'),
            'Landed': i18n.t('flightlog.status.landed'),
            // Bailout variants
            'Bailout (Survived, Wounded)': i18n.t('flightlog.status.bailout_survived_wounded'),
            'Bailout (Survived)': i18n.t('flightlog.status.bailout_survived'),
            'Bailout': i18n.t('flightlog.status.bailout'),
            // MIA variants
            'MIA (Likely Captured)': i18n.t('flightlog.status.mia_likely_captured'),
            'MIA (Captured)': i18n.t('flightlog.status.mia_captured'),
            'MIA (Unknown)': i18n.t('flightlog.status.mia_unknown'),
            'MIA': i18n.t('flightlog.status.mia'),
            // Other statuses
            'Crashed': i18n.t('flightlog.status.crashed'),
            'KIA': i18n.t('flightlog.status.kia'),
            'Captured': i18n.t('flightlog.status.captured'),
            'Wounded': i18n.t('flightlog.status.wounded'),
            'Hard Landing': i18n.t('flightlog.status.hard_landing')
        };

        replacements.forEach(({ pattern, replacement }) => {
            output = output.replace(pattern, replacement);
        });

        // Replace complete status strings (case-insensitive)
        Object.entries(fullStatusMap).forEach(([status, translated]) => {
            // Escape special regex chars in status, match whole phrase
            const escaped = status.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escaped, 'gi');
            output = output.replace(regex, translated);
        });

        output = this.localizeDebriefingDates(output);
        return output;
    },

    localizeDebriefingDates(text) {
        const monthKeys = {
            january: 'january',
            february: 'february',
            march: 'march',
            april: 'april',
            may: 'may',
            june: 'june',
            july: 'july',
            august: 'august',
            september: 'september',
            october: 'october',
            november: 'november',
            december: 'december'
        };

        const monthPattern = Object.keys(monthKeys).join('|');
        const regex = new RegExp(`\\b(${monthPattern})\\b`, 'gi');

        return text.replace(regex, (match) => {
            const key = monthKeys[match.toLowerCase()];
            return key ? i18n.t(`flightlog.months.${key}`) : match;
        });
    },
    
    /**
     * Render campaign summary
     */
    renderSummary(summary) {
        this.elements.summaryContent.innerHTML = '';
        
        if (!summary) {
            this.elements.summaryContent.innerHTML = `<p class="empty-message">${this.escapeHTML(i18n.t('web.message.no_summary'))}</p>`;
            return;
        }
        
        const sections = [];

        if (summary.combat_results) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.combat_results'),
                this.renderCombatResults(summary.combat_results)
            ));
        }

        if (summary.missions_stats) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.missions_flown'),
                this.renderMissionsStats(summary.missions_stats)
            ));
        }

        if (summary.aircraft_usage && Object.keys(summary.aircraft_usage).length > 0) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.aircraft_flown'),
                this.renderAircraftUsage(summary.aircraft_usage)
            ));
        }

        if (summary.career_progression) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.career_progression'),
                this.renderCareerProgression(summary.career_progression)
            ));
        }

        if (summary.timeline && summary.timeline.first_mission_date) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.campaign_timeline'),
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
        summaryStats.appendChild(this.createInlineStat(i18n.t('web.stat.overall_score'), results.total_score ?? 0));
        summaryStats.appendChild(this.createInlineStat(i18n.t('web.stat.total_kills'), results.total_kills ?? 0));
        container.appendChild(summaryStats);

        const categories = [
            { key: 'Aircraft', icon: 'icon_aircraft.png', i18nKey: 'web.combat.category.aircraft' },
            { key: 'Vehicles', icon: 'icon_vehicles.png', i18nKey: 'web.combat.category.vehicles' },
            { key: 'Railroad', icon: 'icon_railroad.png', i18nKey: 'web.combat.category.railroad' },
            { key: 'Armaments', icon: 'icon_armaments.png', i18nKey: 'web.combat.category.armaments' },
            { key: 'Buildings', icon: 'icon_buildings.png', i18nKey: 'web.combat.category.buildings' },
            { key: 'Marine', icon: 'icon_marine.png', i18nKey: 'web.combat.category.marine' }
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
            img.alt = `${category.key} icon`;
            img.onerror = () => img.remove();
            cell.appendChild(img);

            const count = document.createElement('div');
            count.className = 'combat-icon-count';
            count.textContent = total;
            cell.appendChild(count);

            const label = document.createElement('div');
            label.className = 'combat-icon-label';
            label.textContent = i18n.t(category.i18nKey);
            cell.appendChild(label);

            iconRow.appendChild(cell);
        });

        container.appendChild(iconRow);

        const subcategoryColumns = document.createElement('div');
        subcategoryColumns.className = 'combat-subcategory-columns';

        const subcategoryMap = {
            'Aircraft': [
                { label: 'Light', i18nKey: 'web.combat.subcategory.light' },
                { label: 'Medium', i18nKey: 'web.combat.subcategory.medium' },
                { label: 'Heavy', i18nKey: 'web.combat.subcategory.heavy' },
                { label: 'Parked', i18nKey: 'web.combat.subcategory.parked' },
                { label: 'Balloons', i18nKey: 'web.combat.subcategory.balloons' }
            ],
            'Vehicles': [
                { label: 'Transport', i18nKey: 'web.combat.subcategory.transport' },
                { label: 'Armored (Light)', i18nKey: 'web.combat.subcategory.armored_light' },
                { label: 'Armored (Medium)', i18nKey: 'web.combat.subcategory.armored_medium' },
                { label: 'Armored (Heavy)', i18nKey: 'web.combat.subcategory.armored_heavy' }
            ],
            'Railroad': [
                { label: 'Locomotives', i18nKey: 'web.combat.subcategory.locomotives' },
                { label: 'Railroad Cars', i18nKey: 'web.combat.subcategory.railroad_cars' },
                { label: 'Station Facilities', i18nKey: 'web.combat.subcategory.facilities' }
            ],
            'Armaments': [
                { label: 'Machine Guns', i18nKey: 'web.combat.subcategory.machine_guns' },
                { label: 'Cannons', i18nKey: 'web.combat.subcategory.cannons' },
                { label: 'AAA Guns', i18nKey: 'web.combat.subcategory.aaa_guns' },
                { label: 'Rocket Launchers', i18nKey: 'web.combat.subcategory.rocket_launchers' },
                { label: 'Searchlights', i18nKey: 'web.combat.subcategory.searchlights' },
                { label: 'Radars', i18nKey: 'web.combat.subcategory.radars' }
            ],
            'Buildings': [
                { label: 'Residential Buildings', i18nKey: 'web.combat.subcategory.residential' },
                { label: 'Facilities', i18nKey: 'web.combat.subcategory.facilities' },
                { label: 'Bridges', i18nKey: 'web.combat.subcategory.bridges' }
            ],
            'Marine': [
                { label: 'Light', i18nKey: 'web.combat.subcategory.light' },
                { label: 'Cargo', i18nKey: 'web.combat.subcategory.cargo' },
                { label: 'Submarines', i18nKey: 'web.combat.subcategory.submarines' },
                { label: 'Destroyers', i18nKey: 'web.combat.subcategory.destroyers' }
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
                const translatedLabel = i18n.t(subcat.i18nKey);
                const formattedLabel = translatedLabel.replace('Armored ', 'Armored\n');
                label.textContent = formattedLabel;
                row.appendChild(label);

                const value = document.createElement('span');
                value.className = 'combat-subcategory-value';
                value.textContent = (byCategory[category.key] || {})[subcat.label] || 0;
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

        container.appendChild(this.createStat(i18n.t('web.stat.missions_completed'), totalMissions));
        container.appendChild(this.createStat(i18n.t('web.stat.flight_time'), totalFlightTime));
        container.appendChild(this.createStat(i18n.t('web.stat.average_flight_time'), averageDuration));

        const landingStats = Array.isArray(stats.landings) ? stats.landings : [];
        const filteredLandings = landingStats.filter(
            landing => landing && landing.label !== undefined && Number(landing.value || 0) > 0
        );

        if (filteredLandings.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-message';
            empty.textContent = i18n.t('web.stat.no_status_data');
            container.appendChild(empty);
            return container;
        }

        const landingLabelKeys = {
            'Safe Landings': 'web.stat.safe_landings',
            'Hard Landings / Crashes': 'web.stat.hard_landings_crashes',
            'Wounded Landings': 'web.stat.wounded_landings',
            'Bailouts': 'web.stat.bailouts',
            'KIA / MIA': 'web.stat.kia_mia'
        };

        filteredLandings.forEach(landing => {
            const labelKey = landingLabelKeys[landing.label];
            const label = labelKey ? i18n.t(labelKey) : i18n.tr(landing.label);
            container.appendChild(this.createStat(label, landing.value ?? 0));
        });

        return container;
    },
    
    /**
     * Render aircraft usage
     */
    renderAircraftUsage(usage) {
        const container = document.createElement('div');
        
        for (const [aircraft, data] of Object.entries(usage)) {
            const value = `${data.missions} missions (${data.kills} kills)`;
            container.appendChild(this.createStat(aircraft, value));
        }
        
        return container;
    },
    
    /**
     * Render career progression
     */
    renderCareerProgression(progression) {
        const container = document.createElement('div');
        const country = this.currentCampaign?.country;
        
        container.appendChild(this.createStat(i18n.t('web.stat.starting_rank'), translateRankName(progression.starting_rank, country)));
        container.appendChild(this.createStat(i18n.t('web.stat.final_rank'), translateRankName(progression.final_rank, country)));
        container.appendChild(this.createStat(i18n.t('web.stat.promotions'), progression.promotions_count));
        container.appendChild(this.createStat(i18n.t('web.stat.awards'), progression.awards_count));
        
        // Awards list
        if (progression.awards_list && progression.awards_list.length > 0) {
            const list = document.createElement('ul');
            list.className = 'awards-list';
            
            progression.awards_list.forEach(award => {
                const item = document.createElement('li');
                item.textContent = translateAwardName(award);
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
            container.appendChild(this.createStat(i18n.t('web.stat.first_mission'), timeline.first_mission_date));
        }
        
        if (timeline.last_mission_date) {
            container.appendChild(this.createStat(i18n.t('web.stat.last_mission'), timeline.last_mission_date));
        }
        
        if (timeline.duration_days !== null && timeline.duration_days !== undefined) {
            const durationText = i18n.t('web.stat.duration_days', { days: timeline.duration_days });
            container.appendChild(this.createStat(i18n.t('web.stat.duration'), durationText));
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
        link.textContent = `📄 ${i18n.t('web.button.download_pdf')}`;
        link.target = '_blank';
        
        this.elements.summaryContent.appendChild(link);
    },
    
    /**
     * Show error state
     */
    showError(message) {
        this.elements.title.textContent = 'Error';
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
