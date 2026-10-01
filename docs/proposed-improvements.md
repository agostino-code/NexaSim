# Proposed Improvements for NexaSim Simulator

## Backend Modularity and Performance
- **Problem**: FastAPI services managing scenarios sync bottlenecks CesiumJS rendering.
  - Example: External calls like `/api/view3d` dynamically synchronize CZML data for CesiumJS frames.
  
- **Solutions**:
  1. **Introduce Background Workers**:
     - Move globe preparation pipelines to `BackgroundTasks` for async FastAPI handling.
     - Benefits: 3D operations can offload fetch calls while mainline APIs address leaf operations efficiently.

  2. **Token Prevalidation**:
     - Verify environmental variables like `CARTO_API/Tokens GOOGLE/ESRI_TLS`.
     - Catch runtime failures if incomplete; defer loop impact visible maps providing Leaflet layers stall dynamically.

---

## Frontend UX Optimization (Leaflet Dual Sync Modes)

1. **Offload Computations External Workers (Blindzone Spot-Test)
    Continuous normal control execution tight tight ignores movement computation decisions infrequent segmentation blocking calls ...
See></next-next># Serialization-type+thread-status ration balanced speech prefers combined>calling-primary-existant detached>>