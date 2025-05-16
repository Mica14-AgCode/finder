import streamlit as st
import pandas as pd
import math
import os
import json
import time

# Configuración de la página - solo títulos esenciales
st.set_page_config(
    page_title="Visor de Productores Agrícolas", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal (único)
st.write("# Visor de Productores Agrícolas")

# Constantes
RUTA_CSV = "datos_productores.csv"

# Inicializar variables de estado (solo las necesarias)
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'radio_busqueda' not in st.session_state:
    st.session_state.radio_busqueda = 200.0
if 'mostrar_resultado' not in st.session_state:
    st.session_state.mostrar_resultado = False
if 'productores_cercanos' not in st.session_state:
    st.session_state.productores_cercanos = []

# Funciones básicas
def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """Calcula la distancia en kilómetros entre dos puntos usando la fórmula de Haversine"""
    R = 6371.0  # Radio de la Tierra en km
    
    # Convertir coordenadas a radianes
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    # Diferencias de latitud y longitud
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c  # Distancia en km

def punto_en_poligono(latitud, longitud, poligono_wkt):
    """Verifica si un punto está dentro de un polígono WKT (algoritmo ray casting)"""
    if not poligono_wkt or not isinstance(poligono_wkt, str):
        return False
    
    try:
        # Extraer coordenadas del polígono
        coords_str = poligono_wkt.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
        coords_pares = coords_str.split(',')
        
        # Convertir a pares (lon, lat)
        vertices = []
        for par in coords_pares:
            valores = par.strip().split()
            if len(valores) >= 2:
                lon, lat = float(valores[0]), float(valores[1])
                vertices.append((lon, lat))
        
        # Algoritmo ray casting
        inside = False
        n = len(vertices)
        if n < 3:  # No es un polígono válido
            return False
        
        j = n - 1
        for i in range(n):
            if ((vertices[i][1] > latitud) != (vertices[j][1] > latitud)) and \
               (longitud < (vertices[j][0] - vertices[i][0]) * (latitud - vertices[i][1]) / (vertices[j][1] - vertices[i][1]) + vertices[i][0]):
                inside = not inside
            j = i
        
        return inside
    except:
        return False

def wkt_a_coordenadas(wkt_str):
    """Convierte un string WKT de polígono a coordenadas [[lat, lng], ...] para Leaflet"""
    if not wkt_str or not isinstance(wkt_str, str):
        return []
    
    try:
        # Extraer coordenadas
        coords_str = wkt_str.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
        coords_pares = coords_str.split(',')
        
        # Convertir a formato Leaflet [lat, lng]
        coords = []
        for par in coords_pares:
            valores = par.strip().split()
            if len(valores) >= 2:
                # WKT es lon,lat pero Leaflet necesita lat,lon
                lon, lat = float(valores[0]), float(valores[1])
                coords.append([lat, lon])
        
        return coords
    except:
        return []

def crear_datos_ejemplo():
    """Datos de ejemplo cuando no se puede cargar el CSV"""
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
        # Verificar existencia del archivo
        if not os.path.exists(ruta_archivo):
            return crear_datos_ejemplo()
        
        # Cargar CSV
        df = pd.read_csv(ruta_archivo)
        
        # Verificar columnas necesarias
        columnas_requeridas = ['cuit', 'titular', 'latitud', 'longitud']
        if not all(col in df.columns for col in columnas_requeridas):
            return crear_datos_ejemplo()
        
        return df
    except:
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
    """Encuentra productores cercanos a un punto dado dentro de un radio específico"""
    cercanos = []
    cuits_encontrados = set()  # Para evitar duplicados
    
    # Verificar si está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        cercanos.append(productor_contenedor)
        cuits_encontrados.add(productor_contenedor['cuit'])
    
    # Buscar otros productores cercanos por distancia
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            # Si ya encontramos este CUIT, continuar
            if fila['cuit'] in cuits_encontrados:
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
                    'poligono': fila.get('poligono', None),
                    'contenedor': False
                })
                cuits_encontrados.add(fila['cuit'])
    
    # Ordenar por distancia
    return sorted(cercanos, key=lambda x: x['distancia'])

# Obtener datos (una sola vez)
datos_productores = cargar_datos()

# Panel lateral simple
with st.sidebar:
    st.write("## Filtros")
    
    # Radio de búsqueda
    radio_busqueda = st.slider(
        "Radio de búsqueda (km):",
        min_value=1.0,
        max_value=500.0,
        value=st.session_state.radio_busqueda,
        step=1.0
    )
    st.session_state.radio_busqueda = radio_busqueda
    
    # Información básica
    st.write("## Información")
    if not datos_productores.empty:
        cuits_unicos = datos_productores['cuit'].nunique()
        st.success(f"{len(datos_productores)} parcelas de {cuits_unicos} productores")
    
    st.info("""
    **Instrucciones:**
    
    1. Haz clic en el mapa para seleccionar un punto
    2. Haz clic en "Buscar" para encontrar productores
    3. Ajusta el radio de búsqueda si es necesario
    """)

# Verificar parámetros URL (sin hacer experimental_rerun)
try:
    # Ver si tenemos parámetros de URL
    params = st.experimental_get_query_params()
    if 'lat' in params and 'lng' in params:
        lat = float(params['lat'][0])
        lon = float(params['lng'][0])
        
        # Actualizar estado sin rerun
        st.session_state.punto_seleccionado = (lat, lon)
        st.session_state.mostrar_resultado = True
        
        # Buscar productores cercanos
        st.session_state.productores_cercanos = encontrar_cuits_cercanos(
            lat, lon, datos_productores, radio_km=st.session_state.radio_busqueda
        )
        
        # Limpiar parámetros sin rerun
        st.experimental_set_query_params()
except:
    # Ignorar errores de parámetros silenciosamente
    pass

# Layout principal (2 columnas)
col1, col2 = st.columns([3, 1])

with col1:
    st.write("## Mapa Interactivo")
    
    # Calcular centro del mapa
    centro_lat = datos_productores['latitud'].mean() if not datos_productores.empty else -34.0
    centro_lon = datos_productores['longitud'].mean() if not datos_productores.empty else -60.0
    
    # Preparar datos para el mapa
    poligonos_result = []
    productores_para_marcadores = []
    if st.session_state.punto_seleccionado and st.session_state.productores_cercanos:
        productores_cercanos = st.session_state.productores_cercanos
        
        # Incluir polígonos de productores cercanos
        if 'poligono' in datos_productores.columns:
            cuits_cercanos = [p['cuit'] for p in productores_cercanos]
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
        
        # Añadir marcadores para todos los productores cercanos
        for productor in productores_cercanos:
            productores_para_marcadores.append({
                'cuit': productor['cuit'],
                'titular': productor['titular'],
                'latitud': float(productor['latitud']),
                'longitud': float(productor['longitud']),
                'contenedor': productor.get('contenedor', False)
            })
    
    # Crear mapa Leaflet simplificado
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
            #coords-display {{
                font-weight: bold;
                color: #333;
            }}
            #search-btn {{
                margin-top: 10px;
                padding: 8px 16px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
            }}
            #search-btn:hover {{
                background-color: #45a049;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div id="info-panel">
            <div>Coordenadas: <span id="coords-display">Haz clic en el mapa</span></div>
            <button id="search-btn">Buscar</button>
        </div>
        
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script>
            // Variables globales
            let map;
            let selectedMarker = null;
            let polygonsLayer, markersLayer;
            let selectedCoords = null;
            
            // Datos
            const poligonos = {json.dumps(poligonos_result)};
            const marcadores = {json.dumps(productores_para_marcadores)};
            const puntoSeleccionado = {"[" + str(st.session_state.punto_seleccionado[0]) + "," + str(st.session_state.punto_seleccionado[1]) + "]" if st.session_state.punto_seleccionado else "null"};
            
            // Inicializar mapa
            document.addEventListener('DOMContentLoaded', () => {{
                // Crear mapa
                map = L.map('map').setView([{centro_lat}, {centro_lon}], 9);
                
                // Capas base
                const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    attribution: 'Tiles &copy; Esri'
                }});
                
                const osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }});
                
                // Añadir capas
                satelliteLayer.addTo(map);
                
                const baseMaps = {{
                    "Satélite": satelliteLayer,
                    "Mapa": osmLayer
                }};
                
                L.control.layers(baseMaps).addTo(map);
                
                // Capas para resultados
                polygonsLayer = L.layerGroup().addTo(map);
                markersLayer = L.layerGroup().addTo(map);
                
                // Mostrar polígonos y marcadores si hay
                mostrarResultados();
                
                // Evento de clic en el mapa
                map.on('click', e => {{
                    const lat = e.latlng.lat;
                    const lng = e.latlng.lng;
                    
                    selectedCoords = [lat, lng];
                    document.getElementById('coords-display').textContent = `Lat: ${{lat.toFixed(6)}}, Lng: ${{lng.toFixed(6)}}`;
                    
                    if (selectedMarker) {{
                        map.removeLayer(selectedMarker);
                    }}
                    
                    selectedMarker = L.marker([lat, lng], {{
                        zIndexOffset: 1000
                    }}).addTo(map);
                }});
                
                // Evento de botón de búsqueda
                document.getElementById('search-btn').addEventListener('click', () => {{
                    if (!selectedCoords) {{
                        alert('Primero selecciona un punto en el mapa');
                        return;
                    }}
                    
                    // Redireccionar con coordenadas
                    const url = new URL(window.location.href);
                    url.searchParams.set('lat', selectedCoords[0]);
                    url.searchParams.set('lng', selectedCoords[1]);
                    window.location.href = url.toString();
                }});
                
                // Mostrar punto seleccionado previamente
                if (puntoSeleccionado) {{
                    selectedCoords = puntoSeleccionado;
                    document.getElementById('coords-display').textContent = 
                        `Lat: ${{puntoSeleccionado[0].toFixed(6)}}, Lng: ${{puntoSeleccionado[1].toFixed(6)}}`;
                    
                    selectedMarker = L.marker([puntoSeleccionado[0], puntoSeleccionado[1]], {{
                        zIndexOffset: 1000
                    }}).addTo(map);
                    
                    // Centrar en el punto y resultados
                    if (poligonos.length > 0 || marcadores.length > 0) {{
                        centrarEnResultados();
                    }} else {{
                        map.setView([puntoSeleccionado[0], puntoSeleccionado[1]], 12);
                    }}
                }}
            }});
            
            // Función para mostrar resultados
            function mostrarResultados() {{
                // Limpiar capas
                polygonsLayer.clearLayers();
                markersLayer.clearLayers();
                
                // Mostrar polígonos
                poligonos.forEach(poligono => {{
                    if (poligono.coords && poligono.coords.length > 0) {{
                        const polygon = L.polygon(poligono.coords, {{
                            color: '#3388ff',
                            weight: 2,
                            opacity: 0.7,
                            fillOpacity: 0.2
                        }}).addTo(polygonsLayer);
                        
                        polygon.bindPopup(`
                            <strong>CUIT:</strong> ${{poligono.cuit}}<br>
                            <strong>Razón Social:</strong> ${{poligono.titular}}
                        `);
                    }}
                }});
                
                // Mostrar marcadores
                marcadores.forEach(marcador => {{
                    // Color diferente si contiene el punto
                    const markerIcon = marcador.contenedor ? 
                        new L.Icon({{ 
                            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41],
                            popupAnchor: [1, -34],
                            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                            shadowSize: [41, 41]
                        }}) : 
                        new L.Icon({{
                            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41],
                            popupAnchor: [1, -34],
                            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                            shadowSize: [41, 41]
                        }});
                    
                    L.marker([marcador.latitud, marcador.longitud], {{
                        title: marcador.titular,
                        icon: markerIcon
                    }}).addTo(markersLayer).bindPopup(`
                        <strong>CUIT:</strong> ${{marcador.cuit}}<br>
                        <strong>Razón Social:</strong> ${{marcador.titular}}<br>
                        ${{marcador.contenedor ? '<strong>Contiene el punto seleccionado</strong>' : ''}}
                    `);
                }});
            }}
            
            // Función para centrar en los resultados
            function centrarEnResultados() {{
                // Si hay polígonos, centrar en ellos
                if (poligonos.length > 0) {{
                    try {{
                        const bounds = L.featureGroup(Array.from(polygonsLayer.getLayers())).getBounds();
                        map.fitBounds(bounds, {{ padding: [50, 50] }});
                        return;
                    }} catch (e) {{
                        console.log("Error al centrar en polígonos:", e);
                    }}
                }}
                
                // Si hay marcadores, centrar en ellos
                if (marcadores.length > 0) {{
                    try {{
                        const bounds = L.featureGroup(Array.from(markersLayer.getLayers())).getBounds();
                        map.fitBounds(bounds, {{ padding: [50, 50] }});
                        return;
                    }} catch (e) {{
                        console.log("Error al centrar en marcadores:", e);
                    }}
                }}
                
                // Si nada funciona, centrar en el punto seleccionado
                if (puntoSeleccionado) {{
                    map.setView([puntoSeleccionado[0], puntoSeleccionado[1]], 12);
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    # Renderizar mapa
    st.components.v1.html(mapa_html, height=600, scrolling=False)

with col2:
    # Mostrar resultados de búsqueda
    if st.session_state.mostrar_resultado and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        # Mostrar punto seleccionado
        st.write(f"### Punto seleccionado")
        st.success(f"Lat: {lat:.6f}, Lng: {lon:.6f}")
        
        # Usar resultados almacenados o calcular si no existen
        if not st.session_state.productores_cercanos:
            with st.spinner(f"Buscando productores en {radio_busqueda} km..."):
                st.session_state.productores_cercanos = encontrar_cuits_cercanos(
                    lat, lon, datos_productores, radio_km=radio_busqueda
                )
        
        productores_cercanos = st.session_state.productores_cercanos
        
        if productores_cercanos:
            # Mostrar conteo
            cuits_unicos = len(set(p['cuit'] for p in productores_cercanos))
            st.write(f"### Resultados")
            st.success(f"{cuits_unicos} productores en {radio_busqueda} km")
            
            # Productor más cercano o contenedor
            mas_cercano = productores_cercanos[0]
            
            # Destacar productor principal
            if mas_cercano.get('contenedor', False):
                st.info(f"**El punto está dentro del campo de:**")
            else:
                st.info(f"**Productor más cercano:**")
                
            st.write(f"""
            **CUIT:** {mas_cercano['cuit']}  
            **Razón Social:** {mas_cercano['titular']}  
            **Distancia:** {mas_cercano['distancia']} km  
            **Localidad:** {mas_cercano.get('localidad', 'No disponible')}  
            **Superficie:** {mas_cercano.get('superficie', 'No disponible')} ha  
            """)
            
            # Tabla de todos los productores
            st.write(f"### Listado completo")
            
            # Crear tabla
            tabla_data = [
                {
                    "CUIT": p['cuit'],
                    "Razón Social": p['titular'],
                    "Distancia (km)": p['distancia'],
                    "Localidad": p.get('localidad', ''),
                    "Contiene punto": "Sí" if p.get('contenedor', False) else "No"
                }
                for p in productores_cercanos
            ]
            
            st.dataframe(pd.DataFrame(tabla_data), use_container_width=True)
        else:
            st.warning(f"No se encontraron productores en {radio_busqueda} km")
    else:
        st.info("Haz clic en el mapa para buscar productores cercanos.")
