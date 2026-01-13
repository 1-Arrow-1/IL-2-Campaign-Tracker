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
            header.style.color = '#27ae60';
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
            header.style.color = '#f39c12';
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
        
        item.innerHTML = `
            <div class="event-type">${typeLabel}</div>
            <div class="event-name">${this.escapeHTML(mainText)}</div>
            <div class="event-date">${this.escapeHTML(dateText)}</div>
            ${reasonText ? `<div class="event-reason">${this.escapeHTML(reasonText)}</div>` : ''}
        `;
        
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
        
        // Direct HTML injection (safe - comes from Campaign Tracker)
        this.elements.debriefingsContainer.innerHTML = html;
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
        
        // Combat Results
        if (summary.combat_results) {
            const section = this.createSummarySection('Combat Results', 
                this.renderCombatResults(summary.combat_results)
            );
            this.elements.summaryContent.appendChild(section);
        }
        
        // Missions Stats
        if (summary.missions_stats) {
            const section = this.createSummarySection('Missions Flown',
                this.renderMissionsStats(summary.missions_stats)
            );
            this.elements.summaryContent.appendChild(section);
        }
        
        // Aircraft Usage
        if (summary.aircraft_usage && Object.keys(summary.aircraft_usage).length > 0) {
            const section = this.createSummarySection('Aircraft Flown',
                this.renderAircraftUsage(summary.aircraft_usage)
            );
            this.elements.summaryContent.appendChild(section);
        }
        
        // Career Progression
        if (summary.career_progression) {
            const section = this.createSummarySection('Career Progression',
                this.renderCareerProgression(summary.career_progression)
            );
            this.elements.summaryContent.appendChild(section);
        }
        
        // Timeline
        if (summary.timeline && summary.timeline.first_mission_date) {
            const section = this.createSummarySection('Campaign Timeline',
                this.renderTimeline(summary.timeline)
            );
            this.elements.summaryContent.appendChild(section);
        }
    },
    
    /**
     * Create summary section wrapper
     */
    createSummarySection(title, content) {
        const section = document.createElement('div');
        section.className = 'summary-section-inner';
        
        const header = document.createElement('h4');
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
        
        // Total score
        if (results.total_score !== undefined) {
            const stat = this.createStat('Total Score', results.total_score);
            container.appendChild(stat);
        }
        
        // Air kills
        const airKills = results['Air'] || results['air_total'] || 0;
        if (airKills > 0) {
            const stat = this.createStat('Air Victories', airKills);
            container.appendChild(stat);
        }
        
        // Ground kills
        const groundKills = results['Ground'] || results['ground_total'] || 0;
        if (groundKills > 0) {
            const stat = this.createStat('Ground Victories', groundKills);
            container.appendChild(stat);
        }
        
        return container;
    },
    
    /**
     * Render missions stats
     */
    renderMissionsStats(stats) {
        const container = document.createElement('div');
        
        container.appendChild(this.createStat('Total Missions', stats.total_missions || 0));
        
        if (stats.successful_missions !== undefined) {
            container.appendChild(this.createStat('Successful', stats.successful_missions));
        }
        
        if (stats.success_rate !== undefined) {
            container.appendChild(this.createStat('Success Rate', `${stats.success_rate}%`));
        }
        
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
