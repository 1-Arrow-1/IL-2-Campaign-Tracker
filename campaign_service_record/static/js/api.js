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
    async post(endpoint, data = {}) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API POST ${endpoint} failed:`, error);
            throw error;
        }
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
