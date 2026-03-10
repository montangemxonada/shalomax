// ==================== Toast ====================
function toast() {
    return {
        visible: false,
        message: '',
        timeout: null,
        show(detail) {
            this.message = detail.message || '';
            this.visible = true;
            clearTimeout(this.timeout);
            this.timeout = setTimeout(() => { this.visible = false; }, 2500);
        }
    };
}

// ==================== Search Tabs ====================
function searchTabs() {
    return {
        tab: 'orden',
        queryOse: '',
        queryOrden: '',
        queryCodigo: '',
        history: JSON.parse(localStorage.getItem('shalomax_history') || '[]'),
        scanner: null,
        scannerStatus: 'Iniciando camara...',

        saveToHistory(val) {
            if (!val || !val.trim()) return;
            let h = this.history.filter(i => i !== val.trim());
            h.unshift(val.trim());
            h = h.slice(0, 8);
            this.history = h;
            localStorage.setItem('shalomax_history', JSON.stringify(h));
        },

        setQuery(val) {
            if (this.tab === 'ose') this.queryOse = val;
            else if (this.tab === 'orden') this.queryOrden = val;
        },

        clearHistory() {
            this.history = [];
            localStorage.removeItem('shalomax_history');
        },

        startScanner() {
            if (this.scanner) return;
            if (typeof Html5Qrcode === 'undefined') {
                this.scannerStatus = 'Escaner no disponible. Recarga la pagina.';
                return;
            }

            this.scannerStatus = 'Iniciando camara...';
            const self = this;

            this.$nextTick(() => {
                const readerEl = document.getElementById('qr-reader');
                if (!readerEl) return;

                self.scanner = new Html5Qrcode('qr-reader');
                self.scanner.start(
                    { facingMode: 'environment' },
                    { fps: 10, qrbox: { width: 250, height: 250 } },
                    (decodedText) => {
                        self.handleQrResult(decodedText);
                    },
                    () => {}
                ).then(() => {
                    self.scannerStatus = 'Apunta al codigo QR del recibo';
                }).catch((err) => {
                    console.warn('Camera error:', err);
                    self.scannerStatus = 'No se pudo acceder a la camara. Verifica los permisos.';
                    self.scanner = null;
                });
            });
        },

        stopScanner() {
            if (this.scanner) {
                this.scanner.stop().then(() => {
                    this.scanner.clear();
                    this.scanner = null;
                }).catch(() => {
                    this.scanner = null;
                });
            }
        },

        handleQrResult(text) {
            this.stopScanner();
            let oseId = text.trim();

            // If it's a URL like https://shalomax.../tracking/12345678
            const urlMatch = oseId.match(/\/tracking\/(\d+)/);
            if (urlMatch) {
                oseId = urlMatch[1];
            }

            // Clean to digits only
            oseId = oseId.replace(/\D/g, '');

            if (oseId && oseId.length >= 5 && oseId.length <= 8) {
                this.saveToHistory(oseId);
                window.location.href = '/tracking/' + oseId;
            } else {
                this.scannerStatus = 'QR no valido. Intenta de nuevo.';
                this.tab = 'orden';
                window.dispatchEvent(new CustomEvent('show-toast', {
                    detail: { message: 'El QR no contiene un ID valido' }
                }));
            }
        },

        destroy() {
            this.stopScanner();
        }
    };
}

// ==================== Tracking Page ====================
function trackingPage(oseId) {
    return {
        oseId: oseId,
        refreshInterval: null,

        init() {
            this.refreshInterval = setInterval(() => {
                this.refreshStatus();
            }, 60000);

            this.addToRecent(oseId);
        },

        async refreshStatus() {
            try {
                const res = await fetch(`/api/v1/tracking/${this.oseId}/status`);
                if (res.ok) {
                    // Silently refresh
                }
            } catch (e) {
                // Silent fail
            }
        },

        addToRecent(id) {
            let recent = JSON.parse(localStorage.getItem('shalomax_recent') || '[]');
            recent = recent.filter(i => i !== id);
            recent.unshift(id);
            recent = recent.slice(0, 20);
            localStorage.setItem('shalomax_recent', JSON.stringify(recent));
        },

        destroy() {
            clearInterval(this.refreshInterval);
        }
    };
}
