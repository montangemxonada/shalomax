// Push notification subscription
async function subscribeToPush(oseId) {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        window.dispatchEvent(new CustomEvent('show-toast', {
            detail: { message: 'Tu navegador no soporta notificaciones push' }
        }));
        return;
    }

    try {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            window.dispatchEvent(new CustomEvent('show-toast', {
                detail: { message: 'Permiso de notificaciones denegado' }
            }));
            return;
        }

        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: null // Would need VAPID keys for production
        });

        // Save subscription to server
        await fetch('/api/v1/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ose_id: oseId,
                subscription: subscription.toJSON()
            })
        });

        window.dispatchEvent(new CustomEvent('show-toast', {
            detail: { message: 'Notificaciones activadas!' }
        }));

    } catch (err) {
        console.error('Push subscription failed:', err);
        window.dispatchEvent(new CustomEvent('show-toast', {
            detail: { message: 'Error al activar notificaciones' }
        }));
    }
}
