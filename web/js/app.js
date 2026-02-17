/**
 * Main application logic for AI Debate
 */

class DebateApp {
    constructor() {
        this.sessionId = null;
        this.isDebating = false;
        this.turnCount = 0;
        this.currentSpeaker = null;
        this.mouthAnimationInterval = null;
        this.autoPlay = true; // 自動進行フラグ

        // DOM elements
        this.elements = {
            setupSection: document.getElementById('setup-section'),
            debateSection: document.getElementById('debate-section'),
            apiKeyInput: document.getElementById('api-key-input'),
            toggleApiKeyBtn: document.getElementById('toggle-api-key'),
            topicInput: document.getElementById('topic-input'),
            topicText: document.getElementById('topic-text'),
            startBtn: document.getElementById('start-btn'),
            stopBtn: document.getElementById('stop-btn'),
            judgeBtn: document.getElementById('judge-btn'),
            resetBtn: document.getElementById('reset-btn'),
            debateLog: document.getElementById('debate-log'),
            statusIndicator: document.getElementById('status-indicator'),
            statusText: document.querySelector('.status-text'),
            proName: document.getElementById('pro-name'),
            conName: document.getElementById('con-name'),
            proAvatar: document.getElementById('pro-avatar'),
            conAvatar: document.getElementById('con-avatar'),
            // Speech settings
            speechEnabled: document.getElementById('speech-enabled'),
            speechRate: document.getElementById('speech-rate'),
            speechRateValue: document.getElementById('speech-rate-value'),
            voiceSelect: document.getElementById('voice-select'),
            stopSpeechBtn: document.getElementById('stop-speech-btn'),
        };

        this._bindEvents();
        this._initSpeechSettings();
        this._initApiKey();
    }

    /**
     * Bind event listeners
     * @private
     */
    _bindEvents() {
        this.elements.startBtn.addEventListener('click', () => this.startDebate());
        this.elements.stopBtn.addEventListener('click', () => this.togglePause());
        this.elements.judgeBtn.addEventListener('click', () => this.judgeDebate());
        this.elements.resetBtn.addEventListener('click', () => this.reset());
        this.elements.stopSpeechBtn.addEventListener('click', () => speechManager.stop());

        // API Key toggle visibility
        this.elements.toggleApiKeyBtn.addEventListener('click', () => {
            const input = this.elements.apiKeyInput;
            if (input.type === 'password') {
                input.type = 'text';
                this.elements.toggleApiKeyBtn.textContent = '🙈';
            } else {
                input.type = 'password';
                this.elements.toggleApiKeyBtn.textContent = '👁';
            }
        });

        // Save API key on change
        this.elements.apiKeyInput.addEventListener('change', () => {
            this._saveApiKey();
        });

        // Speech settings
        this.elements.speechEnabled.addEventListener('change', (e) => {
            speechManager.setEnabled(e.target.checked);
        });

        this.elements.speechRate.addEventListener('input', (e) => {
            const rate = parseFloat(e.target.value);
            speechManager.setRate(rate);
            this.elements.speechRateValue.textContent = rate.toFixed(1);
        });

        this.elements.voiceSelect.addEventListener('change', (e) => {
            speechManager.setVoiceByName(e.target.value);
        });

        // Enter key to start
        this.elements.topicInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.startDebate();
            }
        });

        // Speech callbacks
        speechManager.onSpeakStart = () => this._updateSpeakingState(true);
        speechManager.onSpeakEnd = () => this._updateSpeakingState(false);
    }

    /**
     * Initialize speech settings UI
     * @private
     */
    _initSpeechSettings() {
        // Populate voice select after a short delay (voices may load async)
        setTimeout(() => {
            this._populateVoiceSelect();
        }, 100);

        // Also listen for voices changed
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = () => this._populateVoiceSelect();
        }
    }

    /**
     * Initialize API key from localStorage
     * @private
     */
    _initApiKey() {
        const savedKey = localStorage.getItem('groq_api_key');
        if (savedKey) {
            this.elements.apiKeyInput.value = savedKey;
            debateAPI.setApiKey(savedKey);
        }
    }

    /**
     * Save API key to localStorage
     * @private
     */
    _saveApiKey() {
        const apiKey = this.elements.apiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('groq_api_key', apiKey);
            debateAPI.setApiKey(apiKey);
        } else {
            localStorage.removeItem('groq_api_key');
            debateAPI.setApiKey('');
        }
    }

    /**
     * Populate voice select dropdown
     * @private
     */
    _populateVoiceSelect() {
        const voices = speechManager.getVoices();
        const japaneseVoices = speechManager.getJapaneseVoices();

        this.elements.voiceSelect.innerHTML = '<option value="">デフォルト</option>';

        // Add Japanese voices first
        if (japaneseVoices.length > 0) {
            const group = document.createElement('optgroup');
            group.label = '日本語';
            japaneseVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = voice.name;
                group.appendChild(option);
            });
            this.elements.voiceSelect.appendChild(group);
        }

        // Add other voices
        const otherVoices = voices.filter(v => !v.lang.includes('ja') && !v.lang.includes('JP'));
        if (otherVoices.length > 0) {
            const group = document.createElement('optgroup');
            group.label = 'その他';
            otherVoices.slice(0, 10).forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = `${voice.name} (${voice.lang})`;
                group.appendChild(option);
            });
            this.elements.voiceSelect.appendChild(group);
        }
    }

    /**
     * Update speaking state UI (mouth animation)
     * @private
     * @param {boolean} speaking - Whether currently speaking
     */
    _updateSpeakingState(speaking) {
        const proImg = document.getElementById('pro-img');
        const conImg = document.getElementById('con-img');

        if (speaking && this.currentSpeaker) {
            // Start mouth animation
            this._startMouthAnimation();
        } else {
            // Stop mouth animation, show closed mouth
            this._stopMouthAnimation();
            if (proImg) proImg.src = '/assets/pro_closed.png';
            if (conImg) conImg.src = '/assets/con_closed.png';
        }
    }

    /**
     * Start mouth animation loop
     * @private
     */
    _startMouthAnimation() {
        // 既存のアニメーションを停止
        this._stopMouthAnimation();

        const proImg = document.getElementById('pro-img');
        const conImg = document.getElementById('con-img');
        let mouthOpen = false;

        // 話していない方は常に閉じた口
        if (this.currentSpeaker === 'pro' && conImg) {
            conImg.src = '/assets/con_closed.png';
        } else if (this.currentSpeaker === 'con' && proImg) {
            proImg.src = '/assets/pro_closed.png';
        }

        this.mouthAnimationInterval = setInterval(() => {
            mouthOpen = !mouthOpen;
            if (this.currentSpeaker === 'pro' && proImg) {
                proImg.src = mouthOpen ? '/assets/pro_open.png' : '/assets/pro_closed.png';
            } else if (this.currentSpeaker === 'con' && conImg) {
                conImg.src = mouthOpen ? '/assets/con_open.png' : '/assets/con_closed.png';
            }
        }, 120); // 口パクの速度（少し速く）
    }

    /**
     * Stop mouth animation
     * @private
     */
    _stopMouthAnimation() {
        if (this.mouthAnimationInterval) {
            clearInterval(this.mouthAnimationInterval);
            this.mouthAnimationInterval = null;
        }
    }

    /**
     * Show/hide status indicator
     * @private
     * @param {boolean} show - Whether to show loading
     * @param {string} text - Status text
     */
    _setLoading(show, text = '考え中...') {
        if (show) {
            this.elements.statusText.textContent = text;
            this.elements.statusIndicator.classList.remove('hidden');
        } else {
            this.elements.statusIndicator.classList.add('hidden');
        }
    }

    /**
     * Add a log entry
     * @private
     * @param {string} type - Entry type (pro, con, judge, system)
     * @param {string} speaker - Speaker name (optional)
     * @param {string} text - Log text
     */
    _addLogEntry(type, speaker, text) {
        // Remove placeholder if exists
        const placeholder = this.elements.debateLog.querySelector('.log-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;

        if (speaker) {
            const speakerEl = document.createElement('div');
            speakerEl.className = 'log-speaker';
            speakerEl.textContent = speaker;
            entry.appendChild(speakerEl);
        }

        const textEl = document.createElement('div');
        textEl.className = 'log-text';
        textEl.textContent = text;
        entry.appendChild(textEl);

        this.elements.debateLog.appendChild(entry);
        this.elements.debateLog.scrollTop = this.elements.debateLog.scrollHeight;
    }

    /**
     * Set active character
     * @private
     * @param {string|null} role - Active role (pro, con, or null)
     */
    _setActiveCharacter(role) {
        this.currentSpeaker = role;

        const proChar = this.elements.proAvatar.closest('.character');
        const conChar = this.elements.conAvatar.closest('.character');

        proChar.classList.toggle('active', role === 'pro');
        conChar.classList.toggle('active', role === 'con');
    }

    /**
     * Show error message
     * @private
     * @param {string} message - Error message
     */
    _showError(message) {
        this._addLogEntry('system', null, `エラー: ${message}`);
    }

    /**
     * Start a new debate
     */
    async startDebate() {
        // Validate API key
        const apiKey = this.elements.apiKeyInput.value.trim();
        if (!apiKey) {
            alert('Groq APIキーを入力してください');
            this.elements.apiKeyInput.focus();
            return;
        }
        this._saveApiKey();

        const topic = this.elements.topicInput.value.trim();
        if (!topic) {
            alert('議題を入力してください');
            return;
        }

        // iOS用：ユーザー操作時に音声を有効化
        speechManager.unlock();

        this._setLoading(true, 'ディベートを開始しています...');

        try {
            const response = await debateAPI.startDebate(topic);

            this.sessionId = response.session_id;
            this.isDebating = true;
            this.turnCount = 0;

            // Update UI
            this.elements.setupSection.classList.add('hidden');
            this.elements.debateSection.classList.remove('hidden');
            this.elements.topicText.textContent = `議題: 「${response.topic}」`;
            this.elements.proName.textContent = response.pro.name;
            this.elements.conName.textContent = response.con.name;

            // Clear log
            this.elements.debateLog.innerHTML = '<div class="log-placeholder">ディベートが始まります...</div>';

            // Enable controls
            this.autoPlay = true;
            this.elements.stopBtn.disabled = false;
            this.elements.stopBtn.textContent = '⏸ 一時停止';
            this.elements.judgeBtn.disabled = true;

            // Auto-start debate loop
            this._runDebateLoop();

        } catch (error) {
            this._showError(error.message);
        } finally {
            this._setLoading(false);
        }
    }

    /**
     * Toggle pause/resume
     */
    togglePause() {
        this.autoPlay = !this.autoPlay;
        if (this.autoPlay) {
            this.elements.stopBtn.textContent = '⏸ 一時停止';
            // Resume debate loop
            this._runDebateLoop();
        } else {
            this.elements.stopBtn.textContent = '▶ 再開';
            speechManager.stop();
        }
    }

    /**
     * Run debate loop (auto-progress)
     */
    async _runDebateLoop() {
        while (this.isDebating && this.autoPlay) {
            const success = await this._executeTurn();
            if (!success) break;

            // Small delay between turns
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    /**
     * Execute a single turn
     * @returns {boolean} Whether the turn was successful
     */
    async _executeTurn() {
        if (!this.sessionId || !this.isDebating) return false;

        this._setLoading(true);

        try {
            const response = await debateAPI.debateTurn(this.sessionId);

            this.turnCount = response.turn_number;

            // Update UI
            this._setActiveCharacter(response.speaker.role);
            this._addLogEntry(
                response.speaker.role,
                response.speaker.name,
                response.text
            );

            // Speak the text
            await speechManager.speak(response.text);

            // Enable judge after 2+ turns
            if (this.turnCount >= 2) {
                this.elements.judgeBtn.disabled = false;
            }

            this._setActiveCharacter(null);
            return true;

        } catch (error) {
            this._showError(error.message);
            this.autoPlay = false;
            return false;
        } finally {
            this._setLoading(false);
        }
    }

    /**
     * Get judge evaluation
     */
    async judgeDebate() {
        if (!this.sessionId) return;

        this.isDebating = false;
        this.autoPlay = false;
        this.elements.stopBtn.disabled = true;
        this.elements.judgeBtn.disabled = true;
        this._setLoading(true, 'ジャッジ中...');

        try {
            const response = await debateAPI.judgeDebate(this.sessionId);

            // Add system message
            this._addLogEntry('system', null, '⚖️ ジャッジタイム！');

            // Add judge result
            this._addLogEntry('judge', '👩‍⚖️ ジャッジ', response.verdict.text);

            // Speak the verdict
            await speechManager.speak(response.verdict.text);

            this._setActiveCharacter(null);

        } catch (error) {
            this._showError(error.message);
            // Re-enable controls on error
            this.isDebating = true;
            this.autoPlay = true;
            this.elements.stopBtn.disabled = false;
            this.elements.judgeBtn.disabled = false;
        } finally {
            this._setLoading(false);
        }
    }

    /**
     * Reset to initial state
     */
    reset() {
        speechManager.stop();
        this._stopMouthAnimation();

        this.sessionId = null;
        this.isDebating = false;
        this.autoPlay = false;
        this.turnCount = 0;
        this.currentSpeaker = null;

        // Reset UI
        this.elements.setupSection.classList.remove('hidden');
        this.elements.debateSection.classList.add('hidden');
        this.elements.debateLog.innerHTML = '<div class="log-placeholder">ディベートが始まると、ここに会話が表示されます...</div>';
        this._setActiveCharacter(null);

        // Reset images to closed mouth
        const proImg = document.getElementById('pro-img');
        const conImg = document.getElementById('con-img');
        if (proImg) proImg.src = '/assets/pro_closed.png';
        if (conImg) conImg.src = '/assets/con_closed.png';
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DebateApp();
});
