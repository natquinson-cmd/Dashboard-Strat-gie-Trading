const CACHE_NAME = 'songbook-v11';
// Only cache external CDN libraries — NEVER the app HTML itself
const ASSETS = [
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const url = event.request.url;
    // Always network-first for the app HTML, Firebase, Google APIs and fonts
    if (
        url.includes('firebasedatabase') || url.includes('googleapis') ||
        url.includes('fonts.gstatic') || url.includes('fonts.googleapis') ||
        url.endsWith('.html') || url.endsWith('/') ||
        url === self.location.origin + '/'
    ) {
        event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    } else {
        // Cache-first only for CDN libraries (pdf.js, mammoth, sortable)
        event.respondWith(
            caches.match(event.request).then(cached => cached || fetch(event.request))
        );
    }
});
