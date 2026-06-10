async function loadNotifications() {
    try {
        const response = await fetch('/api/notifications?page=1', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            updateNotificationUI(data.notifications, data.unread_count);
            return data;
        } else {
            console.error('API returned error:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Failed to load notifications:', error);
        return null;
    }
}

function updateNotificationUI(notifications, unreadCount) {
    updateNotificationBadge(unreadCount);
    const dropdown = document.getElementById('notifications-dropdown');
    if (dropdown) {
        if (notifications && notifications.length > 0) {
            dropdown.innerHTML = notifications.slice(0, 10).map(notif => `
                <div class="notification-item p-3 border-bottom ${notif.read ? '' : 'bg-light'}" data-id="${notif.id}">
                    <div class="d-flex">
                        <div class="flex-shrink-0">
                            ${getNotificationIcon(notif.name)}
                        </div>
                        <div class="flex-grow-1 ms-3">
                            <p class="mb-1 small">${getNotificationMessage(notif)}</p>
                            <small class="text-muted">${formatTimeAgo(notif.timestamp)}</small>
                        </div>
                    </div>
                </div>
            `).join('');
            dropdown.innerHTML += '<div class="text-center p-2"><a href="/notifications-page" class="small">View all notifications</a></div>';
        } else {
            dropdown.innerHTML = '<div class="text-center p-4 text-muted"><i class="fas fa-bell-slash fa-2x mb-2 d-block"></i>No notifications yet</div>';
        }
    }
}

function getNotificationIcon(name) {
    const icons = {
        'like': '<i class="fas fa-thumbs-up text-primary fa-fw"></i>',
        'comment': '<i class="fas fa-comment text-success fa-fw"></i>',
        'follow': '<i class="fas fa-user-plus text-info fa-fw"></i>',
        'share': '<i class="fas fa-share-alt text-warning fa-fw"></i>',
        'friend_request': '<i class="fas fa-user-friends text-danger fa-fw"></i>'
    };
    return icons[name] || '<i class="fas fa-bell text-secondary fa-fw"></i>';
}

function getNotificationMessage(notif) {
    try {
        const payload = typeof notif.payload === 'string' ? JSON.parse(notif.payload) : notif.payload;

        switch(notif.name) {
            case 'like':
                return `<strong>${payload.username || 'Someone'}</strong> liked your post`;
            case 'comment':
                return `<strong>${payload.username || 'Someone'}</strong> commented: "${payload.comment_preview?.substring(0, 50)}..."`;
            case 'follow':
                return `<strong>${payload.username || 'Someone'}</strong> started following you`;
            case 'share':
                return `<strong>${payload.username || 'Someone'}</strong> shared your post`;
            case 'friend_request':
                return `<strong>${payload.username || 'Someone'}</strong> sent you a friend request`;
            default:
                return notif.name;
        }
    } catch(e) {
        return 'New notification';
    }
}

let notificationInterval = null;

function startNotificationPolling() {
    if (notificationInterval) clearInterval(notificationInterval);

    notificationInterval = setInterval(async () => {
        if (document.hidden) return;

        const data = await loadNotifications();
        if (data && data.unread_count > 0) {
            updateNotificationBadge(data.unread_count);
        }
    }, 30000);
}

function stopNotificationPolling() {
    if (notificationInterval) {
        clearInterval(notificationInterval);
        notificationInterval = null;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('notification-bell')) {
        startNotificationPolling();
        loadNotifications();
    }
});
