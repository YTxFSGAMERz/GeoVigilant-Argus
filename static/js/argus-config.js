/**
 * GeoVigilant Argus Eye — Production Client Configuration & API Gateway
 *
 * Automatically resolves the backend API URL across:
 * - Vercel production deployment (via VITE_API_URL injected into build)
 * - Local development Vite server (falling back to relative proxy paths)
 * - Standalone Flask server
 */
(function() {
    var rawEnv = "%VITE_API_URL%";
    var configuredUrl = (rawEnv && rawEnv.indexOf("%") !== 0) ? rawEnv : "";

    // Allow window override if already set by an inline config
    var apiBaseUrl = (window.ARGUS_API_BASE_URL || configuredUrl || "").replace(/\/+$/, "");
    window.ARGUS_API_BASE_URL = apiBaseUrl;

    /**
     * Resolves an endpoint to an absolute URL if ARGUS_API_BASE_URL is configured,
     * or leaves it as a relative path for local development.
     */
    window.apiUrl = function(endpoint) {
        if (!endpoint) return "";
        if (endpoint.indexOf("http://") === 0 || endpoint.indexOf("https://") === 0) {
            return endpoint;
        }
        var cleanPath = endpoint.indexOf("/") === 0 ? endpoint : "/" + endpoint;
        return window.ARGUS_API_BASE_URL ? window.ARGUS_API_BASE_URL + cleanPath : cleanPath;
    };

    // If a production API base URL is present, install transparent fetch & axios interceptors
    if (window.ARGUS_API_BASE_URL) {
        var base = window.ARGUS_API_BASE_URL;
        var originalFetch = window.fetch;

        window.fetch = function(resource, init) {
            try {
                if (typeof resource === 'string') {
                    if (
                        resource.indexOf('/api/') === 0 ||
                        resource.indexOf('/nearby') === 0 ||
                        resource.indexOf('/searchzz') === 0 ||
                        resource.indexOf('/chat') === 0 ||
                        resource.indexOf('/socio/') === 0
                    ) {
                        resource = base + resource;
                    }
                } else if (resource && typeof resource === 'object' && resource.url) {
                    var origin = window.location.origin;
                    if (resource.url.indexOf(origin + '/api/') === 0 ||
                        resource.url.indexOf(origin + '/nearby') === 0 ||
                        resource.url.indexOf(origin + '/searchzz') === 0 ||
                        resource.url.indexOf(origin + '/chat') === 0 ||
                        resource.url.indexOf(origin + '/socio/') === 0) {
                        var path = resource.url.substring(origin.length);
                        resource = new Request(base + path, resource);
                    }
                }
            } catch (e) {
                console.warn('[Argus API Gateway] URL rewrite notice:', e);
            }
            return originalFetch.call(this, resource, init);
        };

        // Axios request interceptor hook
        function hookAxios() {
            if (window.axios && window.axios.interceptors && window.axios.interceptors.request) {
                window.axios.interceptors.request.use(function(config) {
                    if (config.url && (
                        config.url.indexOf('/api/') === 0 ||
                        config.url.indexOf('/nearby') === 0 ||
                        config.url.indexOf('/searchzz') === 0 ||
                        config.url.indexOf('/chat') === 0 ||
                        config.url.indexOf('/socio/') === 0
                    )) {
                        config.url = base + config.url;
                    }
                    return config;
                }, function(error) {
                    return Promise.reject(error);
                });
            }
        }

        if (window.axios) {
            hookAxios();
        } else {
            document.addEventListener('DOMContentLoaded', hookAxios);
        }
    }

    console.log('[Argus Config] Gateway active. API Base:', window.ARGUS_API_BASE_URL || '(relative local proxy)');
})();
