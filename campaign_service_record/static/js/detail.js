/**
 * Detail Page Controller
 * 
 * Handles:
 * - Loading campaign details
 * - Rendering events, debriefings, summary
 * - PDF download button
 */

const DetailPage = {
    /**
     * DOM elements
     */
    elements: {
        page: null,
        title: null,
        country: null,
        missions: null,
        eventsList: null,
        debriefingsContainer: null,
        summaryContent: null
    },
    
    /**
     * Current campaign data
     */
    currentCampaign: null,
    
    /**
     * Initialize detail page
     */
    init() {
        this.cacheElements();
    },
    
    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements.page = document.getElementById('detail-page');
        this.elements.title = document.getElementById('campaign-title');
        this.elements.country = document.getElementById('campaign-country');
        this.elements.missions = document.getElementById('campaign-missions');
        this.elements.eventsList = document.getElementById('events-list');
        this.elements.debriefingsContainer = document.getElementById('debriefings-container');
        this.elements.summaryContent = document.getElementById('summary-content');
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

        if (event.image_url) {
            const img = document.createElement('img');
            img.className = 'event-image';
            img.alt = `${mainText || 'Event'} icon`;
            img.src = event.image_url;
            img.onload = () => this.scaleEventImage(img);
            img.onerror = () => img.remove();
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

        return item;
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
                label.textContent = subcat;
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
        const scale = 0.35;
        img.style.width = `${Math.round(img.naturalWidth * scale)}px`;
        img.style.height = `${Math.round(img.naturalHeight * scale)}px`;
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
