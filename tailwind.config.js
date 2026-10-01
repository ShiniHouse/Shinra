// La configurazione di Tailwind: la stessa che stava in un copione dentro index.html.
//
// Tailwind non gira piu' nel browser. `web/static/css/tailwind.css` e' generato da qui con
// `npm run css` e va committato: la dashboard non ha niente da costruire a ogni apertura, e
// una CI che rigenera il file e lo confronta (`npm run css:verifica`) impedisce di cambiare
// una classe senza ricordarsi di rigenerarlo.
//
// `content` elenca dove cercare le classi. Una classe costruita a pezzi in JavaScript
// (`'bg-' + colore + '-500'`) qui non si vede: ci sono guardie contro l'HTML costruito
// attaccando stringhe, ed e' anche per questo.

/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: ['./web/templates/**/*.html', './web/static/js/**/*.js'],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                mono: ['"JetBrains Mono"', 'monospace'],
            },
            colors: {
                brand: {
                    50: '#eef2ff',
                    100: '#e0e7ff',
                    400: '#818cf8',
                    500: '#6366f1',
                    600: '#4f46e5',
                    700: '#4338ca',
                    900: '#1e1b4b',
                },
                amber: {
                    400: '#fbbf24',
                    500: '#f59e0b',
                    600: '#d97706',
                },
            },
        },
    },
};
