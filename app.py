import streamlit as st
import pandas as pd
import math
import json
import base64

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
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        # Crear datos de ejemplo
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
                    'idx': idx
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
                    'idx': idx
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

# Filtro por localidad si existe
if 'localidad' in datos_productores.columns:
    localidades = ["Todas"] + sorted(list(datos_productores['localidad'].unique()))
    localidad_seleccionada = st.sidebar.selectbox("Filtrar por localidad:", localidades)
    
    if localidad_seleccionada != "Todas":
        datos_filtrados = datos_filtrados[datos_filtrados['localidad'] == localidad_seleccionada]

# Radio de búsqueda ajustable con mayor rango
radio_busqueda = st.sidebar.slider(
    "Radio de búsqueda (km):", 
    min_value=0.1, 
    max_value=100.0, 
    value=5.0, 
    step=0.1
)

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

# Layout principal
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa Interactivo")
    st.info("👆 **Haz clic en cualquier punto del mapa** para buscar productores cercanos.")
    
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
        
        # Código HTML y JavaScript para el mapa Leaflet
        mapa_html = f"""
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css" />
        <style>
            #map {{
                width: 100%;
                height: 500px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
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
        </style>
        
        <div id="map"></div>
        <div id="selected-coords">
            <div>
                <span>Coordenadas seleccionadas:</span>
                <span class="coord-value" id="selected-lat">-</span>, 
                <span class="coord-value" id="selected-lng">-</span>
            </div>
            <button id="use-coords-btn">🔍 USAR ESTAS COORDENADAS</button>
        </div>
        
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js"></script>
        <script src="https://unpkg.com/@tmcw/togeojson/dist/togeojson.umd.js"></script>
        <script src="https://unpkg.com/shpjs@latest/dist/shp.js"></script>
        
        <script>
            // Inicializar el mapa
            const map = L.map('map').setView([{centro_lat}, {centro_lon}], 9);
            
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
            
            // Agregar control de capas
            L.control.layers(baseMaps).addTo(map);
            
            // Agregar control de búsqueda de localidades
            L.Control.geocoder({{
                defaultMarkGeocode: false,
                placeholder: "Buscar localidad...",
                errorMessage: "No se encontró la localidad",
                suggestMinLength: 3,
                suggestTimeout: 250,
                queryMinLength: 1
            }})
            .on('markgeocode', function(e) {{
                const latlng = e.geocode.center;
                map.setView(latlng, 13);
                L.marker(latlng).addTo(map);
            }})
            .addTo(map);
            
            // Variable para el marcador del punto seleccionado
            let puntoSeleccionado = null;
            
            // Colección de polígonos para los productores
            const poligonosLayer = L.layerGroup().addTo(map);
            
            // Array de colores para polígonos
            const colors = {colors_json};
            
            // Variable para guardar los polígonos cercanos
            let poligonosCercanos = [];
            
            // Función para dibujar polígonos de productores
            function dibujarPoligonos(poligonos) {{
                // Limpiar los polígonos existentes
                poligonosLayer.clearLayers();
                
                // Obtener los datos de polígonos
                const datos = {poligonos_json};
                
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
            }}
            
            // Función para colorear polígonos cercanos
            function colorearPoligonosCercanos(cercanos) {{
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
            }}
            
            // Función para colorear el polígono más cercano
            function colorearPoligonoMasCercano(masCercano) {{
                if (!masCercano) return;
                
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
                
                if (!isNaN(lat) && !isNaN(lng)) {{
                    // Enviar datos de vuelta a Streamlit
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: {{ lat: lat, lng: lng }}
                    }}, '*');
                }}
            }});
            
            // Manejador para actualizar los polígonos cercanos
            window.addEventListener('message', function(event) {{
                const data = event.data;
                
                // Comprobar si tenemos datos de polígonos cercanos
                if (data && data.type === 'cercanos') {{
                    // Actualizar los polígonos cercanos
                    colorearPoligonosCercanos(data.cercanos);
                    
                    // Colorear el polígono más cercano
                    if (data.masCercano) {{
                        colorearPoligonoMasCercano(data.masCercano);
                    }}
                }}
            }});
            
            // Función para cargar archivo KML/KMZ/Shapefile
            function cargarArchivo(tipo, datos) {{
                try {{
                    if (tipo.includes('kml')) {{
                        // Convertir de base64 a texto
                        const texto = atob(datos);
                        // Crear un objeto DOM del KML
                        const parser = new DOMParser();
                        const kml = parser.parseFromString(texto, 'text/xml');
                        // Convertir a GeoJSON usando toGeoJSON
                        const geojson = toGeoJSON.kml(kml);
                        
                        // Agregar al mapa
                        L.geoJSON(geojson, {{
                            style: {{
                                color: '#ff9900',
                                weight: 2,
                                fillOpacity: 0.2
                            }}
                        }}).addTo(map);
                        
                        // Hacer zoom al extent
                        if (geojson.features.length > 0) {{
                            const bounds = L.geoJSON(geojson).getBounds();
                            map.fitBounds(bounds);
                        }}
                        
                    }} else if (tipo.includes('zip') || tipo.includes('shp')) {{
                        // Usar shpjs para cargar el shapefile
                        shp(datos).then(function(geojson) {{
                            L.geoJSON(geojson, {{
                                style: {{
                                    color: '#ff9900',
                                    weight: 2,
                                    fillOpacity: 0.2
                                }}
                            }}).addTo(map);
                            
                            // Hacer zoom al extent
                            if (geojson.features && geojson.features.length > 0) {{
                                const bounds = L.geoJSON(geojson).getBounds();
                                map.fitBounds(bounds);
                            }}
                        }});
                    }}
                }} catch (error) {{
                    console.error('Error al cargar el archivo:', error);
                }}
            }}
            
            // Cargar archivo si existe
            {f"cargarArchivo('{st.session_state.archivo_cargado['tipo']}', '{st.session_state.archivo_cargado['b64']}');" if st.session_state.archivo_cargado else ""}
            
            // Si hay un punto seleccionado previamente, mostrarlo
            {f"const lat = {st.session_state.punto_seleccionado[0]}; const lng = {st.session_state.punto_seleccionado[1]};" if st.session_state.punto_seleccionado else ""}
            {"""
            if (lat && lng) {
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
        </script>
        """
        
        # Mostrar el mapa con Leaflet
        components_result = st.components.v1.html(mapa_html, height=600)
        
        # Procesar los resultados del componente HTML
        if isinstance(components_result, dict) and 'lat' in components_result and 'lng' in components_result:
            # Guardar las coordenadas en session_state
            st.session_state.punto_seleccionado = (components_result['lat'], components_result['lng'])
            st.session_state.busqueda_realizada = True
            st.rerun()
        
        # Mostrar ayuda para cargar archivos
        st.markdown("""
        ### Cargar archivos geoespaciales
        
        Puedes subir archivos KML, KMZ o Shapefile (ZIP) desde el panel lateral para visualizarlos en el mapa.
        """)
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
            # Crear JavaScript para actualizar el mapa
            update_js = f"""
            <script>
            // Enviar datos al mapa
            window.parent.postMessage({{
                type: 'cercanos',
                cercanos: {json.dumps(cuits_cercanos)},
                masCercano: {json.dumps(cuit_mas_cercano) if cuit_mas_cercano else 'null'}
            }}, '*');
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
1. **Selección en mapa**: Haz clic en cualquier punto del mapa.
2. **Usar coordenadas**: Haz clic en el botón grande "USAR ESTAS COORDENADAS" para consultar el punto seleccionado.
3. **Resultados**: Verás el productor más cercano y todos los que estén dentro del radio especificado.
4. **Filtros**: Usa los filtros en el panel lateral para mostrar productores específicos.
5. **Radio de búsqueda**: Ajusta el radio para ver productores a mayor o menor distancia (0.1 a 100 km).
6. **Búsqueda de localidad**: Usa el buscador en la esquina superior derecha del mapa.
7. **Carga de archivos**: Sube archivos KML, KMZ o Shapefile desde el panel lateral.
""")
