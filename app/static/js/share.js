// ==================== Share Widget ====================
function shareWidget(trackingUrl, oseId, status) {
    const shareText = `Mira el estado de mi envio ${oseId}: ${status}`;

    return {
        canShare: !!navigator.share,
        whatsappUrl: `https://wa.me/?text=${encodeURIComponent(shareText + '\n' + trackingUrl)}`,
        telegramUrl: `https://t.me/share/url?url=${encodeURIComponent(trackingUrl)}&text=${encodeURIComponent(shareText)}`,
        emailUrl: `mailto:?subject=${encodeURIComponent('Estado de envio ' + oseId)}&body=${encodeURIComponent(shareText + '\n\n' + trackingUrl)}`,

        copyUrl() {
            navigator.clipboard.writeText(trackingUrl).then(() => {
                window.dispatchEvent(new CustomEvent('show-toast', {
                    detail: { message: 'Link copiado al portapapeles!' }
                }));
            }).catch(() => {
                // Fallback
                const input = document.createElement('input');
                input.value = trackingUrl;
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                document.body.removeChild(input);
                window.dispatchEvent(new CustomEvent('show-toast', {
                    detail: { message: 'Link copiado!' }
                }));
            });
        },

        nativeShare() {
            if (navigator.share) {
                navigator.share({
                    title: `Envio ${oseId} - Shalomax`,
                    text: shareText,
                    url: trackingUrl,
                }).catch(() => {});
            }
        }
    };
}
