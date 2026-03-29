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
    } else if (countryKey === 'germany') {
        key = normalizeGermanyAwardNarrativeKey(key);
    } else if (countryKey === 'soviet') {
        key = normalizeUSSRAwardNarrativeKey(key);
    }

    return key;
};

const getAwardNarrativeCode = (event, countryKey) => {
    const rawCode = event?.award_code || event?.awardCode;
    // Skip numeric IDs (e.g. career numeric award codes like "201001") — fall through
    // to name-based lookup so the human-readable name_key in event.name is used instead.
    if (rawCode && !/^\d/.test(String(rawCode))) {
        let key = nameToI18nKey(rawCode);
        if (countryKey === 'usa') {
            key = normalizeUSAwardNarrativeKey(key);
        } else if (countryKey === 'britain') {
            key = normalizeBritainAwardNarrativeKey(key);
        } else if (countryKey === 'germany') {
            key = normalizeGermanyAwardNarrativeKey(key);
        } else if (countryKey === 'soviet') {
            key = normalizeUSSRAwardNarrativeKey(key);
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
        second_bar_to_the_distinguished_service_order: 'second_bar_to_the_dso',
        // Short asset name_keys (career events use AwardAsset.name_key)
        dfc:                     'distinguished_flying_cross_dfc',
        dfc_bar:                 'bar_to_the_dfc',
        dfc_2bar:                'second_bar_to_the_dfc',
        dfm:                     'distinguished_flying_medal_dfm',
        dfm_bar:                 'bar_to_the_dfm',
        dfm_2bar:                'second_bar_to_the_dfm',
        dso:                     'distinguished_service_order_dso',
        dso_bar:                 'bar_to_the_dso',
        dso_bar2:                'second_bar_to_the_dso',
        dso_bar3:                'third_bar_to_the_distinguished_service_order',
        af_cross:                'air_force_cross',
        af_cross_bar:            'bar_to_the_air_force_cross',
        af_cross_2bars:          'second_bar_to_the_air_force_cross',
        af_medal:                'air_force_medal',
        af_medal_bar:            'bar_to_the_air_force_medal',
        af_medal_2bars:          'second_bar_to_the_air_force_medal',
        france_germany_star:     'france_and_germany_star',
        victoria_cross_bar:      'bar_to_the_vc',
        wound_stripe_2:          'second_wound_stripe',
        wound_stripe_3:          'third_wound_stripe',
    };
    return mappings[key] || key;
};

const normalizeGermanyAwardNarrativeKey = (key) => {
    if (!key) {
        return key;
    }
    const mappings = {
        // Long display-name keys → narrative keys (campaign events)
        front_flying_clasp_for_fighters_in_bronze:            'front_flying_clasp_fighters_bronze',
        front_flying_clasp_for_fighters_in_silver:            'front_flying_clasp_fighters_silver',
        front_flying_clasp_for_fighters_in_gold:              'front_flying_clasp_fighters_gold',
        front_flying_clasp_for_fighters_in_gold_with_pendant: 'front_flying_clasp_fighters_gold',
        // Short asset name_key mappings (career events use AwardAsset.name_key)
        iron_cross_1st:              'iron_cross_1st_class',
        iron_cross_2nd:              'iron_cross_2nd_class',
        knights_cross:               'knights_cross_of_the_iron_cross',
        knights_cross_oak_leaves:    'with_oak_leaves',
        knights_cross_swords:        'with_oak_leaves_and_swords',
        knights_cross_diamonds:      'with_oak_leaves_swords_and_diamonds',
        knights_cross_gold_diamonds: 'with_golden_oak_leaves_swords_and_diamonds',
        german_cross_gold:           'german_cross_in_gold',
        honor_clasp:                 'luftwaffe_honor_roll_clasp',
        fighters_bronze:             'front_flying_clasp_fighters_bronze',
        fighters_silver:             'front_flying_clasp_fighters_silver',
        fighters_gold:               'front_flying_clasp_fighters_gold',
        fighters_gold_clasp:         'front_flying_clasp_fighters_gold',
        wound_badge_black:           'wound_badge_in_black',
        wound_badge_silver:          'wound_badge_in_silver',
        wound_badge_gold:            'wound_badge_in_gold',
    };
    return mappings[key] || key;
};

const normalizeUSAwardNarrativeKey = (key) => {
    if (!key) {
        return key;
    }
    // Short asset name_key mappings (career events use AwardAsset.name_key)
    const directMappings = {
        bronze_star:           'bronze_star_medal',
        bronze_star_1_oak:     'bronze_star_plus_one_oak_leaf_cluster',
        bronze_star_2_oak:     'bronze_star_plus_two_oak_leaf_clusters',
        air_medal_1_oak:       'air_medal_plus_one_oak_leaf_cluster',
        air_medal_1silver_oak: 'air_medal_plus_four_oak_leaf_clusters',
        air_medal_2_oak:       'air_medal_plus_two_oak_leaf_clusters',
        air_medal_3_oak:       'air_medal_plus_three_oak_leaf_clusters',
        air_medal_4_oak:       'air_medal_plus_four_oak_leaf_clusters',
        dfc_1_oak:             'dfc_plus_one_oak_leaf_cluster',
        dfc_1_silver_oak:      'dfc_plus_one_silver_oak_leaf_cluster',
        dfc_2_oak:             'dfc_plus_two_oak_leaf_clusters',
        dfc_3_oak:             'dfc_plus_three_oak_leaf_clusters',
        dfc_4_oak:             'dfc_plus_four_oak_leaf_clusters',
        dsc_1_oak:             'dsc_plus_one_oak_leaf_cluster',
        dsc_2_oak:             'dsc_plus_two_oak_leaf_clusters',
        dsc_3_oak:             'dsc_plus_three_oak_leaf_clusters',
        dsc_4_oak:             'dsc_plus_four_oak_leaf_clusters',
        medal_of_honor_1_oak:  'medal_of_honor_plus_one_oak_leaf_cluster',
        purple_heart_1_oak:    'purple_heart_plus_one_oak_leaf_cluster',
        purple_heart_2_oak:    'purple_heart_plus_two_oak_leaf_clusters',
        silver_star:           'silver_star_medal',
        silver_star_1_oak:     'silver_star_plus_one_oak_leaf_cluster',
        silver_star_2_oak:     'silver_star_plus_two_oak_leaf_clusters',
        eu_af_me_medal:        'european_african_middle_eastern_campaign_medal',
    };
    if (directMappings[key]) {
        return directMappings[key];
    }
    // Long display-name prefix replacements (campaign events)
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

const normalizeUSSRAwardNarrativeKey = (key) => {
    if (!key) {
        return key;
    }
    const mappings = {
        // Short asset name_keys → existing long narrative keys
        hero_soviet_union:         'hero_of_the_soviet_union',
        medal_battle_merit:        'medal_for_battle_merit',
        medal_courage:             'medal_for_courage',
        order_nevsky:              'order_of_alexander_nevsky',
        order_suvorov:             'order_of_suvorov_3rd_class',
        order_patriotic_war_1st:   'order_of_the_patriotic_war_1st_class',
        order_patriotic_war_2nd:   'order_of_the_patriotic_war_2nd_class',
        order_red_banner:          'order_of_the_red_banner',
        order_red_banner_2:        'order_of_the_red_banner_2nd_awarding',
        order_red_banner_3:        'order_of_the_red_banner_3rd_awarding',
        order_red_star:            'order_of_the_red_star',
        air_kill_bonus:            'aircraft_kill_bonus_1000_rubles',
        bomber_kill_bonus:         'bomber_kill_bonus_2000_rubles',
        bomber_kill_bonus1:        'bomber_kill_bonus_1500_rubles',
        bonus_15_sorties:          '15_combat_sorties_bonus_2000_rubles',
        bonus_25_sorties:          '25_combat_sorties_bonus_3000_rubles',
        bonus_40_sorties:          '40_combat_sorties_bonus_5000_rubles',
        bonus_5_sorties:           '5_combat_sorties_bonus_1500_rubles',
        dest_sub_kill_bonus:       'destroyer_or_submarine_kill_bonus_10000_rubles',
        fighter_kill_bonus:        'fighter_kill_bonus_1000_rubles',
        small_ship_kill_bonus:     'small_ship_kill_bonus_1000_rubles',
        transport_kill_bonus:      'transport_plane_kill_bonus_1500_rubles',
        transport_ship_kill_bonus: 'transport_ship_kill_bonus_3000_rubles',
        dfm_caucasus:              'medal_for_the_defense_of_the_caucasus',
        dfm_moscow:                'medal_for_the_defense_of_moscow',
        dfm_stalingrad:            'medal_for_the_defense_of_stalingrad',
    };
    return mappings[key] || key;
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

const translateOrFallback = (key, fallback, params = {}) => (
    i18n && typeof i18n.hasKey === 'function' && i18n.hasKey(key)
        ? i18n.t(key, params)
        : fallback
);

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
        additionalNotesEmpty: null,
        storiesSection: null,
        storiesStatus: null,
        storiesContent: null,
        storiesGenerateBtn: null
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
    currentStoriesEntryId: null,
    currentStoriesPayload: null,
    storiesLoading: false,
    storyBatchSize: 1,
    
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
        this.setupStoryHandlers();
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
        this.elements.personalDisplaySquadron = document.getElementById('personal-display-current-squadron');
        this.elements.personalSquadronRow = document.getElementById('personal-squadron-row');
        this.elements.squadronStatsSelector = document.getElementById('squadron-stats-selector');
        this.elements.squadronStatsSelectorWrap = document.getElementById('squadron-stats-selector-wrap');
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
        this.elements.summaryHeading = document.querySelector('[data-i18n="web.section.campaign_summary"]');
        this.elements.storiesSection = document.getElementById('stories-section');
        this.elements.storiesStatus = document.getElementById('stories-status');
        this.elements.storiesContent = document.getElementById('stories-content');
        this.elements.storiesGenerateBtn = document.getElementById('stories-generate-btn');
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

    setupStoryHandlers() {
        if (this.elements.storiesGenerateBtn) {
            this.elements.storiesGenerateBtn.addEventListener('click', () => this.generateStories());
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
        // 4. Medal Showcase Section

        const showcaseSection = page.querySelector('#medal-showcase-section');

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

        if (showcaseSection && showcaseSection.parentElement !== leftColumn) {
            if (eventsSection) {
                eventsSection.after(showcaseSection);
            } else {
                leftColumn.appendChild(showcaseSection);
            }
        }
    },


    /**
     * Load and display campaign or career details
     *
     * @param {string} entryId - Campaign name or career root id
     * @param {string} source  - "campaign" (default) | "career"
     */
    async load(entryId, source) {
        const resolvedSource = source || 'campaign';
        this._source = resolvedSource;
        console.log('Loading details:', resolvedSource, entryId);

        try {
            // Show loading state
            this.elements.title.textContent = 'Loading...';
            this.elements.eventsList.innerHTML = '<p>Loading events...</p>';
            this.elements.debriefingsContainer.innerHTML = '<p>Loading debriefings...</p>';
            this.elements.summaryContent.innerHTML = '<p>Loading summary...</p>';
            this.currentStoriesEntryId = entryId;
            this.currentStoriesPayload = null;
            this.renderStoriesSection({
                supported: resolvedSource === 'career' || resolvedSource === 'campaign',
                status: 'loading',
                message: (resolvedSource === 'career' || resolvedSource === 'campaign') ? 'Loading stories...' : '',
                chapters: []
            });

            // Fetch data from the appropriate provider
            const campaign = resolvedSource === 'career'
                ? await API.getCareerDetail(entryId)
                : await API.getCampaignDetail(entryId);

            if (!campaign) {
                throw new Error(resolvedSource === 'career' ? 'Career not found' : 'Campaign not found');
            }

            this.currentCampaign = campaign;

            // Apply per-campaign locale override if present
            // This affects ONLY the detail page rendering
            if (campaign.effective_locale && campaign.effective_locale !== i18n.getLocale()) {
                console.log(`[DetailPage] Switching to campaign locale: ${campaign.effective_locale}`);
                await i18n.setLocale(campaign.effective_locale);
                // Re-translate page elements with new locale
                App.translatePage();
            }

            this.applyBackgroundForCountry(campaign.country, { force: true });

            // Render components
            this.renderHeader(campaign);
            this.renderEvents(campaign.events);
            this.renderDebriefings(campaign.debriefings_html);
            this.renderSummary(campaign.summary);

            // Update middle-column heading to match data source
            if (this.elements.summaryHeading) {
                const summaryKey = resolvedSource === 'career'
                    ? 'web.section.career_summary'
                    : 'web.section.campaign_summary';
                this.elements.summaryHeading.dataset.i18n = summaryKey;
                this.elements.summaryHeading.textContent = i18n.t(summaryKey);
            }

            if (resolvedSource === 'career') {
                const basePersonalData = {
                    name: campaign.pilot_last_name || '',
                    first_name: campaign.pilot_first_name || '',
                    birthday: campaign.birth_date || '',
                    birth_country: getLocalizedCountryName(campaign.country) || campaign.country || '',
                };
                const squadronRecords = Array.isArray(campaign.squadron_records)
                    ? campaign.squadron_records
                    : [];
                const currentSquadronRecord = squadronRecords.find(record => record && record.is_current)
                    || squadronRecords[squadronRecords.length - 1]
                    || null;
                // Career mode: prefill personal data from the career API response
                // (no separate personal_data endpoint; data comes from cp.db)
                this.setPersonalDataDisplay({
                    ...basePersonalData,
                    squadron: this.formatCareerSquadronDisplay(currentSquadronRecord, campaign),
                });
                this.setPersonalDataFields({
                    name: campaign.pilot_last_name || '',
                    first_name: campaign.pilot_first_name || '',
                    birthday: campaign.birth_date || '',
                });
                // Show squadron row, hide birth-place row
                const birthPlaceRow = this.elements.personalDisplayBirthPlace?.closest('.personal-data-row');
                if (birthPlaceRow) birthPlaceRow.style.display = 'none';
                if (this.elements.personalSquadronRow) {
                    this.elements.personalSquadronRow.style.display = '';
                }
                // Hide additional notes edit controls (career uses display-only)
                if (this.elements.additionalNotesEditBtn) {
                    this.elements.additionalNotesEditBtn.style.display = 'none';
                }
                // Switch section heading to "Other Incidences" for career mode
                const notesHeadingCareer = document.querySelector('[data-i18n="web.section.additional_notes"]');
                if (notesHeadingCareer) {
                    notesHeadingCareer.dataset.i18n = 'web.section.other_incidences';
                    notesHeadingCareer.textContent = i18n.t('web.section.other_incidences');
                }
                // Hide the static h3 — the <details><summary> inside display replaces it
                const notesH3Career = this.elements.additionalNotesDisplay
                    ?.closest('.additional-notes-section')
                    ?.querySelector('h3');
                if (notesH3Career) notesH3Career.style.display = 'none';
                // Render database-driven incidences instead of user notes
                this.renderOtherIncidences(campaign.other_incidences || []);
                // Render squadron statistics below the 3-column layout
                this.renderSquadronStats(
                    squadronRecords,
                    currentSquadronRecord,
                    selectedRecord => {
                        this.setPersonalDataDisplay({
                            ...basePersonalData,
                            squadron: this.formatCareerSquadronDisplay(selectedRecord, campaign),
                        });
                    }
                );
            } else {
                // Campaign mode: restore row visibility and load from personal_data API
                const birthPlaceRow = this.elements.personalDisplayBirthPlace?.closest('.personal-data-row');
                if (birthPlaceRow) birthPlaceRow.style.display = '';
                if (this.elements.personalSquadronRow) {
                    this.elements.personalSquadronRow.style.display = 'none';
                }
                if (this.elements.additionalNotesEditBtn) {
                    this.elements.additionalNotesEditBtn.style.display = '';
                }
                // Restore section heading to "Additional Incidents" for campaign mode
                const notesHeadingCampaign = document.querySelector(
                    '[data-i18n="web.section.other_incidences"], [data-i18n="web.section.additional_notes"]'
                );
                if (notesHeadingCampaign) {
                    notesHeadingCampaign.dataset.i18n = 'web.section.additional_notes';
                    notesHeadingCampaign.textContent = i18n.t('web.section.additional_notes');
                }
                // Restore the static h3 hidden in career mode
                const notesH3Campaign = this.elements.additionalNotesDisplay
                    ?.closest('.additional-notes-section')
                    ?.querySelector('h3');
                if (notesH3Campaign) notesH3Campaign.style.display = '';
                await this.loadPersonalData(campaign.name);
                // Hide squadron stats section for campaign mode
                const sqSection = document.getElementById('squadron-stats-section');
                if (sqSection) sqSection.style.display = 'none';
                if (this.elements.squadronStatsSelector) {
                    this.elements.squadronStatsSelector.innerHTML = '';
                    this.elements.squadronStatsSelector.onchange = null;
                }
                if (this.elements.squadronStatsSelectorWrap) {
                    this.elements.squadronStatsSelectorWrap.style.display = 'none';
                }
            }

            await this.loadPilotPhoto(campaign.name);

            // Check for PDF
            this.checkPDF(campaign.name);

            // Medal Showcase button
            this.setupMedalShowcase(campaign.name, campaign.country);

            await this.loadStories(entryId, resolvedSource);

            // Career first-run debriefing parse (inline panel indicator, 3-second grace period)
            if (resolvedSource === 'career' && campaign.debriefings_pending) {
                this._startDebriefParse(entryId);
            }

        } catch (error) {
            console.error('Failed to load campaign details:', error);
            this.showError(error.message);
        }
    },

    setStoriesStatus(message, tone = '') {
        const status = this.elements.storiesStatus;
        if (!status) {
            return;
        }
        status.textContent = message || '';
        status.classList.remove('is-error', 'is-success');
        if (tone === 'error') {
            status.classList.add('is-error');
        } else if (tone === 'success') {
            status.classList.add('is-success');
        }
    },

    setStoriesBusy(isBusy) {
        this.storiesLoading = !!isBusy;
        if (this.elements.storiesGenerateBtn) {
            this.elements.storiesGenerateBtn.disabled = !!isBusy;
        }
    },

    renderStoriesSection(payload) {
        const section = this.elements.storiesSection;
        const content = this.elements.storiesContent;
        const button = this.elements.storiesGenerateBtn;
        if (!section || !content) {
            return;
        }

        const source = this._source || 'campaign';
        const supported = !!payload?.supported;
        const enabled = payload?.enabled === true;
        const storyCapableSource = source === 'career' || source === 'campaign';
        const shouldShow = storyCapableSource && (enabled || payload?.status === 'loading');
        section.style.display = shouldShow ? '' : 'none';
        if (!shouldShow) {
            return;
        }

        const chapters = Array.isArray(payload?.chapters) ? payload.chapters : [];
        const status = payload?.status || 'ready';
        const message = payload?.message || '';
        this.currentStoriesPayload = payload || null;

        if (button) {
            const canGenerate = supported && payload?.enabled && payload?.configured;
            button.style.display = supported ? '' : 'none';
            button.disabled = this.storiesLoading || !canGenerate;
            button.textContent = chapters.length > 0
                ? translateOrFallback('web.button.generate_missing_stories', 'Generate Missing Stories')
                : translateOrFallback('web.button.generate_stories', 'Generate Stories');
        }

        const tone = status === 'auth_error' || status === 'quota_error' || status === 'api_error' || status === 'not_configured' || status === 'disabled'
            ? 'error'
            : (status === 'generated' ? 'success' : '');
        this.setStoriesStatus(message, tone);

        content.innerHTML = '';
        if (chapters.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-message';
            empty.textContent = status === 'loading'
                ? message || 'Loading stories...'
                : translateOrFallback('web.message.no_story_chapters', 'No story chapters available yet.');
            content.appendChild(empty);
            return;
        }

        chapters.forEach((chapter, index) => {
            const details = document.createElement('details');
            details.className = 'story-chapter';
            if (index === chapters.length - 1) {
                details.open = true;
            }

            const summary = document.createElement('summary');
            summary.className = 'story-chapter__summary';
            const chapterLabel = translateOrFallback('web.label.chapter', 'Chapter');
            summary.textContent = `${chapterLabel} ${chapter.chapter_index || '—'} | ${chapter.date || '—'} | ${chapter.aircraft || '—'} | ${chapter.result || '—'}`;
            details.appendChild(summary);

            const bodyWrap = document.createElement('div');
            bodyWrap.className = 'story-chapter__content';

            if (chapter.title) {
                const title = document.createElement('div');
                title.className = 'story-chapter__title';
                title.textContent = chapter.title;
                bodyWrap.appendChild(title);
            }

            const body = document.createElement('div');
            body.className = 'story-chapter__body';
            body.textContent = chapter.story_text || '';
            bodyWrap.appendChild(body);

            details.appendChild(bodyWrap);
            content.appendChild(details);
        });
    },

    async loadStories(entryId, source) {
        if (source !== 'career' && source !== 'campaign') {
            this.renderStoriesSection({
                supported: false,
                status: 'unsupported',
                message: '',
                chapters: []
            });
            return;
        }

        try {
            const payload = await API.getStories(source, entryId);
            this.renderStoriesSection(payload);

            if (
                payload?.supported
                && payload?.enabled
                && payload?.configured
                && payload?.auto_generate
                && (!Array.isArray(payload?.chapters) || payload.chapters.length === 0)
            ) {
                await this.generateStories({ silentReadyMessage: true });
            }
        } catch (error) {
            console.error('Failed to load stories:', error);
            this.renderStoriesSection({
                supported: true,
                status: 'api_error',
                message: error.message || 'Unable to load stories.',
                chapters: []
            });
        }
    },

    async generateStories(options = {}) {
        if (!this.currentStoriesEntryId || this.storiesLoading) {
            return;
        }
        if (this._source !== 'career' && this._source !== 'campaign') {
            return;
        }

        this.setStoriesBusy(true);
        this.setStoriesStatus(
            translateOrFallback('web.message.generating_stories', 'Generating stories...'),
            ''
        );

        try {
            const payload = await API.generateStories(
                this._source,
                this.currentStoriesEntryId,
                { max_chapters: this.storyBatchSize }
            );
            if (payload && payload.generated_count > 0 && !options.silentReadyMessage) {
                payload.status = 'generated';
                const remaining = Number(payload.remaining_count || 0);
                const generatedText = `${payload.generated_count} stor${payload.generated_count === 1 ? 'y chapter was' : 'y chapters were'} generated.`;
                payload.message = remaining > 0
                    ? `${generatedText} ${remaining} remaining.`
                    : generatedText;
            } else if (payload && !payload.message) {
                payload.message = translateOrFallback('web.message.story_generation_up_to_date', 'Stories are already up to date.');
            }
            this.renderStoriesSection(payload);
        } catch (error) {
            console.error('Failed to generate stories:', error);
            this.setStoriesStatus(error.message || 'Story generation failed.', 'error');
        } finally {
            this.setStoriesBusy(false);
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
            const displayData = this._source === 'career'
                ? {
                    ...savedData,
                    birth_country: this.getDisplayedPersonalDataValue(this.elements.personalDisplayBirthCountry),
                    squadron: this.getDisplayedPersonalDataValue(this.elements.personalDisplaySquadron),
                }
                : savedData;
            this.setPersonalDataDisplay(displayData);
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

    getDisplayedPersonalDataValue(element) {
        const value = element?.textContent?.trim() || '';
        return value === '—' ? '' : value;
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
        if (this.elements.personalDisplaySquadron) {
            this.elements.personalDisplaySquadron.textContent = this.formatPersonalDataValue(data.squadron);
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
     * Render database-driven "Other Incidences" entries (career mode only).
     *
     * Wraps all content in a collapsible <details open class="theatre-section">
     * element using the same CSS classes as theatre debriefing groups in the
     * right column. Supported types: RECOVERY, COMMAND, SQUADRON_CHANGE, BONUS.
     */
    renderOtherIncidences(incidences) {
        const display = this.elements.additionalNotesDisplay;
        if (!display) return;

        display.innerHTML = '';

        const details = document.createElement('details');
        details.className = 'theatre-section';
        details.open = true;

        const summary = document.createElement('summary');
        summary.className = 'theatre-header';
        summary.setAttribute('data-i18n', 'web.section.other_incidences');
        summary.textContent = i18n.t('web.section.other_incidences');
        details.appendChild(summary);

        const inner = document.createElement('div');
        inner.className = 'theatre-missions';

        if (!incidences || incidences.length === 0) {
            const empty = document.createElement('span');
            empty.className = 'additional-notes-empty';
            empty.setAttribute('data-i18n', 'web.message.no_entries');
            empty.textContent = i18n.t('web.message.no_entries');
            inner.appendChild(empty);
        } else {
            for (const inc of incidences) {
                const p = document.createElement('p');
                p.className = 'other-incidence-entry';

                if (inc.type === 'RECOVERY') {
                    p.textContent = [
                        inc.start_date, '\u2013', inc.end_date, '\u2013',
                        i18n.t('web.label.recovery_from_injury'), '\u2013',
                        `${inc.duration_days} ${i18n.t('web.stat.days_word')}`,
                    ].join(' ');
                } else if (inc.type === 'COMMAND') {
                    p.textContent = [
                        inc.date, '\u2013',
                        inc.squadron
                            ? i18n.t('web.label.appointment_commander_squadron', { squadron: inc.squadron })
                            : i18n.t('web.label.appointment_commander'),
                    ].join(' ');
                } else if (inc.type === 'SQUADRON_CHANGE') {
                    p.textContent = [
                        inc.date, '\u2013',
                        i18n.t('web.label.squadron_transfer_from_to', { from: inc.old_squadron, to: inc.new_squadron }),
                    ].join(' ');
                } else if (inc.type === 'BONUS') {
                    p.textContent = [
                        inc.date, '\u2013',
                        i18n.tr(`progression.awards.${inc.name}`, { defaultText: inc.name }),
                    ].join(' ');
                } else if (inc.type === 'AWARD_REPEAT') {
                    p.textContent = [
                        inc.date, '\u2013',
                        i18n.tr(`progression.awards.${inc.name}`, { defaultText: inc.name }),
                    ].join(' ');
                }

                inner.appendChild(p);
            }
        }

        details.appendChild(inner);
        display.appendChild(details);
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
        const dateText = this.localizeDebriefingDates(event.date || `Mission ${event.mission_number || '?'}`);
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
    /**
     * Start a background debrief parse job for a career.
     * Shows an inline spinner in the debriefings panel only if parsing exceeds 3 seconds.
     */
    _startDebriefParse(entryId) {
        const container = this.elements.debriefingsContainer;
        let jobDone = false;
        let elapsedSeconds = 0;
        let elapsedInterval = null;
        let gracePeriodTimer = null;
        let pollInterval = null;

        function stopTimers() {
            if (gracePeriodTimer !== null) { clearTimeout(gracePeriodTimer); gracePeriodTimer = null; }
            if (elapsedInterval !== null) { clearInterval(elapsedInterval); elapsedInterval = null; }
            if (pollInterval !== null) { clearInterval(pollInterval); pollInterval = null; }
        }

        API.startCareerParse(entryId).then(({ job_id }) => {
            // After 3 s, show inline indicator if job is still running.
            gracePeriodTimer = setTimeout(() => {
                if (jobDone) return;
                elapsedSeconds = 3;
                const mm = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
                const ss = String(elapsedSeconds % 60).padStart(2, '0');
                container.innerHTML =
                    `<div class="debriefings-parsing">` +
                    `<div class="spinner debriefings-parsing__spinner"></div>` +
                    `<p class="debriefings-parsing__text">` +
                    `${i18n.t('ui.progress.preparing_debriefings')} ` +
                    `<span class="debriefings-parsing__elapsed" id="debrief-elapsed">${mm}:${ss}</span>` +
                    `</p></div>`;
                elapsedInterval = setInterval(() => {
                    elapsedSeconds++;
                    const m = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
                    const s = String(elapsedSeconds % 60).padStart(2, '0');
                    const el = document.getElementById('debrief-elapsed');
                    if (el) el.textContent = `${m}:${s}`;
                }, 1000);
            }, 3000);

            // Poll job status every second.
            pollInterval = setInterval(async () => {
                try {
                    const status = await API.getJobStatus(job_id);
                    if (status.status === 'done') {
                        stopTimers();
                        jobDone = true;
                        try {
                            const fresh = await API.getCareerDetail(entryId);
                            if (fresh) {
                                this.renderDebriefings(fresh.debriefings_html);
                                this.renderSummary(fresh.summary);
                            }
                        } catch (err) {
                            console.warn('[DetailPage] Re-fetch after parse failed:', err);
                        }
                    } else if (status.status === 'error') {
                        stopTimers();
                        jobDone = true;
                        console.error('[DetailPage] Career parse job failed:', status.error);
                        this.renderDebriefings('');
                    }
                } catch (_) {
                    // transient network glitch – keep polling
                }
            }, 1000);
        }).catch(err => {
            console.error('[DetailPage] Failed to start career parse job:', err);
            this.renderDebriefings('');
        });
    },

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
            { pattern: /\bGuns\b:/gi, replacement: `${i18n.t('flightlog.metrics.guns')}:` },
            { pattern: /\bBombs\b:/gi, replacement: `${i18n.t('flightlog.metrics.bombs')}:` },
            { pattern: /\bRockets\b:/gi, replacement: `${i18n.t('flightlog.metrics.rockets')}:` },
            { pattern: /\bhits\b/gi, replacement: i18n.t('flightlog.metrics.hits') },
            { pattern: /\bacc\b/gi, replacement: i18n.t('flightlog.metrics.accuracy') },
            { pattern: /\bdropped\b/gi, replacement: i18n.t('flightlog.metrics.dropped') },
            { pattern: /\bfired\b/gi, replacement: i18n.t('flightlog.metrics.fired') },
            { pattern: /\bmixed ordnance\b/gi, replacement: i18n.t('flightlog.metrics.mixed_ordnance') },
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
            'Hard Landing': i18n.t('flightlog.status.hard_landing'),
            'Alive': i18n.t('flightlog.status.alive')
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
                this.renderCombatResults(summary.combat_results),
                true
            ));
        }

        if (summary.air_kills_by_type && Object.keys(summary.air_kills_by_type).length > 0) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.air_kills_by_type'),
                this.renderAirKillsByType(summary.air_kills_by_type),
                true
            ));
        }

        if (summary.missions_stats) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.missions_flown'),
                this.renderMissionsStats(summary.missions_stats),
                true
            ));
        }

        if (summary.aircraft_usage && Object.keys(summary.aircraft_usage).length > 0) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.aircraft_flown'),
                this.renderAircraftUsage(summary.aircraft_usage),
                true
            ));
        }

        if (summary.career_progression) {
            sections.push(this.createSummarySection(
                i18n.t('web.section.career_progression'),
                this.renderCareerProgression(summary.career_progression),
                true
            ));
        }

        if (summary.timeline && summary.timeline.first_mission_date) {
            const timelineKey = this._source === 'career'
                ? 'web.section.career_timeline'
                : 'web.section.campaign_timeline';
            sections.push(this.createSummarySection(
                i18n.t(timelineKey),
                this.renderTimeline(summary.timeline),
                this._source === 'career'
            ));
        }

        sections.forEach(section => this.elements.summaryContent.appendChild(section));
    },
    
    /**
     * Create summary section wrapper
     */
    createSummarySection(title, content, collapsible = false) {
        if (collapsible) {
            const section = document.createElement('details');
            section.className = 'theatre-section summary-section';
            section.open = true;

            const header = document.createElement('summary');
            header.className = 'theatre-header summary-section-header';
            header.textContent = title;
            section.appendChild(header);

            const body = document.createElement('div');
            body.className = 'theatre-missions summary-section-body';
            body.appendChild(content);
            section.appendChild(body);

            return section;
        }

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
        const hasPcp = results.pcp_score !== undefined;
        const scoreLabel = hasPcp ? i18n.t('web.stat.pcp_score') : i18n.t('web.stat.overall_score');
        const scoreValue = hasPcp ? (results.pcp_score ?? 0) : (results.total_score ?? 0);
        summaryStats.appendChild(this.createInlineStat(scoreLabel, scoreValue));
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
            const value = `${data.missions} ${i18n.t('pdf.value.missions')} (${data.kills} ${i18n.t('pdf.value.kills')})`;
            container.appendChild(this.createStat(aircraft, value));
        }
        
        return container;
    },

    /**
     * Render destroyed aircraft types
     */
    renderAirKillsByType(killsByType) {
        const container = document.createElement('div');

        for (const [aircraft, count] of Object.entries(killsByType)) {
            container.appendChild(this.createStat(aircraft, count ?? 0));
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
        const prefix = this._source === 'career' ? '/api/career_assets' : '/api/game_assets';
        return `${prefix}/${normalized}`;
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
     * Set up or refresh the Medal Showcase button in the left column.
     * Probes the showcase API to determine availability before showing button.
     */
    async setupMedalShowcase(campaignName, country) {
        const section = document.getElementById('medal-showcase-section');
        if (!section) return;

        // Clear any previous button
        section.innerHTML = '';
        section.style.display = 'none';

        if (!campaignName || !country) return;

        // Show the button optimistically (API probe happens on click)
        const btn = (typeof createMedalShowcaseButton === 'function')
            ? createMedalShowcaseButton()
            : (() => {
                const b = document.createElement('button');
                b.type = 'button';
                b.id = 'medal-showcase-btn';
                b.className = 'medal-showcase-btn';
                b.textContent = i18n.t('ui.medal_showcase.button');
                return b;
            })();

        if (this._source === 'career') {
            btn.addEventListener('click', () => {
                if (typeof openCareerMedalShowcase === 'function') {
                    openCareerMedalShowcase(campaignName, btn);
                }
            });
        } else {
            btn.addEventListener('click', () => {
                if (typeof openMedalShowcase === 'function') {
                    openMedalShowcase(campaignName, btn);
                }
            });
        }

        section.appendChild(btn);
        section.style.display = '';
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
    },

    formatCareerSquadronDisplay(record, campaign) {
        let squadron = record?.squadron_short_name || campaign?.squadron_short_name || '';
        const role = record?.pilot_role || campaign?.pilot_role || '';
        if (role === 'commander' || role === 'deputy_commander') {
            const roleLabel = i18n.t(`ui.career.role.${role}`);
            if (roleLabel) {
                squadron = squadron ? `${squadron} (${roleLabel})` : `(${roleLabel})`;
            }
        }
        return squadron;
    },

    /**
     * Render the squadron statistics section (career mode only).
     * Shows an aggregated totals row and a per-pilot roster table.
     *
     * @param {Array} records
     * @param {Object|null} initialRecord
     * @param {Function|null} onRecordChange
     */
    renderSquadronStats(records, initialRecord, onRecordChange) {
        const section = document.getElementById('squadron-stats-section');
        const content = document.getElementById('squadron-stats-content');
        const selector = this.elements.squadronStatsSelector;
        const selectorWrap = this.elements.squadronStatsSelectorWrap;
        if (!section || !content) return;

        content.innerHTML = '';

        const availableRecords = Array.isArray(records)
            ? records.filter(record => record && Array.isArray(record.members))
            : [];

        if (selector) {
            selector.innerHTML = '';
            selector.onchange = null;
        }

        if (availableRecords.length === 0) {
            section.style.display = 'none';
            if (selectorWrap) selectorWrap.style.display = 'none';
            return;
        }

        section.style.display = '';
        let selectedRecord = availableRecords.find(record =>
            record.theatre_index === initialRecord?.theatre_index
        ) || availableRecords.find(record => record.is_current) || availableRecords[availableRecords.length - 1];

        if (selector && selectorWrap) {
            selectorWrap.style.display = availableRecords.length > 1 ? '' : 'none';
            selector.setAttribute('aria-label', i18n.t('ui.career.squadron_statistics'));
            availableRecords.forEach(record => {
                const option = document.createElement('option');
                option.value = String(record.theatre_index ?? '');
                option.textContent = `${record.theatre_label || '—'} - ${record.squadron_short_name || '—'}`;
                option.selected = record.theatre_index === selectedRecord.theatre_index;
                selector.appendChild(option);
            });
        }

        const totalKillCols = [
            { key: 'kills_air',       icon: 'icon_aircraft.png',   i18nKey: 'web.combat.category.aircraft'  },
            { key: 'kills_vehicles',  icon: 'icon_vehicles.png',   i18nKey: 'web.combat.category.vehicles'  },
            { key: 'kills_railroad',  icon: 'icon_railroad.png',   i18nKey: 'web.combat.category.railroad'  },
            { key: 'kills_armaments', icon: 'icon_armaments.png',  i18nKey: 'web.combat.category.armaments' },
            { key: 'kills_buildings', icon: 'icon_buildings.png',  i18nKey: 'web.combat.category.buildings' },
            { key: 'kills_marine',    icon: 'icon_marine.png',     i18nKey: 'web.combat.category.marine'    },
        ];

        const memberStatCols = [
            ...totalKillCols,
            { key: 'kill_assist',     icon: 'kill_assist.png',     i18nKey: 'ui.career.squadron_col_kill_assist' },
        ];

        // Sort state
        let sortCol = null;   // null = default (rank → air kills)
        let sortAsc = false;

        // Returns a numeric sort key for a given column id and member.
        // "Larger is better" for descending sort (default).
        const getSortValue = (col, m) => {
            switch (col) {
                case 'rank':         return m.rank_id ?? -1;
                case 'name':         return (m.name || '').toLowerCase();
                case 'award':        return m.highest_award_precedence != null
                                         ? -m.highest_award_precedence   // lower prec = better → negate
                                         : -99999;
                case 'state':        return m.state ?? 0;
                case 'sorties_good': return m.sorties_good ?? 0;
                case 'sorties':      return m.sorties ?? 0;
                case 'flight_time':  return m.flight_time_sec ?? 0;
                default:             return m[col] ?? 0;   // kill bucket keys
            }
        };

        const defaultSort = (a, b) => {
            const rd = (b.rank_id ?? -1) - (a.rank_id ?? -1);
            return rd !== 0 ? rd : (b.kills_air ?? 0) - (a.kills_air ?? 0);
        };

        const getSortedMembers = () => {
            const arr = (selectedRecord?.members || []).slice();
            if (!sortCol) return arr.sort(defaultSort);
            return arr.sort((a, b) => {
                const av = getSortValue(sortCol, a);
                const bv = getSortValue(sortCol, b);
                const dir = sortAsc ? 1 : -1;
                if (av < bv) return -dir;
                if (av > bv) return dir;
                return 0;
            });
        };

        // State icon map
        const stateIconMap = {
            1: 'squadroncommander.png',
            8: 'squadrondeputycommander.png',
            2: 'kia.png',
            3: 'mia.png',
            4: 'wia.png',
            5: 'character_left.png',
        };
        const stateTitleMap = {
            1: i18n.t('ui.career.role.commander'),
            8: i18n.t('ui.career.role.deputy_commander'),
            2: i18n.t('ui.career.role.kia'),
            3: i18n.t('ui.career.role.mia'),
            4: i18n.t('ui.career.role.wia'),
            5: i18n.t('ui.career.role.transferred'),
        };
        let tbody = null;

        const buildRow = (member) => {
            const tr = document.createElement('tr');

            // Rank image
            const tdRank = document.createElement('td');
            if (member.rank_image_url) {
                const rankImg = document.createElement('img');
                rankImg.src = member.rank_image_url;
                rankImg.alt = member.rank_display || '';
                rankImg.title = member.rank_display || '';
                rankImg.className = 'sq-rank-img';
                rankImg.addEventListener('load', () => {
                    if (rankImg.naturalWidth) {
                        rankImg.style.width  = Math.round(rankImg.naturalWidth  * 0.35) + 'px';
                        rankImg.style.height = Math.round(rankImg.naturalHeight * 0.35) + 'px';
                    }
                });
                tdRank.appendChild(rankImg);
            }
            tr.appendChild(tdRank);

            // Name
            const tdName = document.createElement('td');
            tdName.className = 'sq-col-name';
            tdName.textContent = member.name || '—';
            tr.appendChild(tdName);

            // Highest Combat Award
            const tdAward = document.createElement('td');
            if (member.highest_award_image_url) {
                const awardImg = document.createElement('img');
                awardImg.src = member.highest_award_image_url;
                const awardName = member.highest_award_name_key
                    ? i18n.t(member.highest_award_name_key)
                    : (member.highest_award_code || '');
                awardImg.alt   = awardName;
                awardImg.title = awardName;
                awardImg.className = 'sq-award-img';
                awardImg.addEventListener('load', () => {
                    if (awardImg.naturalWidth) {
                        awardImg.style.width  = Math.round(awardImg.naturalWidth  * 0.5) + 'px';
                        awardImg.style.height = Math.round(awardImg.naturalHeight * 0.5) + 'px';
                    }
                });
                tdAward.appendChild(awardImg);
            }
            tr.appendChild(tdAward);

            // State
            const tdState = document.createElement('td');
            const stateIcon = stateIconMap[member.state];
            if (stateIcon) {
                const sImg = document.createElement('img');
                sImg.src = this.getGameAssetUrl(`CampaignRanksAwards/Misc/${stateIcon}`);
                sImg.alt = '';
                sImg.title = stateTitleMap[member.state] || String(member.state);
                sImg.className = 'sq-state-img';
                tdState.appendChild(sImg);
            }
            tr.appendChild(tdState);

            // Kill columns
            memberStatCols.forEach(col => {
                const td = document.createElement('td');
                const val = member[col.key] ?? 0;
                td.textContent = val;
                if (val === 0) td.className = 'sq-zero';
                tr.appendChild(td);
            });

            // Good sorties
            const tdGood = document.createElement('td');
            const gv = member.sorties_good ?? 0;
            tdGood.textContent = gv;
            if (gv === 0) tdGood.className = 'sq-zero';
            tr.appendChild(tdGood);

            // Sorties
            const tdSorties = document.createElement('td');
            const sv = member.sorties ?? 0;
            tdSorties.textContent = sv;
            if (sv === 0) tdSorties.className = 'sq-zero';
            tr.appendChild(tdSorties);

            // Flight time (seconds → "Xh Ym")
            const tdFt = document.createElement('td');
            const secs = member.flight_time_sec ?? 0;
            if (secs > 0) {
                const h = Math.floor(secs / 3600);
                const m = Math.floor((secs % 3600) / 60);
                tdFt.textContent = m > 0 ? `${h}h ${m}m` : `${h}h`;
            } else {
                tdFt.textContent = '0h';
                tdFt.className = 'sq-zero';
            }
            tr.appendChild(tdFt);

            return tr;
        };

        const rebuildTbody = () => {
            if (!tbody) return;
            tbody.innerHTML = '';
            getSortedMembers().forEach(m => tbody.appendChild(buildRow(m)));
        };

        const renderSelectedRecord = () => {
            content.innerHTML = '';

            if (typeof onRecordChange === 'function') {
                onRecordChange(selectedRecord);
            }

            const totals = selectedRecord?.totals || {};

            const totalsDiv = document.createElement('div');
            totalsDiv.className = 'squadron-totals';
            totalKillCols.forEach(col => {
                const cell = document.createElement('div');
                cell.className = 'squadron-totals__cell';

                const img = document.createElement('img');
                img.src = this.getGameAssetUrl(`CampaignRanksAwards/Misc/${col.icon}`);
                img.alt = i18n.t(col.i18nKey);
                img.className = 'squadron-totals__icon';
                cell.appendChild(img);

                const count = document.createElement('div');
                count.className = 'squadron-totals__count';
                count.textContent = totals[col.key] ?? 0;
                cell.appendChild(count);

                const label = document.createElement('div');
                label.className = 'squadron-totals__label';
                label.textContent = i18n.t(col.i18nKey);
                cell.appendChild(label);

                totalsDiv.appendChild(cell);
            });
            content.appendChild(totalsDiv);

            const wrapper = document.createElement('div');
            wrapper.className = 'squadron-table-wrapper';

            const table = document.createElement('table');
            table.className = 'squadron-table';

            // Build a th with optional sort support.
            // colId null = not sortable; 'rank' = resets to default sort.
            const makeTh = (colId, labelNode, extraClass) => {
                const th = document.createElement('th');
                if (extraClass) th.className = extraClass;
                if (typeof labelNode === 'string') {
                    th.textContent = labelNode;
                } else {
                    th.appendChild(labelNode);
                }
                if (colId !== null) {
                    th.classList.add('sq-th-sortable');
                    th.dataset.sortCol = colId;
                    const indicator = document.createElement('span');
                    indicator.className = 'sq-sort-indicator';
                    th.appendChild(indicator);
                    th.addEventListener('click', () => {
                        if (colId === 'rank') {
                            sortCol = null;
                            sortAsc = false;
                        } else if (sortCol === colId) {
                            sortAsc = !sortAsc;
                        } else {
                            sortCol = colId;
                            sortAsc = (colId === 'name');
                        }
                        updateSortIndicators();
                        rebuildTbody();
                    });
                }
                return th;
            };

            const thead = document.createElement('thead');
            tbody = document.createElement('tbody');

            const updateSortIndicators = () => {
                thead.querySelectorAll('.sq-sort-indicator').forEach(span => {
                    const col = span.parentElement.dataset.sortCol;
                    const isActive = (sortCol === col) || (col === 'rank' && sortCol === null);
                    span.textContent = isActive ? (sortAsc ? ' ▲' : ' ▼') : '';
                });
            };

            const headerRow = document.createElement('tr');
            headerRow.appendChild(makeTh('rank', i18n.t('ui.career.squadron_col_rank'), null));
            headerRow.appendChild(makeTh('name', i18n.t('ui.career.squadron_col_name'), 'sq-col-name'));
            headerRow.appendChild(makeTh('award', i18n.t('ui.career.squadron_col_highest_award'), null));

            const stateImgEl = document.createElement('img');
            stateImgEl.src = this.getGameAssetUrl('CampaignRanksAwards/Misc/state.png');
            stateImgEl.alt = i18n.t('ui.career.squadron_col_state');
            stateImgEl.title = i18n.t('ui.career.squadron_col_state');
            headerRow.appendChild(makeTh('state', stateImgEl, null));

            memberStatCols.forEach(col => {
                const img = document.createElement('img');
                img.src = this.getGameAssetUrl(`CampaignRanksAwards/Misc/${col.icon}`);
                img.alt = i18n.t(col.i18nKey);
                img.title = i18n.t(col.i18nKey);
                headerRow.appendChild(makeTh(col.key, img, null));
            });

            const goodImg = document.createElement('img');
            goodImg.src = this.getGameAssetUrl('CampaignRanksAwards/Misc/goodsorties.png');
            goodImg.alt = i18n.t('ui.career.squadron_col_good_sorties');
            goodImg.title = i18n.t('ui.career.squadron_col_good_sorties');
            headerRow.appendChild(makeTh('sorties_good', goodImg, null));

            const sortiesImg = document.createElement('img');
            sortiesImg.src = this.getGameAssetUrl('CampaignRanksAwards/Misc/sorties.png');
            sortiesImg.alt = i18n.t('ui.career.squadron_col_sorties');
            sortiesImg.title = i18n.t('ui.career.squadron_col_sorties');
            headerRow.appendChild(makeTh('sorties', sortiesImg, null));

            const ftImg = document.createElement('img');
            ftImg.src = this.getGameAssetUrl('CampaignRanksAwards/Misc/flighttime.png');
            ftImg.alt = i18n.t('ui.career.squadron_col_flight_time');
            ftImg.title = i18n.t('ui.career.squadron_col_flight_time');
            headerRow.appendChild(makeTh('flight_time', ftImg, null));

            thead.appendChild(headerRow);
            table.appendChild(thead);
            updateSortIndicators();

            rebuildTbody();
            table.appendChild(tbody);
            wrapper.appendChild(table);
            content.appendChild(wrapper);
        };

        if (selector) {
            selector.value = String(selectedRecord.theatre_index ?? '');
            selector.onchange = () => {
                const selectedIndex = Number(selector.value);
                const nextRecord = availableRecords.find(record => record.theatre_index === selectedIndex);
                if (!nextRecord) return;
                selectedRecord = nextRecord;
                renderSelectedRecord();
            };
        }

        renderSelectedRecord();
    }
};
