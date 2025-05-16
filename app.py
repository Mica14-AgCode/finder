import streamlit as st
import pandas as pd
import math
import os
import json

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

# Inicializar variables de estado
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'radio_busqueda' not in st.session_state:
    st.session_state.radio_busqueda = 200.0

# Funciones básicas
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

def crear_datos_ejemplo():
    """Crea datos de ejemplo cuando no se puede cargar el CSV"""
    st.info("Usando datos de ejemplo para demostración")
    return pd.DataFrame({
        'cuit': ['20123456789', '30987654321', '33444555667', '27888999001'],
        'titular': ['Productor Ejemplo 1', 'Productor Ejemplo 2', 'Productor Ejemplo 3', 'Productor Ejemplo 4'],
        'renspa': ['12.345.6.78901/01', '98.765.4.32109/02', '11.222.3.33333/03', '44.555.6.66666/04'],
        'localidad': ['Localidad 1', 'Localidad 2', 'Localidad 3', 'Localidad 4'],
        'superficie': [100, 150, 200, 75],
        'longitud': [-60.0, -60.2, -60.1, -59.9],
        'latitud': [-34.0, -34.2, -34.1, -33.9]
    })

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

def encontrar_cuits_cercanos(lat, lon, datos, radio_km=200):
    """Encuentra CUITs cercanos a un punto dado dentro de un radio específico."""
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
                    'longitud': fila['longitud']
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Panel lateral
with st.sidebar:
    st.header("Instrucciones")
    st.info(f"""
    **Configuración:**
    
    El archivo CSV debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener al menos: 'cuit', 'titular', 'latitud', 'longitud'
    """)
    
    # Filtros
    st.header("Filtros")
    
    # Radio de búsqueda
    radio_busqueda = st.slider(
        "Radio de búsqueda (km):",
        min_value=1.0,
        max_value=500.0,
        value=st.session_state.radio_busqueda,
        step=1.0
    )
    st.session_state.radio_busqueda = radio_busqueda

# Cargar datos
datos_productores = cargar_datos()

# Si hay datos, mostrar información básica
if not datos_productores.empty:
    st.success(f"Datos cargados correctamente: {len(datos_productores)} registros")

# Layout principal
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa Interactivo")
    
    # Calcular centro del mapa
    if datos_productores.empty:
        centro_lat = -34.0
        centro_lon = -60.0
    else:
        centro_lat = datos_productores['latitud'].mean()
        centro_lon = datos_productores['longitud'].mean()
    
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
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div id="info-panel">
            <div>Coordenadas seleccionadas: <span id="coords-display">Haz clic en el mapa</span></div>
            <button id="use-coords-btn">Buscar en estas coordenadas</button>
        </div>
        
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script>
            // Variables globales
            let map;
            let selectedMarker = null;
            let selectedCoords = null;
            
            // Inicializar el mapa cuando cargue la página
            document.addEventListener('DOMContentLoaded', initMap);
            
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
                
                // Evento de clic en el mapa
                map.on('click', function(e) {{
                    const lat = e.latlng.lat;
                    const lng = e.latlng.lng;
                    
                    // Actualizar coordenadas seleccionadas
                    selectedCoords = [lat, lng];
                    document.getElementById('coords-display').textContent = `Lat: ${{lat.toFixed(6)}}, Lng: ${{lng.toFixed(6)}}`;
                    
                    // Actualizar marcador
                    if (selectedMarker) {{
                        map.removeLayer(selectedMarker);
                    }}
                    selectedMarker = L.marker([lat, lng]).addTo(map);
                }});
                
                // Evento para botón de búsqueda
                document.getElementById('use-coords-btn').addEventListener('click', function() {{
                    if (!selectedCoords) {{
                        alert('Primero selecciona un punto en el mapa');
                        return;
                    }}
                    
                    // Enviar mensaje a la página principal
                    window.parent.postMessage({{
                        type: 'coordenadas_seleccionadas',
                        coords: selectedCoords
                    }}, '*');
                }});
            }}
        </script>
    </body>
    </html>
    """
    
    # Mostrar el mapa
    st.components.v1.html(mapa_html, height=600, scrolling=False)
    
    # Código JavaScript para recibir mensajes del mapa
    js_code = """
    <script>
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'coordenadas_seleccionadas') {
            // Crear un formulario oculto para enviar las coordenadas a Streamlit
            var form = document.createElement('form');
            form.method = 'GET';
            form.action = window.location.href;

            // Agregar parámetros de coordenadas
            var lat = document.createElement('input');
            lat.type = 'hidden';
            lat.name = 'lat';
            lat.value = event.data.coords[0];
            form.appendChild(lat);

            var lng = document.createElement('input');
            lng.type = 'hidden';
            lng.name = 'lng';
            lng.value = event.data.coords[1];
            form.appendChild(lng);

            // Enviar el formulario
            document.body.appendChild(form);
            form.submit();
        }
    });
    </script>
    """
    st.components.v1.html(js_code, height=0)
    
    # Verificar si hay parámetros en la URL
    query_params = st.experimental_get_query_params()
    if 'lat' in query_params and 'lng' in query_params:
        try:
            lat = float(query_params['lat'][0])
            lon = float(query_params['lng'][0])
            st.session_state.punto_seleccionado = (lat, lon)
            # Limpiar los parámetros para evitar duplicados
            st.experimental_set_query_params()
            st.experimental_rerun()
        except:
            st.error("Error al procesar las coordenadas")

with col2:
    st.subheader("Buscar por coordenadas")
    
    with st.form("busqueda_manual"):
        col_lat, col_lon = st.columns(2)
        with col_lat:
            latitud = st.number_input("Latitud:", value=-34.603722, format="%.6f")
        with col_lon:
            longitud = st.number_input("Longitud:", value=-58.381592, format="%.6f")
        
        submit_btn = st.form_submit_button("Buscar productores cercanos", use_container_width=True)
        if submit_btn:
            st.session_state.punto_seleccionado = (latitud, longitud)

    # Mostrar resultados si hay un punto seleccionado
    if st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        st.success(f"Punto seleccionado: Lat {lat:.6f}, Lng {lon:.6f}")
        
        # Buscar productores cercanos
        with st.spinner(f"Buscando productores en un radio de {radio_busqueda} km..."):
            productores_cercanos = encontrar_cuits_cercanos(lat, lon, datos_productores, radio_km=radio_busqueda)
        
        st.subheader("Resultados de la búsqueda")
        
        if productores_cercanos:
            st.success(f"Se encontraron {len(productores_cercanos)} productores en un radio de {radio_busqueda} km")
            
            # Productor más cercano
            mas_cercano = productores_cercanos[0]
            
            st.markdown("### Productor más cercano:")
            st.markdown(f"""
            **CUIT:** {mas_cercano['cuit']}  
            **Razón Social:** {mas_cercano['titular']}  
            **Distancia:** {mas_cercano['distancia']} km  
            **Localidad:** {mas_cercano.get('localidad', 'No disponible')}  
            **Coordenadas:** Lat {mas_cercano['latitud']:.6f}, Lng {mas_cercano['longitud']:.6f}
            """)
            
            # Tabla de todos los productores cercanos
            st.markdown("### Todos los productores cercanos:")
            
            # Crear un DataFrame para la tabla
            tabla_data = []
            for productor in productores_cercanos:
                tabla_data.append({
                    "CUIT": productor['cuit'],
                    "Razón Social": productor['titular'],
                    "Distancia (km)": productor['distancia'],
                    "Localidad": productor.get('localidad', '')
                })
            
            # Mostrar tabla
            st.dataframe(pd.DataFrame(tabla_data), use_container_width=True)
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")

# Instrucciones para usar el mapa
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección de punto**: Haz clic en el mapa para seleccionar un punto.
2. **Búsqueda**: Haz clic en "Buscar en estas coordenadas" para encontrar productores cercanos.
3. **Búsqueda manual**: Alternativamente, puedes ingresar coordenadas manualmente en el formulario.
4. **Radio de búsqueda**: Ajusta el radio de búsqueda en el panel lateral para ampliar o reducir el área de búsqueda.
""")
