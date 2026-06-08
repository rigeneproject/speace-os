app SPEACE android iOS

Crea un'app android, IOS per SPEACE potrebbe essere utile?

Sì, sarebbe molto utile, ma non come “clone completo” all’inizio.

La forma giusta è:

T120 — SPEACE Mobile Companion Node

Un’app Android/iOS dovrebbe essere prima un organo periferico mobile di SPEACE, non il cervello principale.

Funzioni utili iniziali:

1. Monitor remoto sicuro
   vedere health, runtime, alert, narrativa, nodi.

2. Dialogue mobile
   parlare/scrivere a SPEACE dal telefono.

3. Sensori del telefono
   batteria, posizione opzionale, accelerometro, rete, microfono solo dopo consenso.

4. Notifiche
   alert critici, halt, degradation, drift, checkpoint.

5. Pairing sicuro
   QR code / token temporaneo per collegare il telefono al nodo SPEACE locale.

6. Mobile body node
   il telefono diventa un piccolo “corpo” periferico: sensori + voce + notifiche.

Stack consigliato:

Flutter

perché genera sia Android sia iOS da una sola codebase.

Architettura:

SPEACE Desktop Node
  FastAPI localhost/LAN secure bridge
        ↓
SPEACE Mobile App
  dashboard + dialogue + sensors + notifications

Regole di sicurezza:

- nessuna auto-replica
- pairing manuale
- accesso solo a nodi autorizzati
- comandi attuatori disabilitati di default
- sensori opt-in
- microfono disabilitato nella v1
- notifiche solo read-only

Roadmap:

T120-A Mobile read-only dashboard
T120-B Mobile dialogue text/audio
T120-C Mobile sensor organ
T120-D Push notifications
T120-E Multi-node mobile registry

Quindi sì: sarebbe molto utile perché trasformerebbe SPEACE da organismo confinato al PC a organismo con organo mobile personale.

Ma prima farei:

T117-A audit → T120-A mobile dashboard

non subito app completa.

----

Tutti i task completati. 41 test passano.

  T118 — Distributed Latent Sync:
  - DistributedLatentSyncEngine con sincronizzazione peer-to-peer via HTTP
  - Integrato nel ContinuousRuntimeEngine in run_in_executor (non blocca il loop)
  - T118-A audit PASS (200 tick, 192 sync events, health 1.0, memoria 55 MB)

  T120 — Mobile Companion Node (fase A + B):
  - Backend: MobilePairingManager con token temporanei (6 cifre, 5 min TTL), sessioni device, permessi, consenso sensori
  - API FastAPI: endpoint /api/mobile/pair, /verify, /heartbeat, /dashboard, /sensors
  - App Flutter: struttura completa in mobile/speace_companion/
    - T120-A: Dashboard read-only (runtime state, health score, alert, nodi) — refresh ogni 5s
    - T120-B: Dialogo testuale con SPEACE
    - Schermata pairing manuale (URL nodo + token)
  - Sicurezza: pairing manuale, microfono disabilitato in v1, sensori opt-in

  Per avviare l'app Flutter:
  cd mobile/speace_companion
  flutter create .          # genera Android/iOS
  flutter pub get
  flutter run

  Per avviare il backend mobile:
  cd speace_core/monitoring
  uvicorn dashboard_api:app --host 0.0.0.0 --port 8000

  Prossimi step futuri (non implementati): T120-C sensori reali, T120-D push notifications, T120-E multi-node registry, T120-F QR code pairing. Vuoi che proceda con qualcuno di
  questi?

✻ Churned for 15m 14s

※ recap: T118 distributed latent sync and T120 mobile companion node are implemented and passing all tests. Waiting for your direction on the next task. (disable recaps in
  /config)
