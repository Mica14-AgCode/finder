import streamlit as st
import pandas as pd
import math
import json
import base64
import os

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

# Inicializar variables de estado
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
if 'archivo_cargado' not in st.session_state:
    st.session_state.archivo_cargado = None
if 'radio_busqueda' not in st.session_state:
    st.session_state.radio_busqueda = 5.0
if 'mostrar_resultados' not in st.session_state:
    st.session_state.mostrar_resultados = False

# Funciones básicas para cálculos geoespaciales
def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """Calcula la distancia en kilómetros entre dos puntos usando la fórmula de Haversine"""
    # Radio de la Tierra en km
    R = 6371.0
    
    # Convertir coordenadas a radianes
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Diferencias de latitud y longitud
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia = R * c
    
    return distancia

# Función para cargar y procesar los datos
@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """Carga los datos de productores desde un archivo CSV"""
    try:
        # Verificar si el archivo existe
        if not os.path.exists(ruta_archivo):
            st.error(f"El archivo {ruta_archivo} no existe.")
            return crear_datos_ejemplo()
        
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        
        # Verificar las columnas necesarias
        columnas_requeridas = ['cuit', 'titular', 'latitud', 'longitud']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            st.error(f"El archivo CSV no contiene las columnas necesarias: {', '.join(columnas_faltantes)}")
            return crear_datos_ejemplo()
        
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return crear_datos_ejemplo()

def crear_datos_ejemplo():
    """Crea datos de ejemplo cuando no se puede cargar el CSV"""
    return pd.DataFrame({
        'cuit': ['20123456789', '30987654321'],
        'titular': ['Productor Ejemplo 1', 'Productor Ejemplo 2'],
        'renspa': ['12.345.6.78901/01', '98.765.4.32109/02'],
        'localidad': ['Localidad 1', 'Localidad 2'],
        'superficie': [100, 150],
        'longitud': [-60.0, -60.2],
        'latitud': [-34.0, -34.2],
        'poligono': [
            "POLYGON((-60.0 -34.0, -60.1 -34.0, -60.1 -34.1, -60.0 -34.1, -60.0 -34.0))",
            "POLYGON((-60.2 -34.2, -60.3 -34.2, -60.3 -34.3, -60.2 -34.3, -60.2 -34.2))"
        ]
    })

# Función para encontrar el CUIT más cercano a un punto
def encontrar_cuit_mas_cercano(lat, lon, datos):
    """Encuentra el CUIT más cercano a un punto dado"""
    distancia_min = float('inf')
    cuit_cercano = None
    
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            distancia = calcular_distancia_km(
                lat, lon, 
                fila['latitud'], fila['longitud']
            )
            
            if distancia < distancia_min:
                distancia_min = distancia
                cuit_cercano = {
                    'cuit': fila['cuit'],
                    'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                    'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                    'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                    'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                    'distancia': round(distancia, 2),
                    'latitud': fila['latitud'],
                    'longitud': fila['longitud'],
                    'poligono': fila['poligono'] if 'poligono' in fila else None,
                    'idx': int(idx)
                }
    
    return cuit_cercano

# Función para encontrar CUITs cercanos a un punto
def encontrar_cuits_cercanos(lat, lon, datos, radio_km=5):
    """
    Encuentra CUITs cercanos a un punto dado dentro de un radio específico.
    """
    cercanos = []
    
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            # Calcular distancia
            distancia = calcular_distancia_km(
                lat, lon, 
                fila['latitud'], fila['longitud']
            )
            
            if distancia <= radio_km:
                cercanos.append({
                    'cuit': fila['cuit'],
                    'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                    'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                    'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                    'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                    'distancia': round(distancia, 2),
                    'latitud': fila['latitud'],
                    'longitud': fila['longitud'],
                    'poligono': fila['poligono'] if 'poligono' in fila else None,
                    'idx': int(idx)
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Función para parsear polígonos WKT a coordenadas Leaflet
def wkt_a_coordenadas(wkt_str):
    """Convierte un string WKT de polígono a coordenadas Leaflet [[lat, lng], ...]"""
    if not wkt_str or not isinstance(wkt_str, str):
        return []
    
    try:
        # Extraer las coordenadas entre paréntesis (ignorando POLYGON, etc.)
        coords_str = wkt_str.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
        
        # Separar las coordenadas por coma
        coords_pares = coords_str.split(',')
        
        # Convertir a pares de [lat, lng] para Leaflet (invierte el orden)
        coords = []
        for par in coords_pares:
            valores = par.strip().split()
            if len(valores) >= 2:
                # En WKT es lon lat, pero en Leaflet necesitamos lat lon
                lon, lat = float(valores[0]), float(valores[1])
                coords.append([lat, lon])
        
        return coords
    except Exception as e:
        st.warning(f"Error al convertir polígono WKT: {e}")
        return []

# Mostrar mensaje de instrucciones
with st.sidebar:
    st.info(f"""
    **Instrucciones de configuración:**
    
    El archivo CSV con los datos de productores debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener al menos las columnas: 'cuit', 'titular', 'latitud', 'longitud'
    4. Opcionalmente: 'poligono' en formato WKT
    """)

# Cargar datos
datos_productores = cargar_datos()

# Crear un sidebar para filtros
st.sidebar.header("Filtros")

# Filtro por Razón Social (Titular)
if 'titular' in datos_productores.columns:
    titulares_disponibles = ["Todos"] + sorted(list(datos_productores['titular'].unique()))
    titular_seleccionado = st.sidebar.selectbox("Filtrar por Razón Social:", titulares_disponibles)
    
    if titular_seleccionado != "Todos":
        datos_filtrados = datos_productores[datos_productores['titular'] == titular_seleccionado]
    else:
        datos_filtrados = datos_productores
else:
    datos_filtrados = datos_productores
    st.sidebar.warning("No se encontró la columna 'titular' en los datos.")

# Radio de búsqueda como un solo campo editable sin límite
st.sidebar.subheader("Radio de búsqueda")
radio_busqueda = st.sidebar.number_input(
    "Radio de búsqueda (km):",
    min_value=0.1,
    value=st.session_state.radio_busqueda,
    step=0.1,
    format="%.1f"
)
st.session_state.radio_busqueda = radio_busqueda

# Opción para cargar archivos KML/KMZ/SHP
st.sidebar.header("Cargar archivos")
archivo_subido = st.sidebar.file_uploader(
    "Cargar archivo KML/KMZ/Shapefile", 
    type=["kml", "kmz", "shp", "zip"],
    help="Sube un archivo KML, KMZ o Shapefile (ZIP) para visualizarlo en el mapa"
)

if archivo_subido is not None:
    # Guardar el archivo en session_state para usarlo en el mapa
    bytes_data = archivo_subido.getvalue()
    # Convertir a base64 para pasar al JavaScript
    b64_data = base64.b64encode(bytes_data).decode()
    st.session_state.archivo_cargado = {
        "nombre": archivo_subido.name,
        "tipo": archivo_subido.type,
        "b64": b64_data
    }
    st.sidebar.success(f"Archivo cargado: {archivo_subido.name}")

# Layout principal
col1, col2 = st.columns([3, 1])

# Comprobar si hay parámetros de URL para las coordenadas
params = st.query_params
if "lat" in params and "lng" in params:
    try:
        lat = float(params["lat"][0])
        lng = float(params["lng"][0])
        st.session_state.punto_seleccionado = (lat, lng)
        st.session_state.busqueda_realizada = True
        st.session_state.mostrar_resultados = True
        # Limpiar los parámetros para evitar recargas duplicadas
        st.query_params.clear()
    except:
        pass

with col1:
    st.subheader("Mapa Interactivo")
    
    # Verificar que tenemos datos válidos para el mapa
    if not datos_filtrados.empty and 'latitud' in datos_filtrados.columns and 'longitud' in datos_filtrados.columns:
        # Calcular el centro del mapa
        centro_lat = datos_filtrados['latitud'].mean()
        centro_lon = datos_filtrados['longitud'].mean()
        
        # Preparar datos de polígonos si existen
        poligonos_data = []
        if 'poligono' in datos_filtrados.columns:
            for idx, fila in datos_filtrados.iterrows():
                if pd.notna(fila['poligono']):
                    coords = wkt_a_coordenadas(fila['poligono'])
                    if coords:
                        poligonos_data.append({
                            'coords': coords,
                            'cuit': fila['cuit'],
                            'titular': fila['titular'],
                            'idx': int(idx)
                        })
        
        # Convertir a JSON
        poligonos_json = json.dumps(poligonos_data)
        
        # JSON para colores de polígonos cercanos
        colors_json = json.dumps([
            "#3388ff", "#ff4433", "#33ff44", "#ff33ff", "#ffff33", 
            "#33ffff", "#ff8833", "#8833ff", "#88ff33", "#ff3388"
        ])
        
        # Verificar si hay un archivo KML/SHP cargado
        archivo_json = "null"
        if st.session_state.archivo_cargado:
            archivo_json = json.dumps(st.session_state.archivo_cargado)
        
        # Estado de búsqueda
        busqueda_realizada = "true" if st.session_state.busqueda_realizada else "false"
        
        # Código HTML y JavaScript para el mapa Leaflet
        mapa_html = f"""
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <style>
            #map {{
                width: 100%;
                height: 500px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                position: relative;
            }}
            #selected-coords {{
                margin-top: 10px;
                padding: 12px;
                background-color: #f8f9fa;
                border-radius: 8px;
                box-shadow: 0 0 5px rgba(0,0,0,0.05);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}
            #use-coords-btn {{
                padding: 10px 20px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                font-size: 16px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                transition: all 0.3s;
            }}
            #use-coords-btn:hover {{
                background-color: #45a049;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                transform: translateY(-2px);
            }}
            .coord-value {{
                font-weight: bold;
                color: #333;
            }}
            .search-control {{
                position: absolute;
                top: 10px;
                left: 50px;
                z-index: 1000;
                width: 300px;
            }}
            .search-input {{
                width: 100%;
                padding: 10px 15px;
                border-radius: 4px;
                border: 1px solid #ccc;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                font-size: 14px;
            }}
            .search-results {{
                display: none;
                background: white;
                max-height: 200px;
                overflow-y: auto;
                border-radius: 4px;
                margin-top: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            }}
            .search-result-item {{
                padding: 8px 12px;
                border-bottom: 1px solid #eee;
                cursor: pointer;
            }}
            .search-result-item:hover {{
                background-color: #f0f0f0;
            }}
            .log-panel {{
                position: fixed;
                bottom: 10px;
                right: 10px;
                width: 300px;
                height: 200px;
                background: rgba(0,0,0,0.8);
                color: #00ff00;
                font-family: monospace;
                padding: 10px;
                overflow: auto;
                z-index: 1000;
                display: none;
            }}
        </style>
        
        <div id="map">
            <div class="search-control">
                <input type="text" id="search-input" class="search-input" placeholder="Buscar ubicación...">
                <div id="search-results" class="search-results"></div>
            </div>
        </div>
        <div id="selected-coords">
            <div>
                <span>Coordenadas seleccionadas:</span>
                <span class="coord-value" id="selected-lat">-</span>, 
                <span class="coord-value" id="selected-lng">-</span>
            </div>
            <button id="use-coords-btn">🔍 USAR ESTAS COORDENADAS</button>
        </div>
        <div id="log-panel" class="log-panel"></div>
        
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script src="https://unpkg.com/@tmcw/togeojson/dist/togeojson.umd.js"></script>
        <script src="https://unpkg.com/shpjs@latest/dist/shp.js"></script>
        
        <script>
            // Función para agregar logs (ayuda en depuración)
            const DEBUG = true;
            const logPanel = document.getElementById('log-panel');
            
            function log(message) {{
                if (!DEBUG) return;
                
                if (typeof message === 'object') {{
                    message = JSON.stringify(message, null, 2);
                }}
                
                if (logPanel) {{
                    const logLine = document.createElement('div');
                    logLine.textContent = message;
                    logPanel.appendChild(logLine);
                    logPanel.scrollTop = logPanel.scrollHeight;
                }}
                
                console.log(message);
            }}
            
            // Mostrar panel de logs si se necesita depuración
            if (DEBUG) {{
                logPanel.style.display = 'block';
            }}
            
            // Inicializar el mapa
            log('Inicializando mapa...');
            const map = L.map('map', {{
                attributionControl: false  // Desactivar atribución para que no interfiera
            }}).setView([{centro_lat}, {centro_lon}], 9);
            
            // Agregar capa base de satélite (ESRI) por defecto
            const baseLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri'
            }}).addTo(map);
            
            // Agregar capa alternativa de OpenStreetMap
            const osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }});
            
            // Crear capas base para el control
            const baseMaps = {{
                "Satélite": baseLayer,
                "Mapa": osmLayer
            }};
            
            // Agregar control de capas (abajo a la izquierda)
            L.control.layers(baseMaps).setPosition('bottomleft').addTo(map);
            
            // Mover los controles de zoom abajo a la izquierda
            map.zoomControl.setPosition('bottomleft');
            
            // Agregar atribución en la esquina inferior derecha
            L.control.attribution({{
                position: 'bottomright',
                prefix: 'Leaflet | Tiles © Esri'
            }}).addTo(map);
            
            // Implementar búsqueda de ubicaciones
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');
            let searchTimeout;
            
            searchInput.addEventListener('input', function() {{
                clearTimeout(searchTimeout);
                const query = this.value.trim();
                
                if (query.length < 3) {{
                    searchResults.style.display = 'none';
                    return;
                }}
                
                searchTimeout = setTimeout(() => {{
                    log(`Buscando: ${{query}}`);
                    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${{encodeURIComponent(query)}}&countrycodes=ar&limit=5`)
                        .then(response => response.json())
                        .then(data => {{
                            searchResults.innerHTML = '';
                            
                            if (data.length === 0) {{
                                searchResults.style.display = 'none';
                                return;
                            }}
                            
                            log(`Resultados encontrados: ${{data.length}}`);
                            
                            data.forEach(result => {{
                                const item = document.createElement('div');
                                item.className = 'search-result-item';
                                item.textContent = result.display_name;
                                
                                item.addEventListener('mouseenter', function() {{
                                    this.style.backgroundColor = '#f0f0f0';
                                }});
                                
                                item.addEventListener('mouseleave', function() {{
                                    this.style.backgroundColor = '';
                                }});
                                
                                item.addEventListener('click', function() {{
                                    const lat = parseFloat(result.lat);
                                    const lon = parseFloat(result.lon);
                                    
                                    log(`Ubicación seleccionada: ${{lat}}, ${{lon}}`);
                                    
                                    // Actualizar el mapa
                                    map.setView([lat, lon], 13);
                                    
                                    // Actualizar el marcador
                                    if (puntoSeleccionado) {{
                                        map.removeLayer(puntoSeleccionado);
                                    }}
                                    
                                    puntoSeleccionado = L.marker([lat, lon], {{
                                        icon: L.icon({{
                                            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                                            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                                            iconSize: [25, 41],
                                            iconAnchor: [12, 41],
                                            popupAnchor: [1, -34],
                                            shadowSize: [41, 41]
                                        }})
                                    }}).addTo(map);
                                    
                                    // Actualizar coordenadas
                                    document.getElementById('selected-lat').textContent = lat.toFixed(4);
                                    document.getElementById('selected-lng').textContent = lon.toFixed(4);
                                    
                                    // Ocultar resultados
                                    searchResults.style.display = 'none';
                                    searchInput.value = result.display_name;
                                }});
                                
                                searchResults.appendChild(item);
                            }});
                            
                            searchResults.style.display = 'block';
                        }})
                        .catch(error => {{
                            log(`Error en la búsqueda: ${{error.message}}`);
                            searchResults.style.display = 'none';
                        }});
                }}, 300);
            }});
            
            // Ocultar resultados al hacer clic fuera
            document.addEventListener('click', function(e) {{
                if (e.target !== searchInput && e.target !== searchResults) {{
                    searchResults.style.display = 'none';
                }}
            }});
            
            // Variable para el marcador del punto seleccionado
            let puntoSeleccionado = null;
            
            // Colección de polígonos para los productores
            const poligonosLayer = L.layerGroup().addTo(map);
            
            // Capa para los archivos KML/Shapefile importados
            const archivosLayer = L.layerGroup().addTo(map);
            
            // Array de colores para polígonos
            const colors = {colors_json};
            
            // Función para dibujar polígonos de productores
            function dibujarPoligonos() {{
                log('Dibujando polígonos...');
                
                // Limpiar los polígonos existentes
                poligonosLayer.clearLayers();
                
                // Obtener los datos de polígonos
                const datos = {poligonos_json};
                
                log(`Polígonos a dibujar: ${{datos.length}}`);
                
                datos.forEach((poligono, index) => {{
                    const coords = poligono.coords;
                    if (coords && coords.length > 0) {{
                        // Usar el primer color por defecto
                        const poly = L.polygon(coords, {{
                            color: colors[0],
                            fillOpacity: 0.2,
                            weight: 2
                        }});
                        
                        // Agregar popup con información
                        poly.bindPopup(`
                            <strong>CUIT:</strong> ${{poligono.cuit}}<br>
                            <strong>Razón Social:</strong> ${{poligono.titular}}
                        `);
                        
                        // Guardar el índice para identificar el polígono
                        poly.idx = poligono.idx;
                        
                        // Agregar el polígono a la capa
                        poly.addTo(poligonosLayer);
                    }}
                }});
                
                log('Polígonos dibujados correctamente');
            }}
            
            // Función para colorear polígonos cercanos
            function colorearPoligonosCercanos(cercanos) {{
                log('Coloreando polígonos cercanos...');
                
                // Recorrer los polígonos en la capa
                poligonosLayer.eachLayer(layer => {{
                    // Verificar si es un polígono
                    if (layer instanceof L.Polygon) {{
                        // Color predeterminado (azul)
                        layer.setStyle({{ color: colors[0], fillOpacity: 0.2, weight: 2 }});
                        
                        // Buscar si este polígono está entre los cercanos
                        for (let i = 0; i < cercanos.length; i++) {{
                            if (layer.idx === cercanos[i].idx) {{
                                // Asignar un color diferente según la posición (hasta 10 colores)
                                const colorIdx = i % colors.length;
                                layer.setStyle({{ 
                                    color: colors[colorIdx], 
                                    fillColor: colors[colorIdx],
                                    fillOpacity: 0.3, 
                                    weight: 3
                                }});
                                break;
                            }}
                        }}
                    }}
                }});
                
                log('Polígonos cercanos coloreados correctamente');
            }}
            
            // Función para colorear el polígono más cercano
            function colorearPoligonoMasCercano(masCercano) {{
                if (!masCercano) return;
                
                log(`Coloreando polígono más cercano: ${{masCercano.idx}}`);
                
                poligonosLayer.eachLayer(layer => {{
                    if (layer instanceof L.Polygon && layer.idx === masCercano.idx) {{
                        layer.setStyle({{ 
                            color: '#ff0000', 
                            fillColor: '#ff0000',
                            fillOpacity: 0.4, 
                            weight: 4
                        }});
                        layer.bringToFront();
                    }}
                }});
            }}
            
            // Dibujar polígonos al cargar
            dibujarPoligonos();
            
            // Evento de clic en el mapa
            map.on('click', function(e) {{
                const lat = e.latlng.lat;
                const lng = e.latlng.lng;
                
                log(`Clic en el mapa: ${{lat}}, ${{lng}}`);
                
                // Actualizar el texto con las coordenadas (con menos decimales)
                document.getElementById('selected-lat').textContent = lat.toFixed(4);
                document.getElementById('selected-lng').textContent = lng.toFixed(4);
                
                // Si ya hay un marcador, eliminarlo
                if (puntoSeleccionado) {{
                    map.removeLayer(puntoSeleccionado);
                }}
                
                // Crear un nuevo marcador preciso (solo un punto, sin círculo)
                puntoSeleccionado = L.marker([lat, lng], {{
                    icon: L.icon({{
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    }})
                }}).addTo(map);
            }});
            
            // Evento para el botón de usar coordenadas
            document.getElementById('use-coords-btn').addEventListener('click', function() {{
                const lat = parseFloat(document.getElementById('selected-lat').textContent);
                const lng = parseFloat(document.getElementById('selected-lng').textContent);
                
                if (isNaN(lat) || isNaN(lng)) {{
                    log('Coordenadas inválidas');
                    return;
                }}
                
                log(`Usando coordenadas: ${{lat}}, ${{lng}}`);
                
                // Método 1: Recargar la página con parámetros
                const newUrl = new URL(window.location.href);
                newUrl.searchParams.set('lat', lat);
                newUrl.searchParams.set('lng', lng);
                
                log(`Redirigiendo a: ${{newUrl.toString()}}`);
                window.location.href = newUrl.toString();
            }});
            
            // Función para cargar archivo KML/KMZ/Shapefile
            function cargarArchivo(tipo, nombre, datos) {{
                log(`Cargando archivo: ${{nombre}}, tipo: ${{tipo}}`);
                
                try {{
                    // Limpiar la capa de archivos previos
                    archivosLayer.clearLayers();
                    
                    if (tipo.includes('kml') || tipo.includes('kmz')) {{
                        log('Procesando como KML/KMZ...');
                        
                        // Convertir de base64 a texto
                        const texto = atob(datos);
                        
                        // Crear un objeto DOM del KML
                        const parser = new DOMParser();
                        const kml = parser.parseFromString(texto, 'text/xml');
                        
                        log('Archivo KML parseado, convirtiendo a GeoJSON...');
                        
                        // Convertir a GeoJSON usando toGeoJSON
                        const geojson = toGeoJSON.kml(kml);
                        
                        log('GeoJSON generado correctamente');
                        
                        // Agregar al mapa
                        const kmlLayer = L.geoJSON(geojson, {{
                            style: function(feature) {{
                                return {{
                                    color: '#ff9900',
                                    weight: 3,
                                    opacity: 1,
                                    fillOpacity: 0.3,
                                    fillColor: '#ffcc33'
                                }};
                            }},
                            onEachFeature: function(feature, layer) {{
                                if (feature.properties && feature.properties.name) {{
                                    layer.bindPopup(feature.properties.name);
                                }}
                            }}
                        }}).addTo(archivosLayer);
                        
                        // Hacer zoom al extent
                        if (geojson.features && geojson.features.length > 0) {{
                            try {{
                                const bounds = L.geoJSON(geojson).getBounds();
                                map.fitBounds(bounds);
                                log('Zoom realizado al extent del KML');
                            }} catch (e) {{
                                log(`Error al hacer zoom: ${{e.message}}`);
                            }}
                        }}
                        
                    }} else if (tipo.includes('zip') || tipo.includes('shp')) {{
                        log('Procesando como Shapefile...');
                        
                        // Convertir base64 a ArrayBuffer
                        const binaryString = atob(datos);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {{
                            bytes[i] = binaryString.charCodeAt(i);
                        }}
                        const arrayBuffer = bytes.buffer;
                        
                        log(`ArrayBuffer creado: ${{arrayBuffer.byteLength}} bytes`);
                        
                        // Procesar Shapefile
                        shp(arrayBuffer)
                            .then(function(geojson) {{
                                log('GeoJSON generado desde Shapefile');
                                
                                // Agregar al mapa
                                const shpLayer = L.geoJSON(geojson, {{
                                    style: function(feature) {{
                                        return {{
                                            color: '#ff9900',
                                            weight: 3,
                                            opacity: 1,
                                            fillOpacity: 0.3,
                                            fillColor: '#ffcc33'
                                        }};
                                    }},
                                    onEachFeature: function(feature, layer) {{
                                        // Crear popup con propiedades
                                        if (feature.properties) {{
                                            let popupContent = '<div>';
                                            for (const key in feature.properties) {{
                                                const value = feature.properties[key];
                                                popupContent += `<b>${{key}}:</b> ${{value}}<br>`;
                                            }}
                                            popupContent += '</div>';
                                            layer.bindPopup(popupContent);
                                        }}
                                    }}
                                }}).addTo(archivosLayer);
                                
                                // Hacer zoom al extent
                                try {{
                                    const bounds = L.geoJSON(geojson).getBounds();
                                    map.fitBounds(bounds);
                                    log('Zoom realizado al extent del Shapefile');
                                }} catch (e) {{
                                    log(`Error al hacer zoom: ${{e.message}}`);
                                }}
                            }})
                            .catch(function(error) {{
                                log(`Error al procesar Shapefile: ${{error.message}}`);
                            }});
                    }}
                }} catch (error) {{
                    log(`Error al cargar archivo: ${{error.message}}`);
                }}
            }}
            
            // Cargar archivo si existe
            const archivoData = {archivo_json};
            if (archivoData && archivoData.nombre) {{
                log(`Archivo detectado: ${{archivoData.nombre}}`);
                cargarArchivo(archivoData.tipo, archivoData.nombre, archivoData.b64);
            }}
            
            // Si hay un punto seleccionado previamente, mostrarlo
            {f"const lat = {st.session_state.punto_seleccionado[0]}; const lng = {st.session_state.punto_seleccionado[1]};" if st.session_state.punto_seleccionado else ""}
            {"""
            if (lat && lng) {
                log(`Punto guardado: ${lat}, ${lng}`);
                
                // Crear marcador para el punto guardado
                puntoSeleccionado = L.marker([lat, lng], {
                    icon: L.icon({
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    })
                }).addTo(map);
                
                // Actualizar texto de coordenadas
                document.getElementById('selected-lat').textContent = lat.toFixed(4);
                document.getElementById('selected-lng').textContent = lng.toFixed(4);
                
                // Centrar el mapa en el punto guardado
                map.setView([lat, lng], 15);
            }
            """ if st.session_state.punto_seleccionado else ""}
            
            // Verificar si se ha realizado una búsqueda
            const busquedaRealizada = {busqueda_realizada};
            if (busquedaRealizada) {{
                log('Búsqueda realizada, enviando mensaje para actualizar polígonos');
                
                // Enviar mensaje para actualizar polígonos cercanos
                window.parent.postMessage({{
                    type: 'busqueda_realizada'
                }}, '*');
            }}
        </script>
        """
        
        # Mostrar el mapa con Leaflet
        components_result = st.components.v1.html(mapa_html, height=600)
        
    else:
        st.warning("No hay datos de ubicación disponibles para mostrar en el mapa.")

# Panel de resultados
with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si hay un punto seleccionado
    if st.session_state.busqueda_realizada and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        st.write(f"**Coordenadas del punto:** Lat {lat:.4f}, Lng {lon:.4f}")
        
        # Buscar el CUIT más cercano
        cuit_mas_cercano = encontrar_cuit_mas_cercano(lat, lon, datos_filtrados)
        
        # Buscar CUITs cercanos
        cuits_cercanos = encontrar_cuits_cercanos(lat, lon, datos_filtrados, radio_km=radio_busqueda)
        
        # Enviar datos de polígonos cercanos al mapa
        if cuit_mas_cercano or (cuits_cercanos and len(cuits_cercanos) > 0):
            # Marcar que hay resultados para mostrar
            st.session_state.mostrar_resultados = True
            
            # Crear JavaScript para actualizar el mapa
            update_js = f"""
            <script>
            // Enviar datos al mapa
            try {{
                window.parent.postMessage({{
                    type: 'cercanos',
                    cercanos: {json.dumps(cuits_cercanos)},
                    masCercano: {json.dumps(cuit_mas_cercano) if cuit_mas_cercano else 'null'}
                }}, '*');
                console.log('Datos de polígonos enviados correctamente');
            }} catch (e) {{
                console.error('Error al enviar datos de polígonos:', e);
            }}
            </script>
            """
            st.components.v1.html(update_js, height=0)
        
        if cuit_mas_cercano:
            st.success("**Productor más cercano:**")
            st.markdown(f"""
            **CUIT:** {cuit_mas_cercano['cuit']}  
            **Razón Social:** {cuit_mas_cercano['titular']}  
            **RENSPA:** {cuit_mas_cercano.get('renspa', 'No disponible')}  
            **Localidad:** {cuit_mas_cercano.get('localidad', 'No disponible')}  
            **Superficie:** {cuit_mas_cercano.get('superficie', 'No disponible')} ha  
            **Distancia:** {cuit_mas_cercano['distancia']} km  
            """)
        
        if cuits_cercanos:
            st.subheader(f"Productores cercanos (radio {radio_busqueda} km):")
            
            # Mostrar número de productores encontrados
            st.info(f"Se encontraron {len(cuits_cercanos)} productores cercanos.")
            
            # Tabla resumida
            tabla_datos = []
            for cercano in cuits_cercanos:
                tabla_datos.append({
                    "CUIT": cercano['cuit'],
                    "Razón Social": cercano['titular'][:20] + "..." if len(cercano['titular']) > 20 else cercano['titular'],
                    "Km": cercano['distancia']
                })
            
            st.dataframe(pd.DataFrame(tabla_datos), use_container_width=True)
            
            # Detalles expandibles
            for i, cercano in enumerate(cuits_cercanos[:5]):  # Mostrar los 5 más cercanos
                with st.expander(f"{i+1}. {cercano['titular']} ({cercano['distancia']} km)"):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Razón Social:** {cercano['titular']}  
                    **RENSPA:** {cercano.get('renspa', 'No disponible')}  
                    **Localidad:** {cercano.get('localidad', 'No disponible')}  
                    **Superficie:** {cercano.get('superficie', 'No disponible')} ha  
                    **Distancia:** {cercano['distancia']} km  
                    **Coordenadas:** Lat {cercano['latitud']:.4f}, Lng {cercano['longitud']:.4f}
                    """)
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("👈 Haz clic en el mapa y presiona 'USAR ESTAS COORDENADAS' para ver resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Buscar localidad**: Usa la barra de búsqueda en la parte superior izquierda del mapa.
2. **Selección en mapa**: Haz clic en cualquier punto del mapa.
3. **Usar coordenadas**: Haz clic en el botón "USAR ESTAS COORDENADAS" para consultar el punto seleccionado.
4. **Resultados**: Verás el productor más cercano y todos los que estén dentro del radio especificado.
5. **Filtros**: Usa el filtro por Razón Social para mostrar productores específicos.
6. **Radio de búsqueda**: Ingresa directamente el radio de búsqueda deseado (en kilómetros).
7. **Carga de archivos**: Sube archivos KML, KMZ o Shapefile desde el panel lateral para visualizarlos en el mapa.
""")
