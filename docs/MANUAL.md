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
4. [Analisi dei Dati e Metriche KPI (`analyze_results.py`)](#4-analisi-dei-dati-e-metriche-kpi)
5. [Visualizzazione Grafica della Rete e del Traffico (OMNeT++ Qtenv & SUMO-GUI)](#5-visualizzazione-grafica-della-rete-e-del-traffico-omnet-qtenv--sumo-gui)

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

## 3. Generazione ed Esecuzione degli Scenari

### 1. Compilare lo scenario da YAML a OMNeT++
```bash
python tools/gen_scenario.py scenarios/library/stelvio_pass_hybrid.yaml -o scenarios/generated/stelvio
```
Questo comando genererà:
- `scenario.ned`: Topologia dei moduli di rete 3D (Satelliti, gNodeB, UE, Ground Stations).
- `omnetpp.ini`: File di configurazione completo per il simulatore.
- `constellation.tle`: Effemeridi SGP4 per il calcolo delle orbite.
- `mobility.tcl`: Curve di movimento 3D dei veicoli.

### 2. Eseguire la simulazione
```bash
# Modalità headless rapida via Docker
docker compose run --rm nexasim-run opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Cmdenv

# Modalità grafica interattiva (Qtenv)
docker compose run --rm -e DISPLAY=$DISPLAY nexasim-run opp_run -l build/libartery_core.so -f scenarios/generated/stelvio/omnetpp.ini -u Qtenv
```

---

## 4. Analisi dei Dati e Metriche KPI (`analyze_results.py`)

Per analizzare le prestazioni della simulazione ed estrarre tutti i parametri di telemetria:

```bash
python tools/analyze_results.py scenarios/generated/stelvio
```

### Esempio di Report Generato:
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
  • Copertura Terrestre 5G-NR (Vetta/Valle): 34.5%
  • Copertura Satellitare LEO (Gole/Ombra):  52.0%
  • Copertura Dual-Connectivity (5G + LEO):  11.2%
  • Buco di Copertura / Outage (Pareti):     2.3%

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
