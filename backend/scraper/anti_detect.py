import logging
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

# Comprehensive stealth scripts for Douyin anti-bot bypass
_STEALTH_SCRIPTS = [
    # 1. Hide webdriver flag (most critical)
    """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;
    """,

    # 2. Chrome runtime object
    """
    if (!window.chrome) { window.chrome = {}; }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            connect: function() {},
            sendMessage: function() {},
            onMessage: { addListener: function() {} },
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
            PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
            PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
            RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
            OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        };
    }
    """,

    # 3. Override navigator.plugins to look like normal Chrome
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const arr = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
            ];
            arr.refresh = () => {};
            Object.setPrototypeOf(arr, PluginArray.prototype);
            return arr;
        }
    });
    """,

    # 4. Override navigator.mimeTypes
    """
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => {
            const arr = [
                { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' },
                { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' },
            ];
            Object.setPrototypeOf(arr, MimeTypeArray.prototype);
            return arr;
        }
    });
    """,

    # 5. Override languages
    """Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });""",

    # 6. Fix Chrome user agent data (Client Hints)
    """
    if (navigator.userAgentData) {
        const originalGetHighEntropyValues = navigator.userAgentData.getHighEntropyValues;
        navigator.userAgentData.getHighEntropyValues = async function(hints) {
            const values = await originalGetHighEntropyValues.call(this, hints);
            values.brands = [
                { brand: 'Google Chrome', version: '131' },
                { brand: 'Chromium', version: '131' },
                { brand: 'Not_A Brand', version: '24' }
            ];
            values.mobile = false;
            values.platform = 'macOS';
            values.platformVersion = '15.0.0';
            values.architecture = 'arm';
            values.model = '';
            values.uaFullVersion = '131.0.6778.86';
            return values;
        };
        Object.defineProperty(navigator.userAgentData, 'brands', {
            get: () => [
                { brand: 'Google Chrome', version: '131' },
                { brand: 'Chromium', version: '131' },
                { brand: 'Not_A Brand', version: '24' }
            ]
        });
        Object.defineProperty(navigator.userAgentData, 'mobile', { get: () => false });
        Object.defineProperty(navigator.userAgentData, 'platform', { get: () => 'macOS' });
    }
    """,

    # 7. Override permissions query
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
    """,

    # 8. Spoof WebGL vendor/renderer (Apple GPU for macOS)
    """
    const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Apple';
        if (param === 37446) return 'Apple M1';
        return getParameterOrig.call(this, param);
    };
    const getParameterOrig2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Apple';
        if (param === 37446) return 'Apple M1';
        return getParameterOrig2.call(this, param);
    };
    """,

    # 9. Override connection rtt
    """
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', { get: () => 100 });
    }
    """,

    # 10. Fix hardwareConurrency and deviceMemory
    """
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    """,

    # 11. Canvas fingerprint noise - add subtle noise to canvas readback
    """
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
        // Add subtle pixel noise before export
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] ^ 1;  // tiny R noise
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}
        }
        return originalToBlob.call(this, callback, type, quality);
    };

    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] ^ 1;
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}
        }
        return originalToDataURL.call(this, type, quality);
    };
    """,

    # 12. AudioContext fingerprint protection
    """
    const origGetFloatFrequencyData = AnalyserNode.prototype.getFloatFrequencyData;
    AnalyserNode.prototype.getFloatFrequencyData = function(array) {
        origGetFloatFrequencyData.call(this, array);
        for (let i = 0; i < array.length; i++) {
            array[i] = array[i] + Math.random() * 0.0001;
        }
    };
    """,

    # 13. Prevent detection via Error stack traces (Playwright leaves traces)
    """
    const originalError = Error;
    function PatchedError(...args) {
        const err = new originalError(...args);
        Object.defineProperty(err, 'stack', {
            get: function() {
                return originalError.prototype.stack
                    ? err.stack.replace(/playwright/gi, '').replace(/puppeteer/gi, '')
                    : '';
            }
        });
        return err;
    }
    """,

    # 14. Window dimensions consistency (avoid headless tells)
    """
    Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
    Object.defineProperty(screen, 'availWidth', { get: () => screen.width });
    Object.defineProperty(screen, 'availHeight', { get: () => screen.height - 25 });
    """,

    # 15. Override Notification to look normal
    """
    if (window.Notification) {
        Object.defineProperty(Notification, 'permission', { get: () => 'default' });
    }
    """,

    # 16. Prevent iframe detection of automation
    """
    const origAppendChild = Element.prototype.appendChild;
    Element.prototype.appendChild = function(child) {
        if (child instanceof HTMLIFrameElement) {
            const result = origAppendChild.call(this, child);
            try {
                Object.defineProperty(child.contentWindow.navigator, 'webdriver', { get: () => undefined });
            } catch(e) {}
            return result;
        }
        return origAppendChild.call(this, child);
    };
    """,

    # 17. Override document.hasFocus() to always return true
    """
    Document.prototype.hasFocus = function() { return true; };
    """,

    # 18. Random mouse/keyboard micro-movements to simulate real user
    """
    (function() {
        let lastMove = Date.now();
        function randomMouseMove() {
            if (Date.now() - lastMove < 3000) return;
            lastMove = Date.now();
            const x = Math.floor(Math.random() * window.innerWidth);
            const y = Math.floor(Math.random() * window.innerHeight);
            document.dispatchEvent(new MouseEvent('mousemove', {
                clientX: x, clientY: y, bubbles: true
            }));
        }
        setInterval(randomMouseMove, Math.floor(5000 + Math.random() * 10000));
    })();
    """,

    # 19. Override visibility state to always appear visible
    """
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
    Object.defineProperty(document, 'hidden', { get: () => false });
    """,
]


async def apply_stealth(context: BrowserContext):
    """Apply comprehensive anti-detection measures to browser context."""
    combined_script = "\n".join(f"try {{ {s} }} catch(e) {{}}" for s in _STEALTH_SCRIPTS)
    await context.add_init_script(combined_script)
    logger.info("Applied stealth scripts (%d patches)", len(_STEALTH_SCRIPTS))
