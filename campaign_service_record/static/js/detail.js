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
        close.setAttribute('aria-label', 'Close');
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

const EVENT_DESCRIPTIONS = {
    germany: {
        ranks: {
            Unteroffizier: 'New to the line, you fly tight on a leader’s wing and learn fast or die fast. Your logbook fills one sortie at a time.',
            Feldwebel: 'You’ve seen flak and fighters up close and you don’t flinch. Men follow your turns because they’ve learned you bring them home.',
            Oberfeldwebel: 'Veteran hands, tired eyes—still climbing into the cockpit. You lead by example and the rookies copy everything you do.',
            Leutnant: 'Now you carry a commission and the weight that comes with it. You still fly the same sky, just with more eyes depending on you.',
            Oberleutnant: 'You lead flights into weather, flak, and bad odds. The Staffel watches how you handle the first burst and the last decision.',
            Hauptmann: 'Command and combat collide: paperwork at dawn, engine heat by noon. You fly when it matters and your name rides every outcome.',
            Major: 'Your map table is larger than your cockpit time now. When you do fly, it’s because the mission can’t afford mistakes.',
            Oberstleutnant: 'You keep the unit running and the losses bear your signature. You fly rarely—usually to see the front with your own eyes.',
            Oberst: 'A commander with a pilot’s past and a war on his desk. If you take off, it’s for a reason everyone remembers.',
            Generalmajor: 'You move squadrons like chess pieces and count fuel like blood. Flight time is rare; responsibility is constant.',
            Generalleutnant: 'The war looks different from this altitude—briefings, orders, consequences. You earned wings once; now you carry a theater.'
        },
        awards: {
            "Pilot's Badge": 'You’ve earned the right to wear wings—and to be sent back up tomorrow. Training is over; the war starts now.',
            'Iron Cross 2nd Class': 'A first hard mark of combat service. Not glory—just proof you were there when it counted.',
            'Iron Cross 1st Class': 'You didn’t just survive; you delivered results. The unit knows you’re the one to call when it’s hot.',
            'Honor Goblet': 'A Luftwaffe trophy for men who fly beyond “enough.” It’s handed to those who keep coming back with victories and scars.',
            'German Cross in Gold': 'Sustained combat success, the long grind turned into metal. You’ve been tested—repeatedly—and held.',
            "Knight's Cross of the Iron Cross": 'The kind of award that changes how people look at you. Fame is loud; the war is louder.',
            '…with Oak Leaves': 'More proof, more pressure. They expect miracles now—and they write your name in bigger letters.',
            '…with Oak Leaves and Swords': 'A mark for relentless frontline achievement. You’re not just fighting—you’re shaping the fight.',
            '…with Oak Leaves, Swords and Diamonds': 'Rare, heavy, and impossible to ignore. Your record is legend; your risk stays real.',
            '…with Golden Oak Leaves, Swords and Diamonds': 'The top shelf, almost unheard of. You’ve become a symbol—and symbols still bleed.',
            'Front Flying Clasp (Fighters) Bronze': 'You’ve logged enough combat sorties to know the routine is deadly. The front doesn’t care how brave you feel.',
            'Front Flying Clasp (Fighters) Silver': 'A long run of sorties under pressure. You’ve outlasted luck and learned discipline.',
            'Front Flying Clasp (Fighters) Gold': 'Heavy operational time at the sharp end. You’ve lived where the sky is full of fire.',
            '…Gold with Pendant': 'An extreme tally of frontline sorties. You’ve been to war so often it feels like home—and that’s the danger.',
            'Wound Badge in Black': 'First blood paid to the front. You came back—this time.',
            'Wound Badge in Silver': 'More wounds, fewer illusions. You’re still flying, but you’ve started counting what it costs.',
            'Wound Badge in Gold': 'You’ve been hit again and again and kept returning. The badge shines; the damage doesn’t.'
        }
    },
    britain: {
        ranks: {
            Sergeant: 'Fresh wings, cold cockpit, and the Channel wind cutting through everything. Stay with your leader and keep your eyes moving.',
            'Flight Sergeant': 'You’ve learned the sound of trouble before you see it. In the air, you’re steady—because panic kills.',
            'Warrant Officer': 'A hard veteran in a soft uniform. You fly like you’ve paid for every lesson—and you have.',
            'Pilot Officer': 'Commissioned, but still proving yourself every sortie. The squadron judges you by the way you hold formation under fire.',
            'Flying Officer': 'You can lead a section and make it stick. When the radio goes quiet, your decisions speak loudest.',
            'Flight Lieutenant': 'You balance duty rosters and deadly skies. You still fly—because you won’t ask men to do what you won’t.',
            'Squadron Leader': 'The squadron’s tempo is yours to set: push too hard and you break it. You fly when the moment needs a steady hand.',
            'Wing Commander': 'You command wings and you feel every loss. You go up sometimes—enough to keep the war honest.',
            'Group Captain': 'A commander with a pilot’s instincts and a strategist’s burden. You fly rarely now, but you never stop listening to the engines.',
            'Air Commodore': 'You direct whole air battles from reports and maps. If you fly, it’s exceptional—and everyone notices.',
            'Air Vice Marshal': 'The air war runs through your desk and into the sky. Flight is rare; command is relentless.'
        },
        awards: {
            "RAF Pilot's Badge": 'Your wings are sewn on, and your life is scheduled around sorties. Welcome to the line.',
            'Mentioned in Despatches': 'Your name made it into the official reports. Quiet recognition for work done when it was most dangerous.',
            'Distinguished Flying Medal (DFM)': 'Courage and grit from an airman who kept flying. Earned the hard way, one operation after another.',
            'Bar to the DFM': 'They’re saying you did it again. Same sky, same risk—more proof you don’t quit.',
            'Second Bar to the DFM': 'Rare repeat recognition for relentless operations. You’re becoming the kind of flyer the squadron leans on.',
            'Distinguished Flying Cross (DFC)': 'Gallantry in the air, the kind that holds a formation together. The ribbon looks clean; the sorties weren’t.',
            'Bar to the DFC': 'Another round of hard flying that stood out. You’ve made danger a habit—and lived through it.',
            'Second Bar to the DFC': 'Almost unheard of. You’ve repeatedly done what shouldn’t be survivable.',
            'Distinguished Service Order (DSO)': 'Leadership under fire, not just bravery. You kept men fighting when the odds went ugly.',
            'Bar to the DSO': 'A second time they credit your command in combat. You’ve carried responsibility where it hurts.',
            'Second Bar to the DSO': 'Exceptionally rare and hard-won. You’ve led through repeated crisis and come out standing.',
            'Victoria Cross (VC)': 'The highest kind of courage—beyond orders, beyond reason. A moment that becomes history.',
            'Bar to the VC': 'A second VC is almost myth. It means you faced the impossible twice and refused to yield.',
            'Wound Stripe': 'Proof the war reached you personally. The body keeps the receipt.',
            'Second Wound Stripe': 'Hit again, still flying. Survival isn’t luck anymore—it’s endurance.',
            'Third Wound Stripe': 'Three wounds and still on the roster. The squadron sees you and knows what it costs.'
        }
    },
    usa: {
        ranks: {
            'First Sergeant': 'You keep the unit stitched together when the mission tears it apart. If you fly, it’s to share the risk, not the glory.',
            'Flight Officer': 'You’re rated to fly and thrown into the grinder. Learn fast, hit hard, and don’t waste luck.',
            'Chief Warrant Officer': 'You’re the quiet expert—engines, tactics, nerves of steel. When it gets ugly, they want you in the formation.',
            '2nd Lieutenant': 'Brand-new bars, same flak and same fear. Your lead is light, but the war doesn’t care.',
            '1st Lieutenant': 'You’ve seen enough to stop pretending it’s easy. Now you lead flights and carry men through bad weather and worse skies.',
            Captain: 'You’re a leader and a target both. You still fly—because credibility is earned at altitude.',
            Major: 'Plans, briefings, and harder calls than trigger pulls. You fly selectively now, usually when the mission needs a proven hand.',
            'Lt. Colonel': 'Bigger command, fewer takeoffs. When you do fly, it’s to see the truth beyond the paperwork.',
            Colonel: 'You command from the top but you’ve flown the hard miles. Flight is rare—your war is coordination and consequence.',
            'Brigadier General': 'You shape operations across units and bases. If you take the air, it’s a statement—and a risk you don’t take lightly.',
            'Major General': 'Strategy, logistics, and the weight of whole formations. Your flying days are mostly memory, but the sky is still yours.'
        },
        awards: {
            "Pilot's Badge": 'Your wings say you’re rated and ready. Now the mission board tells you where you’ll bleed for them.',
            'Air Medal': 'Meritorious flying under combat conditions. It’s the war’s way of saying you kept delivering.',
            'Air Medal + One Oak Leaf Cluster': 'You’ve earned it again. Same sky, more missions, more proof.',
            'Air Medal + Two Oak Leaf Clusters': 'A steady record of combat flying. You’re becoming a veteran by accumulation.',
            'Air Medal + Three Oak Leaf Clusters': 'Repeated awards for repeated sorties. The ribbon stack grows as the risks don’t stop.',
            'Bronze Star Medal': 'Combat merit and hard service recognized. Not glamorous—just earned where it’s dangerous.',
            'Bronze Star + One Oak Leaf Cluster': 'Another round of meritorious service under fire. They’re counting what you’ve carried.',
            'Bronze Star + Two Oak Leaf Clusters': 'A third recognition for staying effective in the long grind. You’ve become dependable the hard way.',
            'Distinguished Flying Cross': 'Heroism or extraordinary achievement in the air. The kind of sortie people talk about afterward.',
            'DFC + One Oak Leaf Cluster': 'You’ve done it again—another exceptional mission, another line in the record.',
            'DFC + Two Oak Leaf Clusters': 'A sustained pattern of standout flying. The enemy isn’t the only thing watching you now.',
            'DFC + Three Oak Leaf Clusters': 'Repeated extraordinary performance. Your reputation is built on missions that should’ve gone wrong.',
            'DFC + Four Oak Leaf Clusters': 'More than most ever see in a lifetime. It means you keep walking into the worst and coming out.',
            'DFC + One Silver Oak Leaf Cluster': 'A higher-count mark of repeat awards. You’ve stacked extraordinary sorties like normal work.',
            'Legion of Merit': 'Outstanding service over time, beyond a single fight. You’ve carried the war on your shoulders and kept it moving.',
            'Silver Star Medal': 'Gallantry in action. A moment of courage that refused to break.',
            'Silver Star + One Oak Leaf Cluster': 'Again, you stood when others might not. Repeated bravery under fire.',
            'Silver Star + Two Oak Leaf Clusters': 'A third gallantry award is a hard statement. You don’t just survive trouble—you face it.',
            'Distinguished Service Cross': 'Extraordinary heroism in combat. The kind of action that becomes a unit legend.',
            'DSC + One Oak Leaf Cluster': 'A second time for extreme heroism. That’s not luck—that’s a pattern of risk.',
            'DSC + Two Oak Leaf Clusters': 'A third award for extraordinary heroism. Few ever reach this—and fewer live through it.',
            'DSC + Three Oak Leaf Clusters': 'Repeated actions at the edge of survivability. Your record reads like a warning label.',
            'DSC + Four Oak Leaf Clusters': 'Almost unheard of. You’ve done the impossible too many times to count.',
            'Medal of Honor': 'Valor above and beyond—an act that rewrites what “duty” means. The highest recognition for the darkest moment.',
            'Medal of Honor + One Oak Leaf Cluster': 'A second Medal of Honor is nearly unimaginable. It means you faced that line twice and crossed it.',
            'Purple Heart': 'You were hit by the enemy and paid in blood. The medal is quiet; the memory isn’t.',
            'Purple Heart + One Oak Leaf Cluster': 'Wounded again. You carry the damage and keep flying anyway.',
            'Purple Heart + Two Oak Leaf Clusters': 'Three wounds and still operational. The body keeps score even if the medal does not.'
        }
    },
    soviet: {
        ranks: {
            Sergeant: 'A frontline pilot with little margin and no illusions. You fly, you fight, you hope the engine holds.',
            'Senior Sergeant': 'You’ve survived enough to teach others how to. The new men watch your hands more than they hear your words.',
            'Junior Lieutenant': 'You’ve got a commission and a rifleman’s war in the air. Lead tight, strike fast, and don’t linger.',
            Lieutenant: 'You’re trusted to bring a pair home and still finish the job. The sky is crowded and mercy is scarce.',
            'Senior Lieutenant': 'You lead sorties into flak and weather like it’s routine. Your squadron runs on discipline and stubbornness.',
            Captain: 'You command and you still fly hard. The best orders are the ones you’ve tested in your own cockpit.',
            Major: 'You fly less, plan more, and sleep even less. When you do climb out, it’s for missions that must succeed.',
            'Sub-Colonel': 'Command pulls you away from the line, but you return when it matters. A rare sortie, a familiar smell of fuel and frost.',
            Colonel: 'You carry an air regiment’s fate in your notes and your voice. Flying is occasional; responsibility never is.',
            'Major General': 'You command formations and watch losses like a ledger of steel. If you fly, it’s exceptional—and never for sport.',
            'Lieutenant General': 'The front is vast, the demands endless. You’re a pilot by training, a commander by necessity.'
        },
        awards: {
            'Aviation Badge': 'You’re marked as aircrew now. The front will use you until the machine or the man breaks.',
            'Medal "For Battle Merit"': 'Solid service under fire. You did the work, took the risk, and brought results back.',
            'Medal for Courage': 'Personal bravery, close and undeniable. You held your nerve when the sky turned violent.',
            'Order of the Red Star': 'A serious combat award for real results. Not for talk—only for what you did at the front.',
            'Order of the Red Star (2nd awarding)': 'They’re recognizing you again. Same war, higher stakes, more proof you’re still delivering.',
            'Order of the Red Star (3rd awarding)': 'A third time is no accident. You’ve made a career out of surviving—and winning.',
            'Order of the Patriotic War 2nd Class': 'Combat merit that mattered to the Motherland. Earned in the grind, not the parade.',
            'Order of the Patriotic War 1st Class': 'A higher grade for standout performance in battle. Your name is being noticed beyond the regiment.',
            'Order of Alexander Nevsky': 'For leaders who win while outnumbered and under fire. A commander’s award, earned in the air.',
            'Order of Suvorov 3rd Class': 'Recognition for effective command and successful operations. You made plans work in a world that hates plans.',
            'Order of the Red Banner': 'A major mark of courage and achievement. The kind of ribbon earned only at the sharp end.',
            'Order of the Red Banner (2nd awarding)': 'They say you’ve done it again. Results repeated, losses endured, mission accomplished.',
            'Order of the Red Banner (3rd awarding)': 'A third award speaks of a brutal record. You’ve fought hard, long, and successfully.',
            'Hero of the Soviet Union': 'The highest title—heroism carved into the record. It doesn’t make the next sortie easier.',
            'Hero of the Soviet Union (2nd awarding)': 'A rare second title for extraordinary repeat heroism. Even comrades look twice when your name is read.',
            'Hero of the Soviet Union (3rd awarding)': 'Almost legendary. You’re a symbol now—and symbols are still sent into combat.',
            'Order of Lenin': 'One of the highest honors, often paired with major heroism. A decoration that carries political weight and frontline respect.',
            'Order of Lenin (2nd awarding)': 'They’re elevating you again for continued distinction. Your war record is becoming impossible to ignore.',
            'Order of Lenin (3rd awarding)': 'A third time is exceptional. It marks a sustained level of achievement few ever reach.',
            '5 Combat Sorties Bonus (1500 rubles)': 'A small reward for staying on the roster. The money is nice; the survival is the real prize.',
            '15 Combat Sorties Bonus (2000 rubles)': 'You’ve kept flying while others vanish. The state notices endurance.',
            '25 Combat Sorties Bonus (3000 rubles)': 'A real milestone at the front. You’ve stacked sorties like cordwood and kept moving.',
            '40 Combat Sorties Bonus (5000 rubles)': 'Heavy operational time—hard-earned and rarely clean. You’ve stayed in the fight long enough to be feared.',
            'Red Wound Stripe': 'You were wounded and still came back. The stripe is simple; the story isn’t.',
            'Yellow Wound Stripe': 'Another mark of injury carried forward. You flew hurt, landed alive, and returned to duty.'
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
            
            // Render components
            this.renderHeader(campaign);
            this.renderEvents(campaign.events);
            this.renderDebriefings(campaign.debriefings_html);
            this.renderSummary(campaign.summary);
            this.applyBackgroundForCountry(campaign.country);
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

    applyBackgroundForCountry(country) {
        if (!this.elements.page || this.elements.page.offsetParent === null) {
            return;
        }
        const normalized = (country || '').trim().toLowerCase();
        const background = this.backgroundByCountry[normalized];
        if (background && background !== this.currentBackground) {
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
        } catch (error) {
            console.error('Failed to load personal data:', error);
            this.showPersonalDataStatus('Unable to load personal data.');
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
            this.elements.eventsList.innerHTML = '<p class="empty-message">No events recorded</p>';
            return;
        }
        
        // Separate promotions and awards
        const promotions = events.filter(e => e.type === 'promotion');
        const awards = events.filter(e => e.type === 'award');
        
        // Render promotions
        if (promotions.length > 0) {
            const header = document.createElement('h4');
            header.textContent = 'Promotions';
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
            header.textContent = 'Awards';
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

        const typeLabel = event.type === 'promotion' ? 'Promotion' : 'Award';
        const mainText = event.type === 'promotion' ? event.rank : event.name;
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
            return descriptions.ranks[rankName] || '';
        }
        if (event.type === 'award') {
            return getAwardDescription(descriptions.awards, event.name);
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
                imageAlt: title || mainText || 'Event preview',
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
            this.elements.debriefingsContainer.innerHTML = '<p class="empty-message">No debriefings available</p>';
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
            this.elements.summaryContent.innerHTML = '<p class="empty-message">No summary available</p>';
            return;
        }
        
        const sections = [];

        if (summary.combat_results) {
            sections.push(this.createSummarySection(
                'Combat Results',
                this.renderCombatResults(summary.combat_results)
            ));
        }

        if (summary.missions_stats) {
            sections.push(this.createSummarySection(
                'Missions Flown',
                this.renderMissionsStats(summary.missions_stats)
            ));
        }

        if (summary.aircraft_usage && Object.keys(summary.aircraft_usage).length > 0) {
            sections.push(this.createSummarySection(
                'Aircraft Flown',
                this.renderAircraftUsage(summary.aircraft_usage)
            ));
        }

        if (summary.career_progression) {
            sections.push(this.createSummarySection(
                'Career Progression',
                this.renderCareerProgression(summary.career_progression)
            ));
        }

        if (summary.timeline && summary.timeline.first_mission_date) {
            sections.push(this.createSummarySection(
                'Campaign Timeline',
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
        summaryStats.appendChild(this.createInlineStat('Overall Score', results.total_score ?? 0));
        summaryStats.appendChild(this.createInlineStat('Total Kills', results.total_kills ?? 0));
        container.appendChild(summaryStats);

        const categories = [
            { key: 'Aircraft', icon: 'icon_aircraft.png' },
            { key: 'Vehicles', icon: 'icon_vehicles.png' },
            { key: 'Railroad', icon: 'icon_railroad.png' },
            { key: 'Armaments', icon: 'icon_armaments.png' },
            { key: 'Buildings', icon: 'icon_buildings.png' },
            { key: 'Marine', icon: 'icon_marine.png' }
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
            label.textContent = category.key;
            cell.appendChild(label);

            iconRow.appendChild(cell);
        });

        container.appendChild(iconRow);

        const subcategoryColumns = document.createElement('div');
        subcategoryColumns.className = 'combat-subcategory-columns';

        const subcategoryMap = {
            'Aircraft': ['Light', 'Medium', 'Heavy', 'Parked', 'Balloons'],
            'Vehicles': ['Transport', 'Armored (Light)', 'Armored (Medium)', 'Armored (Heavy)'],
            'Railroad': ['Locomotives', 'Railroad Cars', 'Station Facilities'],
            'Armaments': ['Machine Guns', 'Cannons', 'AAA Guns', 'Rocket Launchers', 'Searchlights', 'Radars'],
            'Buildings': ['Residential Buildings', 'Facilities', 'Bridges'],
            'Marine': ['Light', 'Cargo', 'Submarines', 'Destroyers']
        };

        categories.forEach(category => {
            const column = document.createElement('div');
            column.className = 'combat-subcategory-column';

            (subcategoryMap[category.key] || []).forEach(subcat => {
                const row = document.createElement('div');
                row.className = 'combat-subcategory-row';

                const label = document.createElement('span');
                label.className = 'combat-subcategory-label';
                const formattedLabel = subcat.startsWith('Armored ')
                    ? subcat.replace('Armored ', 'Armored\n')
                    : subcat;
                label.textContent = formattedLabel;
                row.appendChild(label);

                const value = document.createElement('span');
                value.className = 'combat-subcategory-value';
                value.textContent = (byCategory[category.key] || {})[subcat] || 0;
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

        container.appendChild(this.createStat('Missions Completed', totalMissions));
        container.appendChild(this.createStat('Flight Time', totalFlightTime));
        container.appendChild(this.createStat('Average Flight Time', averageDuration));

        const landingStats = Array.isArray(stats.landings) ? stats.landings : [];
        const filteredLandings = landingStats.filter(
            landing => landing && landing.label !== undefined && Number(landing.value || 0) > 0
        );

        if (filteredLandings.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-message';
            empty.textContent = 'No status data available';
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
        
        container.appendChild(this.createStat('Starting Rank', progression.starting_rank));
        container.appendChild(this.createStat('Final Rank', progression.final_rank));
        container.appendChild(this.createStat('Promotions', progression.promotions_count));
        container.appendChild(this.createStat('Awards', progression.awards_count));
        
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
            container.appendChild(this.createStat('First Mission', timeline.first_mission_date));
        }
        
        if (timeline.last_mission_date) {
            container.appendChild(this.createStat('Last Mission', timeline.last_mission_date));
        }
        
        if (timeline.duration_days !== null && timeline.duration_days !== undefined) {
            container.appendChild(this.createStat('Duration', `${timeline.duration_days} days`));
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
        link.textContent = '📄 Download PDF Report';
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
