# NexaSim Complete User Guide: YAML Syntax, Execution, Visualization & KPI Analysis

Benvenuto nella guida ufficiale di **NexaSim**, il simulatore unificato 3D per reti terrestri (TN), non-terrestri (NTN) e comunicazioni veicolari (V2X) sviluppato per il progetto **Horizon Europe NexaSphere**.

---

## Indice dei Contenuti
1. [Workflow Generale di Simulazione](#1-workflow-generale-di-simulazione)
2. [Sintassi e Specifica Completa dei File YAML](#2-sintassi-e-specifica-completa-dei-file-yaml)
   - [2.1 Metadati e Area Geografica (`scenario`, `area`, `time`)](#21-metadati-e-area-geografica)
   - [2.2 Costellazioni Satellitari LEO & ISL (`constellation`)](#22-costellazioni-satellitari-leo--isl)
   - [2.3 Rete Terrestre 5G-NR & Orografia (`terrestrial`)](#23-rete-terrestre-5g-nr--orografia)
   - [2.4 Terminali Utente & Parabole Phased-Array (`ue`)](#24-terminali-utente--parabole-phased-array)
   - [2.5 Simulazione di Incidenti & Allerte di Emergenza (`incident`)](#25-simulazione-di-incidenti--allerte-di-emergenza)
   - [2.6 Metriche e Configurazione di Output (`output`)](#26-metriche-e-configurazione-di-output)
3. [Generazione ed Esecuzione degli Scenari](#3-generazione-ed-esecuzione-degli-scenari)
4. [Analisi dei Dati, Metriche KPI e Dashboard Interattiva](#4-analisi-dei-dati-e-metriche-kpi)
5. [Visualizzazione Grafica della Rete e del Traffico (OMNeT++ Qtenv & SUMO-GUI)](#5-visualizzazione-grafica-della-rete-e-del-traffico-omnet-qtenv--sumo-gui)
6. [Benchmark Suite & Parameter Sweep (`nexasim sweep`)](#6-benchmark-suite--parameter-sweep-nexasim-sweep)
7. [Digital Twin 3D Geospaziale su Globo Terrestre (`nexasim view-3d`)](#7-digital-twin-3d-geospaziale-su-globo-terrestre-nexasim-view-3d)
   - [7.1 Viste Telecamera Preset](#71-viste-telecamera-preset)
   - [7.2 Selezione Basemap e Terreno](#72-selezione-basemap-e-terreno)
   - [7.3 Gestione HUD in modalità Dual](#73-gestione-hud-in-modalita-dual)
8. [NexaSim Studio: Web Control Center No-Code (`nexasim studio`)](#8-nexasim-studio-web-control-center-no-code-nexasim-studio)
   - [8.1 Layout del Control Center](#81-layout-del-control-center)
   - [8.2 Vista Single 2D — Mappa Tattica Leaflet](#82-vista-single-2d--mappa-tattica-leaflet)
   - [8.3 Vista Single 3D — Globo CesiumJS](#83-vista-single-3d--globo-cesiumjs)
   - [8.4 Vista Dual — 2D + 3D affiancati](#84-vista-dual--2d--3d-affiancati)
   - [8.5 Drawer Inferiore — Dashboard Esecutiva](#85-drawer-inferiore--dashboard-esecutiva)
   - [8.6 Customizer Parametri e Console di Esecuzione](#86-customizer-parametri-e-console-di-esecuzione)

---

## 1. Workflow Generale di Simulazione

Il flusso di lavoro di NexaSim è interamente automatizzato e modulare:

```
+------------------------------------+
|  File di Configurazione YAML       |  (es. scenarios/library/stelvio_pass_hybrid.yaml)
+------------------------------------+
                  |
                  v  python tools/gen_scenario.py <file.yaml> -o scenarios/generated/<nome>
+------------------------------------+
|  File OMNeT++ / SUMO Generati      |  (scenario.ned, omnetpp.ini, constellation.tle, mobility.tcl)
+------------------------------------+
                  |
                  v  Esecuzione (Docker Compose o Dev Container)
+------------------------------------+
|  Esecuzione Simulazione & Log      |  (output/*.csv, output/*.vec, output/*.sca)
+------------------------------------+
         |                          |
         v                          v
+--------------------+    +------------------------------------------+
| Analisi KPI        |    | Visualizzazione Grafica Nativa           |
| analyze_results.py |    | • OMNeT++ Qtenv (Pacchetti, Nodi 3D, RF) |
|                    |    | • SUMO GUI (Traffico Veicolare, Crash)   |
+--------------------+    +------------------------------------------+
```

---

## 2. Sintassi e Specifica Completa dei File YAML

I file di scenario si trovano in `scenarios/library/` e consentono di definire in modo dichiarativo e leggibile topologie di rete 3D complesse.

### 2.1 Metadati e Area Geografica

```yaml
scenario:
  name: "stelvio_pass_alpine_hybrid"          # Nome univoco dello scenario
  description: "Descrizione dettagliata del caso d'uso"
  version: "1.0"
  
  area:
    name: "Passo_dello_Stelvio"               # Nome dell'area geografica
    center_lat: 46.5286                       # Latitudine centrale (gradi decimali)
    center_lon: 10.4531                       # Longitudine centrale (gradi decimali)
    altitude_m: 2757                          # Quota media/vetta (metri)
    bbox: [10.4000, 46.5000, 10.5000, 46.5600]# Bounding Box: [min_lon, min_lat, max_lon, max_lat]
    elevation_mask_deg: 28.0                  # Maschera d'elevazione orografica (blocca satelliti bassi)
  
  time:
    start: "2026-08-26T10:00:00Z"             # Timestamp iniziale ISO 8601
    duration_s: 300                           # Durata totale simulazione in secondi
    warmup_s: 15                              # Periodo di assestamento iniziale
    timezone: "Europe/Rome"
```

---

### 2.2 Costellazioni Satellitari LEO & ISL (`constellation`)

NexaSim supporta sia costellazioni parametriche **Walker-Delta**, sia costellazioni multi-guscio (stile **Starlink / Kuiper**), sia effemeridi **TLE** arbitrarie:

```yaml
  constellation:
    type: "starlink_shell"                    # Opzioni: "starlink_shell", "walker_delta", "custom_tle"
    shells:
      - name: "starlink_shell_550"
        altitude_km: 550                      # Altitudine orbitale LEO (km)
        inclination_deg: 53.0                 # Inclinazione orbitale (gradi)
        num_planes: 12                        # Numero di piani orbitali (P)
        sats_per_plane: 6                     # Satelliti per piano orbitale (S)
        phase_offset: 0                       # Sfasamento tra piani (F)
    
    # Inter-Satellite Links (ISL) ottici o RF
    isl:
      enabled: true                           # Abilita comunicazioni laser tra satelliti
      type: "laser"                           # Opzioni: "laser" (1550nm) o "rf_v_band" (60GHz)
      wavelength_nm: 1550                     # Lunghezza d'onda laser (nm)
      max_range_km: 5000                      # Portata massima link inter-satellitare (km)
      num_ports_per_sat: 4                    # 2 intra-piano (avanti/dietro) + 2 inter-piano (sinistra/destra)
      tx_power_dbm: 20                        # Potenza di trasmissione ottica
      rx_sensitivity_dbm: -40                 # Sensibilità ricevitore
      pointing_accuracy_deg: 0.01             # Accuratezza puntamento PAT (Pointing, Acquisition, Tracking)
      acquisition_time_ms: 80                 # Tempo medio di aggancio ottico (ms)
    
    # Ground Stations (Gateway di Terra collegati alle Centrali di Soccorso/Core Network)
    ground_stations:
      - name: "gw_bolzano_rescue_center"
        lat: 46.4983
        lon: 11.3548
        altitude_m: 262
        feeder_link:
          frequency_ghz: 28.0                 # Frequenza Feeder Link Ka-Band (GHz)
          bandwidth_mhz: 1000                 # Ampiezza di banda feeder (MHz)
        user_link:
          frequency_ghz: 28.0
          bandwidth_mhz: 500
        elevation_mask_deg: 15.0
```

---

### 2.3 Rete Terrestre 5G-NR & Orografia (`terrestrial`)

Definisce le stazioni radio base (gNodeB), le zone d'ombra montuose e il meteo:

```yaml
  terrestrial:
    gnb:
      deployment: "custom"                    # Opzioni: "custom" (coordinate puntuali) o "grid" (griglia automatica)
      sites:
        - name: "gnb_trafoi_valley"
          lat: 46.5540
          lon: 10.5100
          height_m: 30                        # Altezza traliccio (m)
          tx_power_dbm: 46                    # Potenza EIRP (dBm)
          frequency_ghz: 3.5                  # Banda 5G-NR sub-6GHz (n78)
          bandwidth_mhz: 100
          mimo_layers: 4
          coverage_radius_m: 1800             # Raggio di copertura teorico
        - name: "gnb_stelvio_summit"
          lat: 46.5286
          lon: 10.4531
          height_m: 20
          tx_power_dbm: 46
          frequency_ghz: 3.5
          bandwidth_mhz: 100
          mimo_layers: 4
          coverage_radius_m: 2500

    # Zone d'Ombra Radio (Gole, Gallerie, Dietro pareti rocciose)
    blind_spots:
      - name: "gorge_shadow_zone"
        lat_min: 46.5300
        lat_max: 46.5370
        lon_min: 46.4550
        lon_max: 46.4700
        attenuation_db: 45.0                  # Attenuazione rocciosa (provoca il blackout del 5G)

    channel_model: "RMa"                      # Modello di canale: Rural Macro (RMa), Urban Macro (UMa)
    
    # Condizioni Atmosferiche e Meteo
    alpine_weather:
      condition: "snow_and_rain"
      rain_rate_mm_hr: 15.0                   # Intensità precipitazione (mm/h)
      snow_attenuation_db_per_km: 1.8         # Attenuazione neve su link Ka-Band (dB/km)
      atmospheric_loss_db: 2.5
```

---

### 2.4 Terminali Utente & Parabole Phased-Array (`ue`)

```yaml
    ue:
      count: 24                               # Numero di veicoli / nodi mobili
      mobility_model: "alpine_pass_traversal" # Modello di mobilità (tornanti, autostrada, città)
      speed_kmh: 45
      
      # Dual-Connectivity (MR-DC 3GPP Rel. 16/17)
      dual_connectivity:
        enabled: true
        mode: "mrdc"
        primary_rat: "terrestrial_5g"         # RAT preferita quando disponibile
        fallback_rat: "satellite_ntn"         # RAT di backup in caso di blackout radio
        seamless_failover: true
      
      # Antenna a scansione elettronica (Starlink Dish veicolare)
      phased_array:
        elements: 64                          # Matrice 8x8 elementi attivi
        gain_dbi: 32.0                        # Guadagno d'antenna a centro banda
        scan_angle_max_deg: 60.0              # Angolo massimo di sterzamento del fascio
        beamwidth_deg: 8.5                    # Ampiezza a 3dB del fascio
        tracking_rate_deg_per_sec: 45.0       # Velocità di inseguimento angolare

    # Strategie di Handover & Relay Cooperativo
    integration:
      handover:
        enabled: true
        rsrp_threshold_dbm: -108              # Soglia RSRP minima per trigger handover
        hysteresis_db: 3.5
        make_before_break: true               # Handover senza interruzione (connessione al nuovo satellite prima del distacco)
      
      emergency_routing:
        mode: "hybrid_v2v_satellite"          # Se il satellite è ostruito, inoltra via V2V ai veicoli vicini
        v2v_sidelink_enabled: true
        v2v_relay_range_m: 450
        v2v_frequency_ghz: 5.9                # Frequenza ITS-G5 / C-V2X PC5 (GHz)
```

---

### 2.5 Simulazione di Incidenti & Allerte di Emergenza (`incident`)

```yaml
  incident:
    enabled: true
    trigger_time_s: 45.0                      # Secondo esatto in cui avviene il crash
    location:
      name: "Tornante_18_Blind_Curve"
      lat: 46.5332
      lon: 46.4625
      altitude_m: 2310
    vehicle_id: 7                             # ID veicolo coinvolto
    event_type: "severe_collision_road_blocked"
    message_type: "ETSI_DENM_and_eCall"       # Standard ETSI ITS-G5 + eCall
    data_payload_bytes: 1200
    alert_interval_ms: 100                    # Frequenza di ritrasmissione allerta (10 Hz)
```

---

### 2.6 Metriche e Configurazione di Output (`output`)

```yaml
  output:
    directory: "output/stelvio_alpine_hybrid_${timestamp}"
    metrics:
      - "emergency_alert_latency"             # Latenza E2E tra crash e centrale soccorsi
      - "satellite_acquisition_time"          # Tempo di orientamento fascio phased-array
      - "handover_success_rate"               # Percentuale handover riusciti
      - "coverage_ratio_5g_vs_ntn_vs_outage"  # Distribuzione temporale di copertura
      - "throughput_embb_vs_emergency"        # Throughput per slice
      - "v2v_relay_hops"                      # Numero di hop cooperativi
      - "weather_rain_snow_attenuation"       # Perdita di potenza atmosferica
      - "isl_laser_jitter_and_ber"            # Prestazioni link inter-satellitari
    format: "csv"
    write_interval_s: 0.5
```

---

## 3. Generazione ed Esecuzione degli Scenari con la CLI Unificata (`nexasim`)

NexaSim include la CLI unificata `nexasim` (eseguibile da `./nexasim` o `python tools/nexasim.py`), che coordina l'intera pipeline di validazione, generazione topologica, esecuzione del simulatore e generazione dei report.

### Comandi Rapidi della CLI:

```bash
# 1. Elencare tutti gli scenari pronti all'uso nella libreria
./nexasim list

# 2. Validare la sintassi e i vincoli fisici dello scenario (Pydantic & JSON Schema)
./nexasim validate stelvio

# 3. Generare i file OMNeT++ e la rete stradale microscopica SUMO
./nexasim generate stelvio

# 4. Eseguire la simulazione in modalità headless (rapida, via Docker)
./nexasim run stelvio

# 5. Eseguire con visualizzazione interattiva (Qtenv + SUMO-GUI via NoVNC)
./nexasim run stelvio --gui
# Collegarsi nel browser all'indirizzo: http://localhost:6080/vnc.html

# 6. Analisi KPI e generazione Dashboard HTML Chart.js
./nexasim analyze stelvio --dashboard

# 7. Aprire direttamente il Dashboard HTML generato nel browser
./nexasim dashboard stelvio --open

# 8. Esecuzione End-to-End completa (Generate -> Run -> Analyze -> Dashboard)
./nexasim all nexasphere_highway_platooning
```

---

## 4. Analisi dei Dati, Metriche KPI e Dashboard Interattivo

Per analizzare le prestazioni della simulazione ed estrarre tutti i parametri di telemetria:

```bash
./nexasim analyze stelvio --dashboard
```

Questo comando calcola tutti i KPI di rete e genera contemporaneamente nella cartella `results/`:
1. **`dashboard.html`**: dashboard web moderna e reattiva con KPI cards e grafici Chart.js organizzati in una griglia 2x2 unificata (Active Interface, QoS Utility Score, MEC Latency, Cumulative Handovers), più Fleet Multi-RAT Telemetry Summary e Physical Link Budget.
2. **`kpi_summary.json`**: esportazione strutturata dei KPI aggregati per pipeline CI/CD o benchmarking comparativo.

### 4.1 Griglia 2x2 della Dashboard Esecutiva

La dashboard è stata ridisegnata da una struttura a schede (6 tab) a una **griglia CSS 2x2 unificata** che mostra i quattro grafici più rilevanti per il monitoring operativo:

| Grafico | Tipo | Cosa mostra |
| :--- | :--- | :--- |
| **Active Interface** | Area | Timeline dell'interfaccia attiva per ciascun veicolo (5G-NR vs Satellite LEO). |
| **QoS Utility Score** | Linea | Metrica di utilità di rete (0-1) che combina throughput, latenza e affidabilità. |
| **MEC Latency** | Barra | Latenza task di edge computing (upload + elaborazione + download). |
| **Cumulative Handovers** | Linea | Numero cumulativo di handover verticali nel tempo (make-before-break). |

Sotto la griglia sono presenti due sezioni di supporto:
- **Fleet Multi-RAT Telemetry Summary**: tabella riassuntiva per ciascun veicolo (RAT primaria, throughput, latenza, energia residua).
- **Physical Link Budget**: bilancio di link fisico (RSSI, SNR, attenuazione meteo, margine di link).

I grafici sono generati dinamicamente da `tools/dashboard.py` tramite **Chart.js**, con tooltip e legenda interattivi, e sono ri-disegnati automaticamente al redimensionamento della finestra.

### Esempio di Report Generato a Terminale:
```text
=======================================================
 NexaSim KPI Analysis Report: stelvio
=======================================================

--- [1] TEMPI DI RISPOSTA EMERGENZA & INCIDENTI (Tornante 18 Blind Spot) ---
  • Evento Crash Rilevato:                 t = 45.000 s
  • Metodo Trasmissione Principale:        Fallback Satellitare LEO (Phased-Array)
  • Tempo di Allineamento Antenna (PAT):   84.5 ms
  • Latenza E2E Notifica Soccorsi:        14.8 ms (Target URLLC < 20 ms: OK)
  • Latenza Relay Cooperativo V2V-Sidelink:8.2 ms
  • Esito Recapito Allerta eCall/DENM:     CONFERMATO (100% Affidabilità)

--- [2] PERFORMANCE AGGANCIO SATELLITARE & HANDOVER (Maschera 28° Alpina) ---
  • Satelliti Visibili Medi per Veicolo:   3.4 satelliti (Costellazione 550 km, 53°)
  • Tasso di Successo Handover:            98.6%
  • Handover Eseguiti (Make-Before-Break): 48 (95.8% seamless)
  • Link Inter-Satellitari Ottici (ISL):   9.85 Gbps (BER: 1.2e-11)

--- [3] COPERTURA 3D IBRIDA LUNGO IL PERCORSO DELLO STELVIO ---
  • Copertura Terrestre 5G-NR (Vetta/Valle): 55.0%
  • Copertura Satellitare LEO (Gole/Ombra):  45.0%
  • Tasso di Successo Handover Seamless:     100.0%

--- [4] IMPATTO METEO ALPINO (Pioggia / Neve in Quota) ---
  • Attenuazione Aggiuntiva Ka-Band (28 GHz): 3.4 dB
  • Margine di Link Rimanente:                +14.2 dB (Link attivo senza drop)
```

---

## 5. Visualizzazione Grafica della Rete e del Traffico (OMNeT++ Qtenv & SUMO-GUI)

NexaSim supporta l'ispezione grafica completa a due livelli: la **rete 3D spazio-terra (OMNeT++ Qtenv)** e il **traffico microscopico veicolare (SUMO-GUI)**.

---

### 5.1 Visualizzazione di Rete con OMNeT++ Qtenv

**Qtenv** è l'interfaccia grafica nativa avanzata di OMNeT++. Permette di:
- **Osservare l'architettura 3D**: Visualizzazione in tempo reale di tutti i nodi della costellazione LEO (72 satelliti orbitanti), delle Ground Station di terra, dei gNodeB 5G-NR e dei terminali veicolari.
- **Ispezione Pacchetto per Pacchetto**: Cliccando su qualsiasi nodo (es. `ue[7]`), è possibile ispezionare le code di trasmissione, i messaggi **ETSI DENM / eCall**, i pacchetti di controllo **PAT** della parabola phased-array e i payload scambiati sui link laser **ISL**.
- **Animazione dei Flussi Radio**: I pacchetti in transito vengono visualizzati come impulsi grafici tra le antenne e i satelliti.
- **Grafici Vettoriali Live**: Monitoraggio in tempo reale di RSRP, SNR, tempi di accodamento, tassi di handover e BER.

#### Come avviare OMNeT++ Qtenv:

##### A) Tramite VS Code Dev Containers (Consigliato)
1. Apri la repository in VS Code e premi `F1` $\rightarrow$ **`Dev Containers: Reopen in Container`**.
2. Dal terminale integrato, esegui:
   ```bash
   opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Qtenv
   ```
   La finestra grafica apparirà istantaneamente sul desktop grazie all'inoltro X11/WSLg automatico.

##### B) Tramite Docker Compose su Windows
- **Su Windows 11 (WSLg nativo)**:
  ```powershell
  docker compose run --rm -e DISPLAY=$env:DISPLAY nexasim-run opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Qtenv
  ```
- **Su Windows 10 (con VcXsrv avviato con "Disable access control")**:
  ```powershell
  docker compose run --rm -e DISPLAY=host.docker.internal:0.0 nexasim-run opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Qtenv
  ```

---

### 5.2 Visualizzazione del Traffico Veicolare con SUMO-GUI

**SUMO-GUI** permette di visualizzare il flusso di traffico microscopico sui tornanti del Passo dello Stelvio, le manovre di guida, le velocità e il comportamento delle vetture in seguito all'incidente:

```bash
# Esecuzione da Dev Container o Docker Compose
sumo-gui -c scenarios/generated/stelvio/stelvio.sumocfg
```

#### Cosa osservare in SUMO-GUI:
- **Geometria dei Tornanti**: Visualizzazione della mappa stradale dello Stelvio e delle pendenze.
- **Dinamica del Crash ($t = 45\text{s}$)**: Arresto dell'auto coinvolta nell'incidente, rallentamento dei veicoli retrostanti e code in prossimità del tornante cieco.
- **Interazione TraCI**: Sincronizzazione al millisecondo tra il movimento delle auto in SUMO e lo stack di telecomunicazioni in OMNeT++.

---

## 6. Benchmark Suite & Parameter Sweep (`nexasim sweep`)

Per condurre studi di sensibilità e analisi statistiche Monte Carlo confrontando configurazioni multiple:

```bash
# Confronto diretto delle tre strategie di Vertical Handover
./nexasim sweep stelvio --param switchingMode=coverage-based,qos-based,energy-aware --reps 3

# Studio di sensibilità all'attenuazione meteo Ka-Band (pioggia)
./nexasim sweep emergency_corridor --param rainRateMmPerH=0,15,30,50 --reps 1

# Studio d'impatto della maschera d'elevazione orografica
./nexasim sweep stelvio --param elevationMaskDeg=15,25,35 --reps 2
```

Il comando genera nella cartella `scenarios/generated/sweep_<nome>/`:
- `sweep_summary.json`: tabella JSON di tutti i run con parametri e KPI estratti.
- `sweep_report.html`: report esecutivo con grafici a barre e box plot comparativi Chart.js (frequenza VHO, distribuzione latenza, rapporto 5G vs NTN, consumo batteria residua).

---

## 7. Digital Twin 3D Geospaziale su Globo Terrestre (`nexasim view-3d`)

Visualizzazione fotorealistica 3D geospaziale nello spazio e sul terreno tramite **CesiumJS 1.119** e pacchetti **CZML** generati dinamicamente da `tools/czml_generator.py`:

```bash
# Genera lo stream CZML e apre il globo 3D nel browser
./nexasim view-3d stelvio
```

### Elementi visualizzati nel Digital Twin:
- **Costellazione LEO (550 km)**: satelliti con dinamica orbitale Kepleriana / SGP4 attorno alla Terra WGS84.
- **Link Laser Ottici (ISL)**: raggi laser ciano/oro tra satelliti adiacenti nello spazio.
- **Celle 5G-NR**: coni di copertura radio volumetrica attorno ai tralicci base station gNodeB.
- **Fasci di Tracciamento Phased-Array**: raggi dinamici magenta che collegano il veicolo al satellite agganciato in tempo reale.
- **Veicoli sul terreno**: marker 3D dei veicoli del convoglio, allineati al terreno grazie a `heightReference: "CLAMP_TO_GROUND"` (quota di altitudine forzata a 0 m sul modello digitale del terreno).

### 7.1 Viste Telecamera Preset

Il globo 3D mette a disposizione tre preset di inquadratura, calibrati sui coordinate geografiche effettive dello scenario (non valori hardcoded):

| Pulsante | Descrizione | Comportamento |
| :--- | :--- | :--- |
| **Tactical** | Vista tattica regionale | Inquadra l'area dello scenario a 5.5 km di distanza, inclinazione -32°, heading 20°. Mostra l'intera area di studio con terreno, gNodeB e costellazione. |
| **Chase Cam** | Inseguimento del veicolo | Sblocca la telecamera sul veicolo 0 (`veh_0`, capo convoglio) con `viewFrom` relativo. La telecamera segue il veicolo mentre questo si sposta lungo la traiettoria. |
| **Orbit LEO** | Orbita LEO costellazione | Vista d'insieme della costellazione: raggio 150 km, distanza 2.200 km, inclinazione -50°. Permette di osservare la dinamica orbitale dei satelliti e gli ISL. |

Tutti i preset usano `viewer.camera.flyToBoundingSphere` con `Cesium.HeadingPitchRange` e una durata di 1.5-2.0 s (animazione fluida, non salto istantaneo).

### 7.2 Selezione Basemap e Terreno

Il pannello di controllo in alto a destra del globo permette di switchare la mappa di base:
- **Cesium World Terrain** (terreno fotorealistico 3D con dati bathymetrici e ortofoto).
- **ESRI World Imagery** (via `UrlTemplateImageryProvider`, endpoint `server.arcgisonline.com` — evita l'errore del provider deprecato `ArcGisMapServerImageryProvider`).
- **Cesium Black Marble** (mappa notturna, utile per ridurre il disturbo visivo sui link laser nello spazio).

La scelta del terreno è protetta da un try/catch: in caso di mancato caricamento del World Terrain (assenza di token Cesium Ion valido), il viewer cade back a `EllipsoidTerrainProvider` (terreno liscio, niente crash).

### 7.3 Gestione HUD in modalità Dual

Quando il globo viene mostrato in modalità **Dual** (2D+3D affiancati), il pannello HUD del globo deve essere nascosto per evitare sovrapposizioni con la mappa 2D. Questa gestione avviene in due direzioni:
1. Lo studio.html aggiunge `?hud=0` alla query string dell'iframe del globo in modalità dual.
2. Il globo ascolta i messaggi `postMessage` dal parent (`{ showHud: false }`) per nascondere/mostrare il pannello HUD dinamicamente.

---

## 8. NexaSim Studio: Web Control Center No-Code (`nexasim studio`)

Per configurare, visualizzare e lanciare simulazioni tramite interfaccia web locale senza usare il terminale:

```bash
./nexasim studio --port 8080
```
Apri il browser all'indirizzo `http://localhost:8080`.
La documentazione interattiva OpenAPI / Swagger dell'API REST è disponibile a `http://localhost:8080/docs`.
Il token Cesium Ion e la CARTO API Key sono letti da `.env` (isolato e `.gitignore`-ato, mai commitato).

### 8.0 Architettura Backend ad Alte Prestazioni (FastAPI & Uvicorn)

Il backend di NexaSim Studio è basato su **FastAPI** e servito tramite il server ASGI **Uvicorn**:
- **Esecuzione Asincrona con Background Tasks**: Le simulazioni pesanti di OMNeT++ vengono delegate a thread asincroni in background (`BackgroundTasks`), garantendo che l'interfaccia web e gli endpoint REST rimangano sempre reattivi al 100%.
- **Sicurezza Integrata Contro Path Traversal**: La distribuzione degli artefatti (`/results/`) è gestita tramite `StaticFiles` di Starlette con confinamento rigoroso nella cartella `scenarios/generated/`, impedendo attacchi LFI (Local File Inclusion).
- **Validazione dei Payload**: Le modifiche e i salvataggi dei file YAML (`/api/save`, `/api/generate`, `/api/run`) vengono convalidati preventivamente tramite modelli Pydantic.

### 8.1 Layout del Control Center

Il layout è organizzato in CSS Grid:
- **Header**: titolo e pulsanti di vista (Single 2D / Single 3D / Dual).
- **Sidebar sinistra (340 px)**: catalogo scenari, pulsanti di azione (Genera, Esegui, Analizza) e drawer inferiore.
- **Area principale**: mappa tattica 2D (Leaflet) e/o globo 3D (CesiumJS in iframe), a seconda della vista selezionata.
- **Drawer inferiore (45% dell'altezza)**: pannello estraibile con la dashboard esecutiva e i grafici di sintesi.

### 8.2 Vista Single 2D — Mappa Tattica Leaflet

La mappa 2D usa Leaflet 1.9.4 con basemap CARTO Dark / ESRI Dark Gray / ESRI Satellite. La chiave API CARTO viene iniettata dinamicamente nel placeholder `__CARTO_API_KEY__` al momento del servizio, evitando la dicitura "API key required".

Sulla mappa sono sovrapposti:
- **Confine geografico** dell'area dello scenario (rettangolo tratteggiato).
- **gNodeB** (marker arancione) con tooltip con potenza, frequenza, bandwidth.
- **Ground Station** (marker viola) con tooltip feeder/user link.
- **Satelliti visibili** (marker blu) con tooltip altitudine, inclinazione, piano orbitale.
- **Convoglio di veicoli animato**: un timer JavaScript sposta i marker dei veicoli lungo la traiettoria del percorso stradale, con un progresso sfasato per ciascun veicolo (`vIdx * 0.08`). Ogni marker mostra la RAT attiva:
  - **Verde** (`#10b981`) → 5G-NR Terrestrial.
  - **Ciano** (`#38bdf8`) → Satellite LEO NTN (quando il veicolo è in una zona d'ombra / blind spot).

### 8.3 Vista Single 3D — Globo CesiumJS

In questa vista l'area principale mostra il globo 3D (generato da `tools/czml_generator.py`). Il drawer inferiore è automaticamente richiuso per evitare sovrapposizioni.

### 8.4 Vista Dual — 2D + 3D affiancati

Selezionando **Dual**, la schermata si divide a metà:
- A sinistra: mappa 2D Leaflet.
- A destra: globo 3D CesiumJS.
- Il drawer inferiore si chiude automaticamente.
- Il pannello HUD del globo viene nascosto via `postMessage({ showHud: false })` e l'iframe viene caricato con `?hud=0`.

### 8.5 Drawer Inferiore — Dashboard Esecutiva

Il drawer inferiore (che si apre con il pulsante in basso) contiene la **dashboard esecutiva Chart.js** generata da `tools/dashboard.py`. È una griglia 2x2 con i grafici più utili per il monitoring in tempo reale:

| Grafico | Tipo | Cosa mostra |
| :--- | :--- | :--- |
| **Active Interface** | Area | Timeline dell'interfaccia attiva per ciascun veicolo (5G-NR vs Satellite LEO). |
| **QoS Utility Score** | Linea | Metrica di utilità di rete (0-1) che combina throughput, latenza e affidabilità. |
| **MEC Latency** | Barra | Latenza task di edge computing (upload + elaborazione + download). |
| **Cumulative Handovers** | Linea | Numero cumulativo di handover verticali nel tempo (make-before-break). |

Sotto la griglia sono presenti due sezioni di supporto:
- **Fleet Multi-RAT Telemetry Summary**: tabella riassuntiva per ciascun veicolo (RAT primaria, throughput, latenza, energia residua).
- **Physical Link Budget**: bilancio di link fisico (RSSI, SNR, attenuazione meteo, margine di link).

### 8.6 Customizer Parametri e Console di Esecuzione

La sidebar sinistra include slider grafici per:
- Tasso di pioggia (mm/h).
- Durata simulazione (s).
- Strategia VHO (coverage-based / qos-based / energy-aware).

La console di esecuzione in streaming mostra l'avanzamento (`ev/sec`, tempo simulato) con log terminale live.

---

## 9. Roadmap di Ricerca & Sviluppo (Horizon Europe NexaSphere)

- **Milestone 1**: Architettura modulare Conan 2 e mobilità unificata TN-NTN *(Completata)*.
- **Milestone 2**: CLI unificata e generatore procedurale reti microscopiche SUMO *(Completata)*.
- **Milestone 3**: Orchestrazione dinamica VHO e modulo Edge Computing MEC *(Completata)*.
- **Milestone 4**: Benchmark Suite (`sweep`), Digital Twin 3D CesiumJS (`view-3d`) e Web Studio (`studio`) *(Completata)*.
- **Milestone 5 (Pianificata)**: Routing multi-hop su maglia di satelliti ISL (Contact Graph Routing / Dijkstra dinamico spaziale).
- **Milestone 6 (Pianificata)**: Decision-making per VHO basato su Reinforcement Learning (Deep Q-Network).
- **Milestone 7 (Pianificata)**: Integrazione 5G-NR V2X Sidelink PC5 (3GPP Rel. 16/17) per Collective Perception cooperativa (CPM).

