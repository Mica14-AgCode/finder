    # Para depuración
    debug_checkbox = st.checkbox("Mostrar información de depuración")
    
    if debug_checkbox:
        st.write("Estado de la aplicación:")
        st.write({
            "punto_seleccionado": st.session_state.punto_seleccionado,
            "mostrar_resultado": st.session_state.mostrar_resultado,
            "busqueda_realizada": st.session_state.busqueda_realizada,
            "productores_cercanos_count": len(st.session_state.productores_cercanos) if hasattr(st.session_state, 'productores_cercanos') and st.session_state.productores_cercanos else 0,
            "poligonos_encontrados": len(poligonos_result)
        })
        
        if 'poligono' in datos_productores.columns:
            st.write(f"La columna 'poligono' existe en el CSV")
            
            # Mostrar algunos ejemplos de polígonos
            poligonos_count = datos_productores['poligono'].notna().sum()
            st.write(f"Número de polígonos en el CSV: {poligonos_count}")
            
            if poligonos_count > 0:
                st.write("Ejemplos de polígonos del CSV:")
                for i, fila in datos_productores.iterrows():
                    if pd.notna(fila.get('poligono')):
                        poligono_text = str(fila['poligono'])
                        st.code(poligono_text[:200] + "..." if len(poligono_text) > 200 else poligono_text)
                        breakimport streamlit as st
import pandas as pd
import math
import os
import json
import time

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
if 'mostrar_resultado' not in st.session_state:
    st.session_state.mostrar_resultado = False
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
if 'productores_cercanos' not in st.session_state:
    st.session_state.productores_cercanos = []
if 'timestamp_ultima_busqueda' not in st.session_state:
    st.session_state.timestamp_ultima_busqueda = 0

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
        
        return inside
    except Exception as e:
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
        return []

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
        'latitud': [-34.0, -34.2, -34.1, -33.9],
        'poligono': [
            "POLYGON((-60.0 -34.0, -60.1 -34.0, -60.1 -34.1, -60.0 -34.1, -60.0 -34.0))",
            "POLYGON((-60.2 -34.2, -60.3 -34.2, -60.3 -34.3, -60.2 -34.3, -60.2 -34.2))",
            "POLYGON((-60.1 -34.1, -60.2 -34.1, -60.2 -34.2, -60.1 -34.2, -60.1 -34.1))",
            "POLYGON((-59.9 -33.9, -60.0 -33.9, -60.0 -34.0, -59.9 -34.0, -59.9 -33.9))"
        ]
    })

@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """Carga los datos de productores desde un archivo CSV"""
    try:
        # Verificar si el archivo existe
        if not os.path.exists(ruta_archivo):
            return crear_datos_ejemplo()
        
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        
        # Verificar las columnas necesarias
        columnas_requeridas = ['cuit', 'titular', 'latitud', 'longitud']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            return crear_datos_ejemplo()
        
        return df
    except Exception as e:
        return crear_datos_ejemplo()

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
                    'contenedor': True
                }
                break
    
    return productor_contenedor

def encontrar_cuits_cercanos(lat, lon, datos, radio_km=200):
    """Encuentra productores cercanos a un punto dado dentro de un radio específico."""
    cercanos = []
    # Para agrupar por CUIT
    cuits_encontrados = set()
    
    # Primero verificar si está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        cercanos.append(productor_contenedor)
        cuits_encontrados.add(productor_contenedor['cuit'])
    
    # Buscar otros productores cercanos por distancia
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            # Si ya encontramos este CUIT, saltarlo
            if fila['cuit'] in cuits_encontrados:
                continue
                
            # Calcular distancia
            distancia = calcular_distancia_km(
                lat, lon, 
                fila['latitud'], fila['longitud']
            )
            
            if distancia <= radio_km:
                # Agregar a resultado y marcar como encontrado
                cercanos.append({
                    'cuit': fila['cuit'],
                    'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                    'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                    'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                    'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                    'distancia': round(distancia, 2),
                    'latitud': fila['latitud'],
                    'longitud': fila['longitud'],
                    'poligono': fila.get('poligono', None),
                    'contenedor': False
                })
                cuits_encontrados.add(fila['cuit'])
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Función para recibir coordenadas de JavaScript
def procesar_mensaje_js(lat, lon):
    """Procesa un mensaje de coordenadas desde JavaScript"""
    st.session_state.punto_seleccionado = (lat, lon)
    st.session_state.mostrar_resultado = True
    st.session_state.busqueda_realizada = True
    st.session_state.timestamp_ultima_busqueda = time.time()
    
    # Buscar productores cercanos
    st.session_state.productores_cercanos = encontrar_cuits_cercanos(
        lat, lon, datos_productores, radio_km=st.session_state.radio_busqueda
    )

# Panel lateral
with st.sidebar:
    st.header("Instrucciones")
    st.info(f"""
    **Configuración:**
    
    El archivo CSV debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener al menos: 'cuit', 'titular', 'latitud', 'longitud'
    4. Opcionalmente: 'poligono' en formato WKT para mostrar las parcelas
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
    # Contar CUITs únicos
    cuits_unicos = datos_productores['cuit'].nunique()
    st.success(f"Datos cargados correctamente: {len(datos_productores)} parcelas de {cuits_unicos} productores")

# Procesar coordenadas desde componente personalizado
coordinates_received = st.empty()
if "coordinates" in st.session_state:
    lat, lon = st.session_state.coordinates
    
    # Evitar múltiples recargas en corto tiempo
    if time.time() - st.session_state.timestamp_ultima_busqueda > 2:  # Mínimo 2 segundos entre búsquedas
        procesar_mensaje_js(lat, lon)
        del st.session_state.coordinates  # Limpiar para evitar búsquedas repetidas

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
    
    # Preparar polígonos para la respuesta
    poligonos_result = []
    if st.session_state.mostrar_resultado and st.session_state.punto_seleccionado:
        # Usar los productores cercanos ya calculados
        if hasattr(st.session_state, 'productores_cercanos') and st.session_state.productores_cercanos:
            productores_cercanos = st.session_state.productores_cercanos
            
            # Solo incluir polígonos de productores cercanos
            cuits_cercanos = [prod['cuit'] for prod in productores_cercanos]
            
            # Forzar la búsqueda de polígonos aunque no se hayan calculado aún
            if not poligonos_result and 'poligono' in datos_productores.columns:
                for idx, fila in datos_productores.iterrows():
                    if pd.notna(fila['poligono']) and fila['cuit'] in cuits_cercanos:
                        coords = wkt_a_coordenadas(fila['poligono'])
                        if coords:
                            poligonos_result.append({
                                'coords': coords,
                                'cuit': fila['cuit'],
                                'titular': fila['titular'],
                                'latitud': float(fila['latitud']),
                                'longitud': float(fila['longitud'])
                            })
                
                if not poligonos_result:
                    # Si no hay polígonos pero hay productores, incluir todos como marcadores
                    for productor in productores_cercanos:
                        if 'latitud' in productor and 'longitud' in productor:
                            poligonos_result.append({
                                'coords': [],
                                'cuit': productor['cuit'],
                                'titular': productor['titular'],
                                'latitud': float(productor['latitud']),
                                'longitud': float(productor['longitud']),
                                'es_marcador': True
                            })
        else:
            # Si no se han calculado aún los productores cercanos, buscarlos ahora
            lat, lon = st.session_state.punto_seleccionado
            productores_cercanos = encontrar_cuits_cercanos(lat, lon, datos_productores, radio_km=radio_busqueda)
            st.session_state.productores_cercanos = productores_cercanos
            st.session_state.busqueda_realizada = True
            
            # Incluir polígonos y marcadores
            cuits_cercanos = [prod['cuit'] for prod in productores_cercanos]
            if 'poligono' in datos_productores.columns:
                for idx, fila in datos_productores.iterrows():
                    if pd.notna(fila['poligono']) and fila['cuit'] in cuits_cercanos:
                        coords = wkt_a_coordenadas(fila['poligono'])
                        if coords:
                            poligonos_result.append({
                                'coords': coords,
                                'cuit': fila['cuit'],
                                'titular': fila['titular'],
                                'latitud': float(fila['latitud']),
                                'longitud': float(fila['longitud'])
                            })
            
            # Si no hay polígonos, incluir marcadores
            if not poligonos_result:
                for productor in productores_cercanos:
                    poligonos_result.append({
                        'coords': [],
                        'cuit': productor['cuit'],
                        'titular': productor['titular'],
                        'latitud': float(productor['latitud']),
                        'longitud': float(productor['longitud']),
                        'es_marcador': True
                    })
    
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
        <script>
            // Variables globales
            let map;
            let selectedMarker = null;
            let polygonsLayer = null;
            let markersLayer = null;
            let selectedCoords = null;
            
            // Datos para el mapa
            const poligonos = {json.dumps(poligonos_result)};
            const mostrarResultado = {"true" if st.session_state.mostrar_resultado else "false"};
            
            // Mostrar mensaje temporal
            function showMessage(message, duration = 3000) {{
                const msgEl = document.getElementById('status-message');
                msgEl.textContent = message;
                msgEl.style.display = 'block';
                
                setTimeout(() => {{
                    msgEl.style.display = 'none';
                }}, duration);
            }}
            
            // Inicializar el mapa cuando cargue la página
            document.addEventListener('DOMContentLoaded', initMap);
            
            function initMap() {{
                console.log("Iniciando mapa...");
                
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
                
                // Capas para polígonos y marcadores
                polygonsLayer = L.layerGroup().addTo(map);
                markersLayer = L.layerGroup().addTo(map);
                
                // Dibujar polígonos solo si hay resultados de búsqueda
                if (mostrarResultado) {{
                    if (poligonos.length > 0) {{
                        dibujarPoligonos();
                        console.log(`Se dibujaron ${{poligonos.length}} polígonos/marcadores`);
                    }}
                    else {{
                        console.log("No hay polígonos para dibujar, pero se muestra el punto seleccionado");
                    }}
                }}
                
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
                    selectedMarker = L.marker([lat, lng], {{
                        zIndexOffset: 1000  // Asegurar que esté encima de otros marcadores
                    }}).addTo(map);
                }});
                
                // Evento para botón de búsqueda
                document.getElementById('use-coords-btn').addEventListener('click', function() {{
                    if (!selectedCoords) {{
                        showMessage('Primero selecciona un punto en el mapa');
                        return;
                    }}
                    
                    enviarCoordenadas(selectedCoords[0], selectedCoords[1]);
                }});
                
                // Si hay un punto seleccionado anteriormente, mostrarlo
                const puntoSeleccionado = {"[" + str(st.session_state.punto_seleccionado[0]) + "," + str(st.session_state.punto_seleccionado[1]) + "]" if st.session_state.punto_seleccionado else "null"};
                if (puntoSeleccionado) {{
                    selectedCoords = puntoSeleccionado;
                    document.getElementById('coords-display').textContent = `Lat: ${{puntoSeleccionado[0].toFixed(6)}}, Lng: ${{puntoSeleccionado[1].toFixed(6)}}`;
                    selectedMarker = L.marker([puntoSeleccionado[0], puntoSeleccionado[1]], {{
                        zIndexOffset: 1000
                    }}).addTo(map);
                }}
            }}
            
            // Función para dibujar polígonos y marcadores
            function dibujarPoligonos() {{
                polygonsLayer.clearLayers();
                markersLayer.clearLayers();
                
                console.log("Dibujando poligonos y marcadores:", poligonos);
                
                poligonos.forEach(poligono => {{
                    if (poligono.coords && poligono.coords.length > 0) {{
                        // Dibujar polígono
                        const polygon = L.polygon(poligono.coords, {{
                            color: '#3388ff',
                            weight: 2,
                            opacity: 0.7,
                            fillOpacity: 0.2
                        }}).addTo(polygonsLayer);
                        
                        polygon.bindPopup(`
                            <strong>CUIT:</strong> ${{poligono.cuit}}<br>
                            <strong>Razón Social:</strong> ${{poligono.titular}}<br>
                            <button onclick="enviarCoordenadas(${{poligono.latitud}}, ${{poligono.longitud}})" style="margin-top:5px; padding:3px 8px; background:#4CAF50; color:white; border:none; border-radius:3px; cursor:pointer;">
                                Buscar este productor
                            </button>
                        `);
                    }}
                    
                    // Siempre dibujar un marcador para cada productor
                    if (poligono.latitud && poligono.longitud) {{
                        L.marker([poligono.latitud, poligono.longitud], {{
                            title: poligono.titular
                        }}).addTo(markersLayer).bindPopup(`
                            <strong>CUIT:</strong> ${{poligono.cuit}}<br>
                            <strong>Razón Social:</strong> ${{poligono.titular}}<br>
                            <button onclick="enviarCoordenadas(${{poligono.latitud}}, ${{poligono.longitud}})" style="margin-top:5px; padding:3px 8px; background:#4CAF50; color:white; border:none; border-radius:3px; cursor:pointer;">
                                Buscar este productor
                            </button>
                        `);
                    }}
                }});
            }}
            
            // Función para enviar coordenadas a Streamlit
            function enviarCoordenadas(lat, lng) {{
                // Mostrar mensaje de búsqueda
                showMessage(`Buscando productores cercanos a Lat: ${{lat.toFixed(6)}}, Lng: ${{lng.toFixed(6)}}...`);
                
                // Comunicación con Streamlit mediante componentes
                if (window.parent && window.parent.Streamlit) {{
                    window.parent.Streamlit.setComponentValue({{
                        coordinates: [lat, lng]
                    }});
                    console.log("Coordenadas enviadas vía setComponentValue:", lat, lng);
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    # Mostrar el mapa
    st.components.v1.html(mapa_html, height=600, scrolling=False)

with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si tenemos un punto seleccionado
    if st.session_state.mostrar_resultado and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        # Mostrar las coordenadas del punto seleccionado
        st.success(f"Punto seleccionado: Lat {lat:.6f}, Lng {lon:.6f}")
        
        # Buscar productores cercanos si no se ha realizado la búsqueda
        if not st.session_state.busqueda_realizada or not st.session_state.productores_cercanos:
            with st.spinner(f"Buscando productores en un radio de {radio_busqueda} km..."):
                st.session_state.productores_cercanos = encontrar_cuits_cercanos(lat, lon, datos_productores, radio_km=radio_busqueda)
                st.session_state.busqueda_realizada = True
        
        # Usar los resultados almacenados
        productores_cercanos = st.session_state.productores_cercanos
        
        if productores_cercanos:
            # Contar razones sociales únicas
            cuits_unicos = len(set(productor['cuit'] for productor in productores_cercanos))
            st.success(f"Se encontraron {cuits_unicos} productores en un radio de {radio_busqueda} km")
            
            # Productor más cercano o contenedor
            mas_cercano = productores_cercanos[0]
            
            if mas_cercano.get('contenedor', False):
                st.subheader("Productor que contiene este punto:")
            else:
                st.subheader("Productor más cercano:")
                
            st.markdown(f"""
            **CUIT:** {mas_cercano['cuit']}  
            **Razón Social:** {mas_cercano['titular']}  
            **Distancia:** {mas_cercano['distancia']} km  
            **Localidad:** {mas_cercano.get('localidad', 'No disponible')}  
            **Superficie:** {mas_cercano.get('superficie', 'No disponible')} ha  
            **Coordenadas:** Lat {mas_cercano['latitud']:.6f}, Lng {mas_cercano['longitud']:.6f}
            """)
            
            # Tabla de todos los productores cercanos
            st.subheader(f"Todos los productores (radio {radio_busqueda} km):")
            
            # Crear un DataFrame para la tabla
            tabla_data = []
            for productor in productores_cercanos:
                tabla_data.append({
                    "CUIT": productor['cuit'],
                    "Razón Social": productor['titular'],
                    "Distancia (km)": productor['distancia'],
                    "Localidad": productor.get('localidad', ''),
                    "Contiene punto": "Sí" if productor.get('contenedor', False) else "No"
                })
            
            # Mostrar tabla
            st.dataframe(pd.DataFrame(tabla_data), use_container_width=True)

# Instrucciones para usar el mapa
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección de punto**: Haz clic en cualquier punto del mapa para seleccionarlo.
2. **Búsqueda**: Haz clic en el botón "Buscar en estas coordenadas" para encontrar productores cercanos.
3. **Visualización de polígonos**: Los polígonos de los productores cercanos se mostrarán en el mapa tras la búsqueda.
4. **Radio de búsqueda**: Ajusta el radio de búsqueda en el panel lateral para ampliar o reducir el área de búsqueda.
5. **Interacción con polígonos**: Haz clic en un polígono para ver información del productor asociado.
""")
