# Project Global TOD — Mullvad VPN Tray

**Main HEAD**: 9d2df38 · **Branch**: master · **Updated**: 2026-07-06 22:40

## ✅ Done (evidence-gated)

- [x] **MUL-001** — fix bug codice morto riga 181-184 · commit `acc668a`
- [x] **MUL-002** — logging strutturato su tutti gli except · commit `acc668a`
- [x] **MUL-003** — git init + .gitignore · commit `14dd9fb`
- [x] **MUL-004** — GitHub public repo `eroslifestyle/mullvad-vpn-tray` · link: https://github.com/eroslifestyle/mullvad-vpn-tray
- [x] **MUL-005** — README.md manuale EN completo · commit `01da745`
- [x] **MUL-006** — docs/index.html manuale bilingue dark theme · commit `01da745`
- [x] **MUL-007** — i18n EN/IT (24 chiavi) con auto-detect · commit `a10946f`
- [x] **MUL-008** — switch lingua in-app menu (🌐 Language) · commit `bf8ff18`
- [x] **MUL-009** — inline language submenu in build_menu (no monkey-patch) · commit `fdb8613`
- [x] **MUL-010** — ripristinare metodi persi nel refactor · commit `5ffb1dd`

## 🔄 In Progress

(nessuno)

## ⬜ Backlog (prossimi, priorità)

- [ ] **MUL-011** — notifiche desktop al cambio nodo · P2
      Comando: `pip install notify2 && python3 -c "import notify2; notify2.init('vpn-tray'); notify2.Notification('Test', 'OK').show()"`
      Done when: notifica visibile dopo cambio nodo (screenshot + journalctl log)

- [ ] **MUL-012** — validazione IP in `_on_web_connect` · P1
      Comando: edit `vpn-tray.py` aggiungere `if ip not in [n["ip"] for n in self.nodes]: return` prima di `connect_to(ip)`
      Done when: input JS invalido ignorato senza crash, log warning

- [ ] **MUL-013** — icona SVG custom al posto di security-low-symbolic · P3
      Comando: scaricare SVG → `icons/tray-off.svg` + `icons/tray-on.svg`, caricare con `set_icon_full(path)`
      Done when: icona custom visibile nel tray

- [ ] **MUL-014** — pacchetto `.deb` per distribuzione · P3
      Comando: setup `pyproject.toml` + entry point console_scripts
      Done when: `python3 -m build` produce wheel + sdist installabili

- [ ] **MUL-015** — test suite pytest · P2
      Comando: `pip install pytest` + creare `tests/test_vpn_tray.py` con mock per `subprocess.run`
      Done when: `pytest` exit 0, copertura >70%

## 🚫 Deferred / Blocked

- [~] **MUL-016** — multi-account Tailscale — scope creep, rimandato

## Cross-ref

- Session TOD corrente: `/tmp/session-TOD.md` (volatile)
- Checkpoint: `.claude/checkpoints/CP_20260706_224000.md`
- Vault mirror: `~/Obsidian/Memoria/progetti/vpn-tray/PROJECT-TOD.md`
- Sessione: `progetti/vpn-tray/sessioni/2026-07-06-sessione-iniziale-i18n-github.md`
- Decisioni: `progetti/vpn-tray/decisioni/2026-07-06-architettura-i18n.md`
