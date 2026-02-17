/**
 * Web Speech API wrapper for AI Debate
 */

class SpeechManager {
    constructor() {
        this.synthesis = window.speechSynthesis;
        this.enabled = true;
        this.rate = 1.2;
        this.pitch = 1.0;
        this.voice = null;
        this.voices = [];
        this.currentUtterance = null;
        this.onSpeakStart = null;
        this.onSpeakEnd = null;
        this.isUnlocked = false; // iOS用フラグ

        // Load voices
        this._loadVoices();

        // Chrome requires this event listener
        if (this.synthesis.onvoiceschanged !== undefined) {
            this.synthesis.onvoiceschanged = () => this._loadVoices();
        }
    }

    /**
     * Unlock audio for iOS (must be called from user interaction)
     */
    unlock() {
        if (this.isUnlocked) return;

        // iOS requires a user gesture to enable audio
        const utterance = new SpeechSynthesisUtterance('');
        utterance.volume = 0;
        this.synthesis.speak(utterance);
        this.isUnlocked = true;
    }

    /**
     * Load available voices
     * @private
     */
    _loadVoices() {
        this.voices = this.synthesis.getVoices();

        // Try to find Japanese voices
        const japaneseVoices = this.voices.filter(v =>
            v.lang.includes('ja') || v.lang.includes('JP')
        );

        // Set default voice (prefer Japanese)
        if (japaneseVoices.length > 0) {
            this.voice = japaneseVoices[0];
        } else if (this.voices.length > 0) {
            this.voice = this.voices[0];
        }

        return this.voices;
    }

    /**
     * Get available voices
     * @returns {SpeechSynthesisVoice[]} Available voices
     */
    getVoices() {
        if (this.voices.length === 0) {
            this._loadVoices();
        }
        return this.voices;
    }

    /**
     * Get Japanese voices
     * @returns {SpeechSynthesisVoice[]} Japanese voices
     */
    getJapaneseVoices() {
        return this.getVoices().filter(v =>
            v.lang.includes('ja') || v.lang.includes('JP')
        );
    }

    /**
     * Set the voice by name
     * @param {string} voiceName - Voice name
     */
    setVoiceByName(voiceName) {
        if (!voiceName) {
            // Reset to default Japanese voice
            const japaneseVoices = this.getJapaneseVoices();
            this.voice = japaneseVoices.length > 0 ? japaneseVoices[0] : this.voices[0];
            return;
        }

        const voice = this.voices.find(v => v.name === voiceName);
        if (voice) {
            this.voice = voice;
        }
    }

    /**
     * Set speech rate
     * @param {number} rate - Speech rate (0.5 - 2.0)
     */
    setRate(rate) {
        this.rate = Math.max(0.5, Math.min(2.0, rate));
    }

    /**
     * Set speech pitch
     * @param {number} pitch - Speech pitch (0.5 - 2.0)
     */
    setPitch(pitch) {
        this.pitch = Math.max(0.5, Math.min(2.0, pitch));
    }

    /**
     * Enable or disable speech
     * @param {boolean} enabled - Whether speech is enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        if (!enabled) {
            this.stop();
        }
    }

    /**
     * Speak text
     * @param {string} text - Text to speak
     * @returns {Promise<void>} Resolves when speech ends
     */
    speak(text) {
        return new Promise((resolve, reject) => {
            if (!this.enabled || !text) {
                resolve();
                return;
            }

            // Cancel any ongoing speech
            this.stop();

            // Create utterance
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = this.rate;
            utterance.pitch = this.pitch;

            if (this.voice) {
                utterance.voice = this.voice;
            }

            // Event handlers
            utterance.onstart = () => {
                this.currentUtterance = utterance;
                if (this.onSpeakStart) {
                    this.onSpeakStart();
                }
            };

            utterance.onend = () => {
                this.currentUtterance = null;
                if (this.onSpeakEnd) {
                    this.onSpeakEnd();
                }
                resolve();
            };

            utterance.onerror = (event) => {
                this.currentUtterance = null;
                if (this.onSpeakEnd) {
                    this.onSpeakEnd();
                }
                // Don't reject on 'interrupted' or 'canceled'
                if (event.error === 'interrupted' || event.error === 'canceled') {
                    resolve();
                } else {
                    reject(new Error(`Speech error: ${event.error}`));
                }
            };

            // Speak
            this.synthesis.speak(utterance);
        });
    }

    /**
     * Stop current speech
     */
    stop() {
        if (this.synthesis.speaking) {
            this.synthesis.cancel();
        }
        this.currentUtterance = null;
    }

    /**
     * Check if currently speaking
     * @returns {boolean} Whether currently speaking
     */
    isSpeaking() {
        return this.synthesis.speaking;
    }

    /**
     * Check if Web Speech API is supported
     * @returns {boolean} Whether speech is supported
     */
    isSupported() {
        return 'speechSynthesis' in window;
    }
}

// Export singleton instance
const speechManager = new SpeechManager();
