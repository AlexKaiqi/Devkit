// Service Worker for 风铃 Web Push
// 不缓存任何资源，只处理 push 通知和点击事件

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('push', (event) => {
  let title = '风铃';
  let body = '你有一条新消息';
  let url = '/';

  if (event.data) {
    try {
      const data = event.data.json();
      title = data.title || title;
      body = data.body || body;
      url = data.url || url;
    } catch (e) {
      body = event.data.text();
    }
  }

  // 通知所有已打开的页面，把消息插入对话流
  const notifyClients = clients.matchAll({ type: 'window', includeUncontrolled: true })
    .then(windowClients => {
      windowClients.forEach(client => client.postMessage({ type: 'push', body }));
    });

  const options = {
    body,
    icon: 'data:image/svg+xml,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
      '<text y=".9em" font-size="90">🎐</text></svg>'
    ),
    vibrate: [200, 100, 200],
    data: { url },
    badge: 'data:image/svg+xml,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
      '<circle cx="50" cy="50" r="45" fill="#6c63ff"/></svg>'
    ),
  };

  event.waitUntil(
    Promise.all([notifyClients, self.registration.showNotification(title, options)])
  );
});

self.addEventListener('notificationclick', (event) => {
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});
