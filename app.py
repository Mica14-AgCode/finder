import streamlit as st
import pandas as pd
import math
import json
import base64
import os
from io import StringIO

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
    st.session_state.radio_busqueda = 200.0  # Radio predeterminado ampliado a 200 km
if 'modo_debug' not in st.session_state:
    st.session_state.modo_debug = True
if 'resultado_busqueda' not in st.session_state:
    st.session_state.resultado_busqueda = None
if 'cuits_cercanos' not in st.session_state:
    st.session_state.cuits_cercanos = []

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

def punto_en_poligono(latitud, longitud, poligono_wkt):
    """
    Verifica si un punto está dentro de un polígono WKT.
    Implementación simple del algoritmo de "ray casting".
    """
    if not poligono_wkt or not isinstance(poligono_wkt, str):
        return False
    
    try:
        # Extraer las coordenadas del polígono WKT
        coords_str = poligono_wkt.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
        
        # Separar las coordenadas por coma
        coords_pares = coords_str.split(',')
        
        # Convertir a pares de (lon, lat)
        vertices = []
        for par in coords_pares:
            valores = par.strip().split()
            if len(valores) >= 2:
                lon, lat = float(valores[0]), float(valores[1])
                vertices.append((lon, lat))
        
        # Algoritmo de ray casting
        inside = False
        n = len(vertices)
        
        # Si no hay suficientes vértices, no es un polígono válido
        if n < 3:
            return False
        
        j = n - 1
        for i in range(n):
            # Comprobación de si el punto está dentro usando ray casting
            if ((vertices[i][1] > latitud) != (vertices[j][1] > latitud)) and \
               (longitud < (vertices[j][0] - vertices[i][0]) * (latitud - vertices[i][1]) / (vertices[j][1] - vertices[i][1]) + vertices[i][0]):
                inside = not inside
            j = i
        
        if st.session_state.modo_debug and inside:
            st.write(f"Punto ({latitud}, {longitud}) está DENTRO del polígono")
        
        return inside
    except Exception as e:
        if st.session_state.modo_debug:
            st.warning(f"Error al verificar si el punto está en el polígono: {e}")
        return False

def wkt_a_coordenadas(wkt_str):
    """Convierte un string WKT de polígono a coordenadas [[lat, lng], ...]"""
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
        if st.session_state.modo_debug:
            st.warning(f"Error al convertir polígono WKT: {e}")
        return []

def calcular_centroide(poligono_coords):
    """Calcula el centroide de un polígono"""
    if not poligono_coords or len(poligono_coords) < 3:
        return None
    
    # Calcular el centroide como promedio de las coordenadas
    lat_sum = sum(coord[0] for coord in poligono_coords)
    lon_sum = sum(coord[1] for coord in poligono_coords)
    
    return [lat_sum / len(poligono_coords), lon_sum / len(poligono_coords)]

def crear_datos_ejemplo():
    """Crea datos de ejemplo cuando no se puede cargar el CSV"""
    st.warning("Usando datos de ejemplo para demostración")
    return pd.DataFrame({
        'cuit': ['20123456789', '30987654321', '33444555667', '27888999001'],
        'titular': ['Productor Ejemplo 1', 'Productor Ejemplo 2', 'Productor Ejemplo 3', 'Productor Ejemplo 4'],
        'renspa': ['12.345.6.78901/01', '98.765.4.32109/02', '11.222.3.33333/03', '44.555.6.66666/04'],
        'localidad': ['Localidad 1', 'Localidad 2', 'Localidad 3', 'Localidad 4'],
        'superficie': [100, 150, 200, 75],
        'longitud': [-60.0, -60.2, -60.1, -59.9],
        'latitud': [-34.0, -34.2, -34.1, -33.9],
        'poligono': [
            "POLYGON((-60.0 -34.0, -60.1 -34.0, -60.1 -34.1, -60.0 -34.1, -60.0 -34.0))",
            "POLYGON((-60.2 -34.2, -60.3 -34.2, -60.3 -34.3, -60.2 -34.3, -60.2 -34.2))",
            "POLYGON((-60.1 -34.1, -60.2 -34.1, -60.2 -34.2, -60.1 -34.2, -60.1 -34.1))",
            "POLYGON((-59.9 -33.9, -60.0 -33.9, -60.0 -34.0, -59.9 -34.0, -59.9 -33.9))"
        ]
    })

# Función para cargar y procesar los datos
@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """Carga los datos de productores desde un archivo CSV"""
    try:
        # Verificar si el archivo existe
        if not os.path.exists(ruta_archivo):
            st.error(f"El archivo {ruta_archivo} no existe. Usando datos de ejemplo.")
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

# Función para encontrar el productor cuyo polígono contiene el punto
def encontrar_productor_contenedor(lat, lon, datos):
    """Encuentra el productor cuyo polígono contiene el punto dado"""
    productor_contenedor = None
    
    for idx, fila in datos.iterrows():
        if 'poligono' in fila and pd.notna(fila['poligono']):
            if punto_en_poligono(lat, lon, fila['poligono']):
                productor_contenedor = {
                    'cuit': fila['cuit'],
                    'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                    'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                    'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                    'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                    'distancia': 0,  # Distancia 0 porque está dentro del polígono
                    'latitud': fila['latitud'],
                    'longitud': fila['longitud'],
                    'poligono': fila['poligono'],
                    'idx': int(idx),
                    'contenedor': True
                }
                break
    
    return productor_contenedor

# Función para encontrar el CUIT más cercano a un punto
def encontrar_cuit_mas_cercano(lat, lon, datos):
    """Encuentra el CUIT más cercano a un punto dado"""
    # Primero verificar si el punto está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        return productor_contenedor
    
    # Si no está dentro de ningún polígono, buscar el más cercano
    distancia_min = float('inf')
    cuit_cercano = None
    
    # Para depuración
    if st.session_state.modo_debug:
        st.write(f"Buscando el CUIT más cercano al punto ({lat}, {lon})")
        st.write(f"Total de registros en datos: {len(datos)}")
    
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
                    'idx': int(idx),
                    'contenedor': False
                }
    
    # Para depuración
    if st.session_state.modo_debug:
        if cuit_cercano:
            st.write(f"CUIT más cercano encontrado: {cuit_cercano['cuit']} a {cuit_cercano['distancia']} km")
        else:
            st.write("No se encontró ningún CUIT cercano")
        
    return cuit_cercano

# Función para encontrar CUITs cercanos a un punto
def encontrar_cuits_cercanos(lat, lon, datos, radio_km=5):
    """
    Encuentra CUITs cercanos a un punto dado dentro de un radio específico.
    """
    cercanos = []
    
    # Primero verificar si está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        cercanos.append(productor_contenedor)
        if st.session_state.modo_debug:
            st.success(f"El punto está dentro del polígono de: {productor_contenedor['titular']}")
    
    # Buscar otros productores cercanos por distancia
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            # Si ya encontramos que este productor contiene el punto, saltarlo
            if productor_contenedor and int(idx) == productor_contenedor['idx']:
                continue
                
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
                    'idx': int(idx),
                    'contenedor': False
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    # Para depuración
    if st.session_state.modo_debug:
        if cercanos:
            st.success(f"Se encontraron {len(cercanos)} productores dentro del radio de {radio_km} km")
        else:
            st.warning(f"No se encontró ningún productor dentro del radio de {radio_km} km")
    
    return cercanos

# Preparar datos de polígonos para Leaflet
def preparar_poligonos_para_mapa(datos_filtrados):
    """Prepara los datos de polígonos para mostrarlos en el mapa"""
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
    
    return poligonos_data

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

# Agregar un toggle para el modo de depuración en el sidebar
st.sidebar.subheader("Modo depuración")
modo_debug = st.sidebar.checkbox("Activar modo depuración", value=st.session_state.modo_debug)
st.session_state.modo_debug = modo_debug

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
    max_value=500.0,
    value=st.session_state.radio_busqueda,
    step=1.0,
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

# Si tenemos un punto seleccionado, realizar la búsqueda
if st.session_state.busqueda_realizada and st.session_state.punto_seleccionado:
    lat, lon = st.session_state.punto_seleccionado
    
    # Buscar el CUIT más cercano y guardar el resultado
    st.session_state.resultado_busqueda = encontrar_cuit_mas_cercano(lat, lon, datos_filtrados)
    
    # Buscar CUITs cercanos
    st.session_state.cuits_cercanos = encontrar_cuits_cercanos(lat, lon, datos_filtrados, radio_km=radio_busqueda)

with col1:
    st.subheader("Mapa Interactivo")
    
    # Preparar datos para el mapa
    poligonos_data = preparar_poligonos_para_mapa(datos_filtrados)
    
    # Convertir a JSON
    poligonos_json = json.dumps(poligonos_data)
    
    # JSON para colores de polígonos
    colors_json = json.dumps([
        "#3388ff", "#ff4433", "#33ff44", "#ff33ff", "#ffff33", 
        "#33ffff", "#ff8833", "#8833ff", "#88ff33", "#ff3388"
    ])
    
    # Estado de búsqueda y resultado
    busqueda_realizada = "true" if st.session_state.busqueda_realizada else "false"
    resultado_json = "null"
    if st.session_state.resultado_busqueda:
        resultado_json = json.dumps(st.session_state.resultado_busqueda)
    
    cuits_cercanos_json = "[]"
    if st.session_state.cuits_cercanos:
        cuits_cercanos_json = json.dumps(st.session_state.cuits_cercanos)
    
    # Archivo cargado
    archivo_json = "null"
    if st.session_state.archivo_cargado:
        archivo_json = json.dumps(st.session_state.archivo_cargado)
    
    # Centro del mapa
    if datos_filtrados.empty:
        centro_lat = -34.0
        centro_lon = -60.0
    else:
        centro_lat = datos_filtrados['latitud'].mean()
        centro_lon = datos_filtrados['longitud'].mean()
    
    # Coordenadas del punto seleccionado
    punto_seleccionado_json = "null"
    if st.session_state.punto_seleccionado:
        punto_seleccionado_json = json.dumps(st.session_state.punto_seleccionado)
    
    # Contenido HTML para el mapa Leaflet
    mapa_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <style>
            #map {{
                width: 100%;
                height: 500px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            #info-panel {{
                margin-top: 10px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 8px;
                box-shadow: 0 0 5px rgba(0,0,0,0.1);
            }}
            .coord-value {{
                font-weight: bold;
                color: #333;
            }}
            #use-coords-btn {{
                margin-top: 10px;
                padding: 8px 16px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
            }}
            #use-coords-btn:hover {{
                background-color: #45a049;
            }}
            .status-message {{
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                padding: 15px 25px;
                background-color: rgba(0, 0, 0, 0.8);
                color: #fff;
                border-radius: 5px;
                z-index: 2000;
                display: none;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div id="info-panel">
            <div>Coordenadas seleccionadas: <span id="coords-display">Haz clic en el mapa</span></div>
            <button id="use-coords-btn">Buscar en estas coordenadas</button>
        </div>
        <div id="status-message" class="status-message"></div>
        
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script src="https://unpkg.com/@tmcw/togeojson@4.6.0/dist/togeojson.umd.js"></script>
        <script src="https://unpkg.com/shpjs@latest/dist/shp.js"></script>
        
        <script>
            // Variables globales
            let map;
            let markerLayer = null;
            let poligonosLayer = null;
            let archivosLayer = null;
            let selectedCoords = null;
            
            // Función para mostrar mensajes de estado
            function showMessage(message, duration = 3000) {{
                const msgEl = document.getElementById('status-message');
                msgEl.textContent = message;
                msgEl.style.display = 'block';
                
                setTimeout(() => {{
                    msgEl.style.display = 'none';
                }}, duration);
            }}
            
            // Función para inicializar el mapa
            function initMap() {{
                // Crear el mapa
                map = L.map('map').setView([{centro_lat}, {centro_lon}], 9);
                
                // Agregar capa base - Satélite
                const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Tiles &copy; Esri'
                }});
                
                // Agregar capa base - OpenStreetMap
                const osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }});
                
                // Agregar capas al mapa
                satelliteLayer.addTo(map);
                
                // Configurar control de capas
                const baseMaps = {{
                    "Satélite": satelliteLayer,
                    "Mapa": osmLayer
                }};
                
                L.control.layers(baseMaps).addTo(map);
                
                // Capas para marcadores y polígonos
                markerLayer = L.layerGroup().addTo(map);
                poligonosLayer = L.layerGroup().addTo(map);
                archivosLayer = L.layerGroup().addTo(map);
                
                // Dibujar polígonos de productores
                dibujarPoligonos();
                
                // Evento de clic en el mapa
                map.on('click', function(e) {{
                    const lat = e.latlng.lat;
                    const lng = e.latlng.lng;
                    
                    // Actualizar coordenadas seleccionadas
                    selectedCoords = [lat, lng];
                    document.getElementById('coords-display').textContent = `Lat: ${{lat.toFixed(6)}}, Lng: ${{lng.toFixed(6)}}`;
                    
                    // Actualizar marcador
                    markerLayer.clearLayers();
                    L.marker([lat, lng]).addTo(markerLayer);
                    
                    showMessage(`Punto seleccionado: ${{lat.toFixed(6)}}, ${{lng.toFixed(6)}}`);
                }});
                
                // Evento para botón de búsqueda
                document.getElementById('use-coords-btn').addEventListener('click', function() {{
                    if (!selectedCoords) {{
                        showMessage('Error: Primero selecciona un punto en el mapa', 3000);
                        return;
                    }}
                    
                    // Enviar mensaje para buscar
                    window.parent.postMessage({{
                        type: 'coordenadas_seleccionadas',
                        coords: selectedCoords
                    }}, '*');
                    
                    showMessage('Buscando productores cercanos...', 2000);
                }});
                
                // Cargar archivos si hay alguno
                cargarArchivo();
                
                // Si hay un punto seleccionado previamente, mostrarlo
                const puntoSeleccionado = {punto_seleccionado_json};
                if (puntoSeleccionado) {{
                    const [lat, lng] = puntoSeleccionado;
                    selectedCoords = [lat, lng];
                    document.getElementById('coords-display').textContent = `Lat: ${{lat.toFixed(6)}}, Lng: ${{lng.toFixed(6)}}`;
                    L.marker([lat, lng]).addTo(markerLayer);
                    map.setView([lat, lng], 13);
                }}
                
                // Si hay resultados de búsqueda, mostrarlos
                const busquedaRealizada = {busqueda_realizada};
                if (busquedaRealizada) {{
                    mostrarResultadosBusqueda();
                }}
            }}
            
            // Función para dibujar polígonos de productores
            function dibujarPoligonos() {{
                // Limpiar capa de polígonos
                poligonosLayer.clearLayers();
                
                // Datos de polígonos y colores
                const poligonos = {poligonos_json};
                const colors = {colors_json};
                
                // Dibujar cada polígono
                poligonos.forEach((poligono, index) => {{
                    if (poligono.coords && poligono.coords.length > 0) {{
                        const poly = L.polygon(poligono.coords, {{
                            color: colors[0],
                            fillOpacity: 0.2,
                            weight: 2
                        }});
                        
                        // Agregar popup con información
                        poly.bindPopup(`
                            <strong>CUIT:</strong> ${{poligono.cuit}}<br>
                            <strong>Razón Social:</strong> ${{poligono.titular}}
                        `);
                        
                        // Guardar el índice para identificación
                        poly.idx = poligono.idx;
                        
                        // Agregar al mapa
                        poly.addTo(poligonosLayer);
                    }}
                }});
            }}
            
            // Función para cargar y mostrar archivos KML/KMZ/SHP
            function cargarArchivo() {{
                const archivoData = {archivo_json};
                if (!archivoData) return;
                
                try {{
                    // Limpiar capa de archivos
                    archivosLayer.clearLayers();
                    
                    // Convertir base64 a datos binarios
                    const binaryString = atob(archivoData.b64);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {{
                        bytes[i] = binaryString.charCodeAt(i);
                    }}
                    
                    // Procesar según el tipo de archivo
                    if (archivoData.tipo.includes('kml') || archivoData.tipo.includes('kmz')) {{
                        // Procesar KML
                        const kmlText = new TextDecoder().decode(bytes);
                        const parser = new DOMParser();
                        const kml = parser.parseFromString(kmlText, 'text/xml');
                        const geojson = toGeoJSON.kml(kml);
                        
                        // Crear capa GeoJSON
                        const kmlLayer = L.geoJSON(geojson, {{
                            style: {{
                                color: '#ff9900',
                                weight: 3,
                                opacity: 1,
                                fillOpacity: 0.3,
                                fillColor: '#ffcc33'
                            }},
                            onEachFeature: function(feature, layer) {{
                                // Contenido del popup
                                let popupContent = '<div>';
                                
                                if (feature.properties) {{
                                    if (feature.properties.name) {{
                                        popupContent += `<strong>Nombre:</strong> ${{feature.properties.name}}<br>`;
                                    }}
                                    if (feature.properties.description) {{
                                        popupContent += `<strong>Descripción:</strong> ${{feature.properties.description}}<br>`;
                                    }}
                                }}
                                
                                // Botón para usar el centroide
                                popupContent += `<button id="usar-centroide" 
                                                style="background-color:#4CAF50; color:white; border:none; 
                                                padding:5px 10px; border-radius:4px; cursor:pointer; margin-top:5px">
                                            Usar centroide como referencia
                                        </button>`;
                                
                                popupContent += '</div>';
                                
                                layer.bindPopup(popupContent);
                                
                                // Evento para cuando se abre el popup
                                layer.on('popupopen', function(e) {{
                                    setTimeout(() => {{
                                        document.getElementById('usar-centroide').addEventListener('click', function() {{
                                            // Calcular centroide del polígono
                                            let centroide;
                                            if (layer instanceof L.Polygon) {{
                                                centroide = layer.getCenter();
                                            }} else if (layer.getBounds) {{
                                                centroide = layer.getBounds().getCenter();
                                            }} else {{
                                                showMessage('No se puede calcular el centroide para este elemento', 3000);
                                                return;
                                            }}
                                            
                                            // Seleccionar el centroide
                                            selectedCoords = [centroide.lat, centroide.lng];
                                            document.getElementById('coords-display').textContent = 
                                                `Lat: ${{centroide.lat.toFixed(6)}}, Lng: ${{centroide.lng.toFixed(6)}}`;
                                            
                                            // Actualizar marcador
                                            markerLayer.clearLayers();
                                            L.marker([centroide.lat, centroide.lng]).addTo(markerLayer);
                                            
                                            // Cerrar popup
                                            layer.closePopup();
                                            
                                            showMessage(`Centroide seleccionado: ${{centroide.lat.toFixed(6)}}, ${{centroide.lng.toFixed(6)}}`);
                                        }});
                                    }}, 100);
                                }});
                            }}
                        }}).addTo(archivosLayer);
                        
                        // Hacer zoom al extent
                        try {{
                            const bounds = L.geoJSON(geojson).getBounds();
                            map.fitBounds(bounds);
                        }} catch (e) {{
                            console.error('Error al hacer zoom:', e);
                        }}
                        
                        showMessage(`Archivo KML cargado: ${{archivoData.nombre}}`, 3000);
                    }} else if (archivoData.tipo.includes('zip') || archivoData.tipo.includes('shp')) {{
                        // Procesar Shapefile
                        const arrayBuffer = bytes.buffer;
                        
                        // Usar shpjs para procesar el shapefile
                        shp(arrayBuffer)
                            .then(function(geojson) {{
                                const shpLayer = L.geoJSON(geojson, {{
                                    style: {{
                                        color: '#ff9900',
                                        weight: 3,
                                        opacity: 1,
                                        fillOpacity: 0.3,
                                        fillColor: '#ffcc33'
                                    }},
                                    onEachFeature: function(feature, layer) {{
                                        // Contenido del popup
                                        let popupContent = '<div>';
                                        
                                        if (feature.properties) {{
                                            for (const key in feature.properties) {{
                                                const value = feature.properties[key];
                                                if (value !== null && value !== undefined) {{
                                                    popupContent += `<strong>${{key}}:</strong> ${{value}}<br>`;
                                                }}
                                            }}
                                        }}
                                        
                                        // Botón para usar el centroide
                                        popupContent += `<button id="usar-centroide" 
                                                        style="background-color:#4CAF50; color:white; border:none; 
                                                        padding:5px 10px; border-radius:4px; cursor:pointer; margin-top:5px">
                                                    Usar centroide como referencia
                                                </button>`;
                                        
                                        popupContent += '</div>';
                                        
                                        layer.bindPopup(popupContent);
                                        
                                        // Evento para cuando se abre el popup
                                        layer.on('popupopen', function(e) {{
                                            setTimeout(() => {{
                                                document.getElementById('usar-centroide').addEventListener('click', function() {{
                                                    // Calcular centroide del polígono
                                                    let centroide;
                                                    if (layer instanceof L.Polygon) {{
                                                        centroide = layer.getCenter();
                                                    }} else if (layer.getBounds) {{
                                                        centroide = layer.getBounds().getCenter();
                                                    }} else {{
                                                        showMessage('No se puede calcular el centroide para este elemento', 3000);
                                                        return;
                                                    }}
                                                    
                                                    // Seleccionar el centroide
                                                    selectedCoords = [centroide.lat, centroide.lng];
                                                    document.getElementById('coords-display').textContent = 
                                                        `Lat: ${{centroide.lat.toFixed(6)}}, Lng: ${{centroide.lng.toFixed(6)}}`;
                                                    
                                                    // Actualizar marcador
                                                    markerLayer.clearLayers();
                                                    L.marker([centroide.lat, centroide.lng]).addTo(markerLayer);
                                                    
                                                    // Cerrar popup
                                                    layer.closePopup();
                                                    
                                                    showMessage(`Centroide seleccionado: ${{centroide.lat.toFixed(6)}}, ${{centroide.lng.toFixed(6)}}`);
                                                }});
                                            }}, 100);
                                        }});
                                    }}
                                }}).addTo(archivosLayer);
                                
                                // Hacer zoom al extent
                                try {{
                                    const bounds = L.geoJSON(geojson).getBounds();
                                    map.fitBounds(bounds);
                                }} catch (e) {{
                                    console.error('Error al hacer zoom:', e);
                                }}
                                
                                showMessage(`Archivo Shapefile cargado: ${{archivoData.nombre}}`, 3000);
                            }})
                            .catch(function(error) {{
                                console.error('Error al procesar Shapefile:', error);
                                showMessage(`Error al procesar el Shapefile: ${{error.message}}`, 5000);
                            }});
                    }}
                }} catch (error) {{
                    console.error('Error al cargar archivo:', error);
                    showMessage(`Error al cargar el archivo: ${{error.message}}`, 5000);
                }}
            }}
            
            // Función para mostrar los resultados de búsqueda en el mapa
            function mostrarResultadosBusqueda() {{
                const resultado = {resultado_json};
                const cuitsCercanos = {cuits_cercanos_json};
                
                if (!resultado && (!cuitsCercanos || cuitsCercanos.length === 0)) {{
                    return;
                }}
                
                // Colorear polígonos cercanos
                poligonosLayer.eachLayer(layer => {{
                    if (layer instanceof L.Polygon) {{
                        // Resetear estilo
                        layer.setStyle({{ 
                            color: '#3388ff', 
                            fillOpacity: 0.2, 
                            weight: 2 
                        }});
                        
                        // Verificar si es el más cercano
                        if (resultado && layer.idx === resultado.idx) {{
                            layer.setStyle({{ 
                                color: '#ff0000', 
                                fillColor: '#ff0000',
                                fillOpacity: 0.4, 
                                weight: 4
                            }});
                            layer.bringToFront();
                            
                            // Si contiene el punto, hacer zoom al polígono
                            if (resultado.contenedor) {{
                                try {{
                                    map.fitBounds(layer.getBounds());
                                }} catch (e) {{
                                    console.error('Error al hacer zoom al polígono:', e);
                                }}
                            }}
                        }}
                        
                        // Verificar si está entre los cercanos
                        cuitsCercanos.forEach((cercano, index) => {{
                            if (layer.idx === cercano.idx && (!resultado || layer.idx !== resultado.idx)) {{
                                const colorIdx = index % 10; // Usar índice para el color
                                layer.setStyle({{ 
                                    color: '#ff9900', 
                                    fillColor: '#ffcc33',
                                    fillOpacity: 0.3, 
                                    weight: 3
                                }});
                            }}
                        }});
                    }}
                }});
            }}
            
            // Inicializar el mapa cuando cargue la página
            document.addEventListener('DOMContentLoaded', initMap);
            
            // Escuchar mensajes del parent
            window.addEventListener('message', function(event) {{
                if (event.data && event.data.type === 'refresh_map') {{
                    mostrarResultadosBusqueda();
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    # Mostrar el mapa
    st.components.v1.html(mapa_html, height=600, scrolling=False)
    
    # Escuchar mensajes del mapa simplificado con función de retrollamada
    components.html(
        """
        <script>
        // Función para escuchar mensajes del mapa
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'coordenadas_seleccionadas') {
                var coords = event.data.coords;
                console.log('Coordenadas recibidas:', coords);
                
                // Intentar todas las formas posibles de enviar el mensaje a Streamlit
                try {
                    if (window.parent && window.parent.Streamlit) {
                        // Método oficial de Streamlit
                        window.parent.Streamlit.setComponentValue({coordenadas: coords});
                        console.log('Enviado con Streamlit.setComponentValue');
                    } else {
                        // Método alternativo mediante recarga de URL
                        var currentUrl = new URL(window.location.href);
                        currentUrl.searchParams.set('lat', coords[0]);
                        currentUrl.searchParams.set('lng', coords[1]);
                        window.location.href = currentUrl.toString();
                        console.log('Enviado mediante recarga de URL');
                    }
                } catch (error) {
                    console.error('Error al enviar coordenadas:', error);
                    
                    // Método de último recurso
                    var currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set('lat', coords[0]);
                    currentUrl.searchParams.set('lng', coords[1]);
                    window.location.href = currentUrl.toString();
                    console.log('Enviado mediante método de respaldo');
                }
            }
        });
        </script>
        """, 
        height=0
    )
    
    # Componente personalizado para recibir las coordenadas
    coordenadas_component = st.empty()
    
    if coordenadas_component.button("Recibir coordenadas", key="coordenadas_btn", help="Este botón se activará automáticamente cuando selecciones un punto en el mapa"):
        # Este código se ejecutará cuando se reciban nuevas coordenadas
        if 'coordenadas' in st.session_state and st.session_state.coordenadas:
            lat, lon = st.session_state.coordenadas
            st.session_state.punto_seleccionado = (lat, lon)
            st.session_state.busqueda_realizada = True
            st.experimental_rerun()
    
    # Formulario para ingresar coordenadas manualmente
    with st.expander("Ingresar coordenadas manualmente"):
        with st.form("coordenadas_manuales"):
            col_lat, col_lon = st.columns(2)
            with col_lat:
                latitud = st.number_input("Latitud:", value=-34.603722, format="%.6f")
            with col_lon:
                longitud = st.number_input("Longitud:", value=-58.381592, format="%.6f")
            
            submit_btn = st.form_submit_button("Buscar en estas coordenadas")
            if submit_btn:
                st.session_state.punto_seleccionado = (latitud, longitud)
                st.session_state.busqueda_realizada = True
                st.experimental_rerun()

# Panel de resultados
with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si hay un punto seleccionado
    if st.session_state.busqueda_realizada and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        st.write(f"**Coordenadas del punto:** Lat {lat:.4f}, Lng {lon:.4f}")
        
        if st.session_state.resultado_busqueda:
            resultado = st.session_state.resultado_busqueda
            
            if resultado.get('contenedor', False):
                st.success("**Productor que contiene este punto:**")
            else:
                st.success("**Productor más cercano:**")
                
            st.markdown(f"""
            **CUIT:** {resultado['cuit']}  
            **Razón Social:** {resultado['titular']}  
            **RENSPA:** {resultado.get('renspa', 'No disponible')}  
            **Localidad:** {resultado.get('localidad', 'No disponible')}  
            **Superficie:** {resultado.get('superficie', 'No disponible')} ha  
            **Distancia:** {resultado['distancia']} km  
            """)
            
            # Botón para centrar en el mapa
            if st.button("Centrar en el mapa", key="centrar_mapa"):
                st.write("Centrando el mapa en el productor...")
                # Este código enviaría un mensaje al mapa para centrarse
        
        if st.session_state.cuits_cercanos:
            cercanos = st.session_state.cuits_cercanos
            st.subheader(f"Productores cercanos (radio {radio_busqueda} km):")
            
            # Mostrar número de productores encontrados
            st.info(f"Se encontraron {len(cercanos)} productores cercanos.")
            
            # Tabla resumida
            tabla_datos = []
            for cercano in cercanos:
                tabla_datos.append({
                    "CUIT": cercano['cuit'],
                    "Razón Social": cercano['titular'][:20] + "..." if len(cercano['titular']) > 20 else cercano['titular'],
                    "Km": cercano['distancia'],
                    "Contiene": "Sí" if cercano.get('contenedor', False) else "No"
                })
            
            st.dataframe(pd.DataFrame(tabla_datos), use_container_width=True)
            
            # Detalles expandibles
            for i, cercano in enumerate(cercanos[:10]):  # Mostrar los 10 más cercanos
                titulo = f"{i+1}. {cercano['titular']} ({cercano['distancia']} km)"
                if cercano.get('contenedor', False):
                    titulo += " - Contiene el punto"
                    
                with st.expander(titulo):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Razón Social:** {cercano['titular']}  
                    **RENSPA:** {cercano.get('renspa', 'No disponible')}  
                    **Localidad:** {cercano.get('localidad', 'No disponible')}  
                    **Superficie:** {cercano.get('superficie', 'No disponible')} ha  
                    **Distancia:** {cercano['distancia']} km  
                    **Coordenadas:** Lat {cercano['latitud']:.4f}, Lng {cercano['longitud']:.4f}
                    """)
                    
                    if cercano.get('poligono') is not None:
                        st.markdown(f"**Polígono disponible:** Sí")
                        if st.session_state.modo_debug:
                            st.code(cercano['poligono'][:100] + "..." if len(cercano['poligono']) > 100 else cercano['poligono'])
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("Selecciona un punto en el mapa o ingresa coordenadas manualmente para ver los resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección de punto**: Haz clic en el mapa para seleccionar un punto.
2. **Búsqueda**: Haz clic en "Buscar en estas coordenadas" para encontrar productores cercanos.
3. **Carga de archivos**: Sube archivos KML, KMZ o Shapefile para visualizarlos en el mapa.
4. **Uso de centroides**: Haz clic en un elemento del archivo cargado y selecciona "Usar centroide como referencia".
5. **Filtros**: Usa los filtros del panel lateral para mostrar productores específicos.
6. **Resultados**: Los resultados se mostrarán en el panel derecho.
""")

# Información sobre polígonos
st.markdown("### Verificación de polígonos")
st.markdown("""
- Si un punto está dentro de un polígono, se mostrará como "Contiene el punto".
- Los polígonos se colorean según su proximidad o relevancia.
- Para usar esta función, tu CSV debe tener una columna 'poligono' con datos en formato WKT.
""")

# Mostrar información de depuración si está activado
if st.session_state.modo_debug:
    st.markdown("---")
    with st.expander("Información de depuración"):
        st.write("**Estado de la aplicación:**")
        st.json({
            "punto_seleccionado": st.session_state.punto_seleccionado,
            "busqueda_realizada": st.session_state.busqueda_realizada,
            "radio_busqueda": st.session_state.radio_busqueda,
            "archivo_cargado": st.session_state.archivo_cargado["nombre"] if st.session_state.archivo_cargado else None,
            "modo_debug": st.session_state.modo_debug
        })
