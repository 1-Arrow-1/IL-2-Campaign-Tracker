/**
 * API Client for Campaign Service Record
 * 
 * Handles all communication with Flask backend.
 * Provides clean, promise-based interface.
 */

const API = {
    /**
     * Base URL for API requests
     */
    baseURL: '/api',
    
    /**
     * Ping interval for keep-alive (milliseconds)
     */
    pingInterval: 30000, // 30 seconds
    
    /**
     * Ping timer ID
     */
    _pingTimer: null,
    
    /**
     * Generic GET request
     */
    async get(endpoint) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API GET ${endpoint} failed:`, error);
            throw error;
        }
    },
    
    /**
     * Generic POST request
     */
    async post(endpoint, data = {}, options = {}) {
        const timeoutMs = Number(options.timeoutMs || 0);
        const controller = timeoutMs > 0 ? new AbortController() : null;
        let timeoutId = null;
        try {
            if (controller) {
                timeoutId = setTimeout(() => controller.abort(), timeoutMs);
            }
            const fetchPromise = fetch(`${this.baseURL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data),
                signal: controller ? controller.signal : undefined
            });
            const response = timeoutMs > 0
                ? await Promise.race([
                    fetchPromise,
                    new Promise((_, reject) => {
                        setTimeout(() => reject(new Error('Story generation timed out. Please retry, or switch to a faster model/provider.')), timeoutMs + 1000);
                    })
                ])
                : await fetchPromise;
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            if (error && error.name === 'AbortError') {
                throw new Error('Story generation timed out. Please retry, or switch to a faster model/provider.');
            }
            console.error(`API POST ${endpoint} failed:`, error);
            throw error;
        } finally {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        }
    },
    
    /**
     * Generic DELETE request with JSON body
     */
    async delete(endpoint, data = {}) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API DELETE ${endpoint} failed:`, error);
            throw error;
        }
    },

    /**
     * Get active modes (campaign / career)
     */
    async getMode() {
        return this.get('/mode');
    },

    /**
     * Get list of all campaigns
     */
    async getCampaigns() {
        return this.get('/campaigns');
    },

    /**
     * Get detailed campaign data
     */
    async getCampaignDetail(campaignName) {
        return this.get(`/campaign/${encodeURIComponent(campaignName)}`);
    },

    /**
     * Get list of all career entries (virtual pilot careers)
     */
    async getCareers() {
        return this.get('/careers');
    },

    /**
     * Get detailed career data by root career id
     */
    async getCareerDetail(rootCareerId) {
        return this.get(`/career/${encodeURIComponent(rootCareerId)}`);
    },

    /**
     * Get stored personal data for a career
     */
    async getCareerPersonalData(rootCareerId) {
        return this.get(`/career/${encodeURIComponent(rootCareerId)}/personal_data`);
    },

    /**
     * Save personal data for a career
     */
    async saveCareerPersonalData(rootCareerId, data) {
        return this.post(`/career/${encodeURIComponent(rootCareerId)}/personal_data`, data);
    },

    /**
     * Get AI story status and cached chapters for an entry.
     */
    async getStories(source, entryId) {
        return this.get(`/stories/${encodeURIComponent(source)}/${encodeURIComponent(entryId)}`);
    },

    /**
     * Delete a single story chapter by mission_id.
     */
    async deleteStoryChapter(source, entryId, missionId) {
        return this.delete(
            `/stories/${encodeURIComponent(source)}/${encodeURIComponent(entryId)}/chapter`,
            { mission_id: missionId }
        );
    },

    /**
     * Delete all chapters with an empty/missing mission_id.
     */
    async cleanupOrphanedChapters(source, entryId) {
        return this.post(
            `/stories/${encodeURIComponent(source)}/${encodeURIComponent(entryId)}/cleanup_orphans`,
            {}
        );
    },

    /**
     * Generate missing AI story chapters for an entry.
     */
    async generateStories(source, entryId, data = {}) {
        return this.post(
            `/stories/${encodeURIComponent(source)}/${encodeURIComponent(entryId)}/generate`,
            data,
            { timeoutMs: 240000 }
        );
    },
    
    /**
     * Generate a career PDF report (POST, triggers server-side PDF creation)
     */
    async generateCareerPdf(careerId) {
        return this.post(`/career/${encodeURIComponent(careerId)}/pdf`);
    },

    /**
     * Download URL for a generated career PDF
     */
    careerPdfDownloadUrl(careerId, filename) {
        return `${this.baseURL}/career/${encodeURIComponent(careerId)}/pdf/${encodeURIComponent(filename)}`;
    },

    /**
     * Check if PDF report exists for campaign
     */
    async checkPDF(campaignName) {
        try {
            return await this.get(`/pdf/${encodeURIComponent(campaignName)}`);
        } catch (error) {
            // 404 is expected if PDF doesn't exist
            return null;
        }
    },

    /**
     * Get pilot photo path
     */
    async getPilotPhoto(desc) {
        const query = desc ? `?desc=${encodeURIComponent(desc)}` : '';
        return this.get(`/pilot_photo${query}`);
    },

    /**
     * Save pilot photo (multipart form)
     */
    async savePilotPhoto(desc, imageData, pilotName) {
        const formData = new FormData();
        formData.append('desc', desc);
        formData.append('img_data', imageData);
        if (pilotName !== undefined) {
            formData.append('pilot_name', pilotName);
        }

        const response = await fetch(`${this.baseURL}/save_pilot_photo`, {
            method: 'POST',
            body: formData
        });

        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            console.error('Failed to parse pilot photo response:', error);
        }

        if (!response.ok) {
            console.error('Pilot photo save failed:', response.status, payload);
            throw new Error(payload?.error || `HTTP ${response.status}`);
        }

        return payload;
    },

    /**
     * Get campaign personal data
     */
    async getCampaignPersonalData(campaignName) {
        return this.get(`/campaign/${encodeURIComponent(campaignName)}/personal_data`);
    },

    /**
     * Save campaign personal data
     */
    async saveCampaignPersonalData(campaignName, data) {
        return this.post(`/campaign/${encodeURIComponent(campaignName)}/personal_data`, data);
    },
    
    /**
     * Get current locale setting
     */
    async getLocale() {
        return this.get('/locale');
    },

    /**
     * Get supported locales list
     */
    async getLocales() {
        return this.get('/locales');
    },

    /**
     * Start a background career debrief parse job.
     * @param {number|string} careerId - root_career_id
     * @returns {{ job_id: string }}
     */
    async startCareerParse(careerId) {
        return this.post(`/jobs/start_career_parse?career_id=${careerId}`);
    },

    /**
     * Poll a background job's status.
     * @param {string} jobId
     * @returns {{ id, type, status, message, progress_current, progress_total, error }}
     */
    async getJobStatus(jobId) {
        return this.get(`/jobs/status/${jobId}`);
    },
    
    /**
     * Health check
     */
    async health() {
        return this.get('/health');
    },
    
    /**
     * Send keep-alive ping
     */
    async ping() {
        try {
            await this.post('/ping');
        } catch (error) {
            console.warn('Ping failed:', error);
        }
    },
    
    /**
     * Start keep-alive pinging
     */
    startPinging() {
        if (this._pingTimer) {
            return; // Already pinging
        }
        
        console.log('Starting keep-alive pinging');
        this._pingTimer = setInterval(() => {
            this.ping();
        }, this.pingInterval);
        
        // Send immediate ping
        this.ping();
    },
    
    /**
     * Stop keep-alive pinging
     */
    stopPinging() {
        if (this._pingTimer) {
            console.log('Stopping keep-alive pinging');
            clearInterval(this._pingTimer);
            this._pingTimer = null;
        }
    }
};

// Auto-start pinging when page loads
document.addEventListener('DOMContentLoaded', () => {
    API.startPinging();
});

// Stop pinging when page unloads
window.addEventListener('beforeunload', () => {
    API.stopPinging();
});
