# Wireframe Evolutivo: NexaSim Studio

## Obiettivi Migliorativi
1. **Layout Dinamico**: Migliorare la responsività con framework flessibili.
2. **Feedback Visivo**: Integrare interazioni dinamiche e transizioni fluide.
3. **Ottimizzazione Mobile**: Rendere l'interfaccia mobile-friendly con un design semplificato.

---

## Wireframe Proposto

### **Schermata Principale**
- **Header:** Titolo, Switcher per modalità (2D, 3D, Dual), pulsanti per scenario/caricamento.
- **Sidebar:**
  - **Sezioni:** Catalogo scenari, parametri configurabili, azioni "Genera/Esegui/Analizza".
  - **Drawer estraibile inferiore:** Telemetria e KPI visivi con barra grafici dinamici (Chart.js).
- **Sezione Centrale:**
  - Modalità 2D: Leaflet con mappe tattiche ottimizzate (CARTO/ESRI).
  - Modalità 3D: CesiumJS con globe viewer + widget interattivi (HUD on/off).
  - Modalità Dual: Divisore centrale flessibile tra mappa 2D e globo 3D.

---

## Designer Notes
1. **Leaflet:** Miglioramenti nei marker con interazioni al click/hover.
2. **CesiumJS:** Focus sui layer token security e fallback robusti offline.
3. **Compatibilità:** Bootstrap/Tailwind CSS per semplificare layout dinamico.

File wireframe dettagliato in attesa validazione UX debug stylesheets (se onboarding)!