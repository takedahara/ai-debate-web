/**
 * API Client for AI Debate
 */

class DebateAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
        this.apiKey = '';
    }

    /**
     * Set the API key
     * @param {string} apiKey - Groq API key
     */
    setApiKey(apiKey) {
        this.apiKey = apiKey;
    }

    /**
     * Make an API request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
        };

        // Add API key header if set
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        const defaultOptions = {
            headers,
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, mergedOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const error = new Error(errorData.detail || `HTTP ${response.status}`);
                error.status = response.status;
                error.data = errorData;
                throw error;
            }

            return await response.json();
        } catch (error) {
            if (error.status) {
                throw error;
            }
            // Network error
            const networkError = new Error('ネットワークエラーが発生しました');
            networkError.status = 0;
            throw networkError;
        }
    }

    /**
     * Health check
     * @returns {Promise<Object>} Health status
     */
    async healthCheck() {
        return this.request('/health');
    }

    /**
     * Start a new debate
     * @param {string} topic - Debate topic
     * @param {Object} proCharacter - Optional pro character config
     * @param {Object} conCharacter - Optional con character config
     * @returns {Promise<Object>} Session info
     */
    async startDebate(topic, proCharacter = null, conCharacter = null) {
        const body = { topic };
        if (proCharacter) body.pro_character = proCharacter;
        if (conCharacter) body.con_character = conCharacter;

        return this.request('/debate/start', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    }

    /**
     * Execute a debate turn
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Turn result
     */
    async debateTurn(sessionId) {
        return this.request('/debate/turn', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId }),
        });
    }

    /**
     * Get judge evaluation
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Judge result
     */
    async judgeDebate(sessionId) {
        return this.request('/debate/judge', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId }),
        });
    }
}

// Export singleton instance
const debateAPI = new DebateAPI();
