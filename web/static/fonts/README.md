# Caratteri

File copiati qui **senza modifiche**, serviti dal nostro server (la dashboard non chiede piu'
niente a Google Fonts). Sono i pacchetti `@fontsource-variable/*` del registro npm, che
ripubblicano i font originali in formato `woff2` variabile (un file per stile, tutti i pesi).
Solo i sottoinsiemi `latin` e `latin-ext`: coprono l'italiano e le lingue dell'Europa occidentale e
orientale; il cirillico e il vietnamita non servono a questa casa.

| Carattere | Pacchetto npm | Versione | Licenza | Stili qui |
| :--- | :--- | :--- | :--- | :--- |
| Plus Jakarta Sans | `@fontsource-variable/plus-jakarta-sans` | 5.3.0 | SIL OFL 1.1 (`LICENSE-plus-jakarta-sans.txt`) | normale e corsivo, pesi 200–800 |
| JetBrains Mono | `@fontsource-variable/jetbrains-mono` | 5.3.0 | SIL OFL 1.1 (`LICENSE-jetbrains-mono.txt`) | normale, pesi 100–800 |

| File | SHA-256 |
| :--- | :--- |
| `plus-jakarta-sans-latin-wght-normal.woff2` | `153fc85b70298beeb1d61a5f723331649e7f23bb77302a66e61cb3e2fbdb5e79` |
| `plus-jakarta-sans-latin-ext-wght-normal.woff2` | `38e3b8fd8045048eb311d90170a4429ed2c8f405852dc3d91b5af8452758703f` |
| `plus-jakarta-sans-latin-wght-italic.woff2` | `bb113d8f5be89636a9a31ffa0966762126546b98be171d6fa81115abb2cd5352` |
| `plus-jakarta-sans-latin-ext-wght-italic.woff2` | `7524d4b5f829201192882f775b90d78dbd9f9b3014ea729cfb7a47f5261ec7cb` |
| `jetbrains-mono-latin-wght-normal.woff2` | `18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e` |
| `jetbrains-mono-latin-ext-wght-normal.woff2` | `79bfdab9ba467e26eea4122e6f2567e188dd8a09a8c730d501fc487c4ab99c6e` |

Le regole `@font-face` sono in `../css/caratteri.css`. Per aggiornare: scarica la versione nuova
del pacchetto (`npm pack @fontsource-variable/...`), sostituisci i file, aggiorna questa tabella.
