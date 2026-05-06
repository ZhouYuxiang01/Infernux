/**
 * Infernux Engine - Main JavaScript
 */

// ── Theme toggle ─────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
    applyNavbarBackground();
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (!icon) return;
    icon.className = theme === 'light' ? 'fas fa-sun' : 'fas fa-moon';
}

// Apply saved theme on load
(function() {
    const saved = localStorage.getItem('theme') || 'dark';
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    }
    document.addEventListener('DOMContentLoaded', function() {
        updateThemeIcon(saved);
    });
})();

// Mobile menu toggle
function toggleMobileMenu() {
    const navLinks = document.querySelector('.nav-links');
    navLinks.classList.toggle('mobile-open');
}

// Copy code to clipboard
function copyCode(button) {
    const codeBlock = button.closest('.code-block');
    const code = codeBlock.querySelector('code, pre');
    const text = code.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const icon = button.querySelector('i');
        icon.className = 'fas fa-check';
        button.style.color = '#27ca40';
        
        setTimeout(() => {
            icon.className = 'fas fa-copy';
            button.style.color = '';
        }, 2000);
    });
}

// Smooth scroll for anchor links
document.addEventListener('DOMContentLoaded', function() {
    applyNavbarBackground();
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                const navHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight - 20;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
});

// Navbar background: scroll + theme must both refresh — inline RGB from a
// previous theme would otherwise stick after toggleTheme() (e.g. after focus
// or code selection causes a scroll event).
function applyNavbarBackground() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;
    const style = getComputedStyle(document.documentElement);
    if (window.scrollY > 50) {
        navbar.style.background = style.getPropertyValue('--nav-bg-scroll').trim();
    } else {
        navbar.style.background = style.getPropertyValue('--nav-bg').trim();
    }
}

window.addEventListener('scroll', applyNavbarBackground);

// Add animation classes when elements come into view
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.addEventListener('DOMContentLoaded', function() {
    const animatedElements = document.querySelectorAll('[data-reveal], .hero-slab, .subpage-hero, .hub-hero, .cta-panel');
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        observer.observe(el);
    });
});

// Tab switching for code examples
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const tab = document.getElementById(tabId);
    if (tab) {
        tab.classList.add('active');
        // Find the button that triggered this
        document.querySelectorAll('.tab-btn').forEach(b => {
            if (b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId)) {
                b.classList.add('active');
            }
        });
    }
}

// Add animate-in styles
document.head.insertAdjacentHTML('beforeend', `
<style>
.animate-in {
    opacity: 1 !important;
    transform: translateY(0) !important;
}

.nav-links.mobile-open {
    display: flex !important;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-panel);
    flex-direction: column;
    padding: 20px;
    gap: 16px;
    border: 1px solid var(--border);
    border-radius: 22px;
    box-shadow: var(--shadow);
}
</style>
`);
