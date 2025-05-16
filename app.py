import streamlit as st
import pandas as pd
import math
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
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
if 'latitud_input' not in st.session_state:
    st.session_state.latitud_input = -34.6037
if 'longitud_input' not in st.session_state:
    st.session_state.longitud_input = -58.3816
if 'coordenadas_seleccionadas' not in st.session_state:
    st.session_state.coordenadas_seleccionadas = None

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
            'latitud': [-34.0, -34.2]
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
                    'longitud': fila['longitud']
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
                    'longitud': fila['longitud']
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Callback para actualizar coordenadas desde JavaScript
def handle_coords(lat, lng):
    st.session_state.coordenadas_seleccionadas = (lat, lng)
    st.session_state.punto_seleccionado = (lat, lng)
    st.session_state.busqueda_realizada = True

# Mostrar mensaje de instrucciones
with st.sidebar:
    st.info(f"""
    **Instrucciones de configuración:**
    
    El archivo CSV con los datos de productores debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener al menos las columnas: 'cuit', 'titular', 'latitud', 'longitud'
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

# Radio de búsqueda ajustable
radio_busqueda = st.sidebar.slider(
    "Radio de búsqueda (km):", 
    min_value=0.5, 
    max_value=20.0, 
    value=5.0, 
    step=0.5
)

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
        
        # Código HTML y JavaScript para el mapa Leaflet
        mapa_html = f"""
        <div id="map" style="width:100%; height:500px;"></div>
        <div id="selected-coords" style="margin-top:10px; padding:10px; background-color:#f8f9fa; border-radius:5px;">
            Coordenadas del punto seleccionado: <span id="selected-lat">-</span>, <span id="selected-lng">-</span>
            <button id="use-coords" style="margin-left:10px; padding:5px 10px; background-color:#4CAF50; color:white; border:none; border-radius:4px; cursor:pointer;">Usar estas coordenadas</button>
        </div>
        
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        
        <script>
            // Inicializar el mapa
            const map = L.map('map').setView([{centro_lat}, {centro_lon}], 9);
            
            // Agregar capa base de satélite (ESRI) por defecto
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri'
            }}).addTo(map);
            
            // Variable para el marcador del punto seleccionado
            let puntoSeleccionado = null;
            
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
            document.getElementById('use-coords').addEventListener('click', function() {{
                const lat = parseFloat(document.getElementById('selected-lat').textContent);
                const lng = parseFloat(document.getElementById('selected-lng').textContent);
                
                if (!isNaN(lat) && !isNaN(lng)) {{
                    // Enviar datos de vuelta a Streamlit
                    const inputs = parent.document.querySelectorAll('input[type=number]');
                    if (inputs.length >= 2) {{
                        // Actualizar los campos de entrada numérica
                        inputs[0].value = lat;
                        inputs[1].value = lng;
                        
                        // Buscar el botón "Buscar en estas coordenadas" y hacer clic en él
                        const buttons = parent.document.querySelectorAll('button');
                        for (let i = 0; i < buttons.length; i++) {{
                            if (buttons[i].innerText.includes('Buscar en estas coordenadas')) {{
                                buttons[i].click();
                                break;
                            }}
                        }}
                    }}
                }}
            }});
            
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
        st.components.v1.html(mapa_html, height=600)
        
        # Opción para ingresar coordenadas manualmente
        st.subheader("O ingresa coordenadas manualmente:")
        col_lat, col_lon = st.columns(2)
        with col_lat:
            lat_input = st.number_input("Latitud", value=st.session_state.latitud_input, format="%.4f", step=0.001, key="lat_input")
            st.session_state.latitud_input = lat_input
        with col_lon:
            lon_input = st.number_input("Longitud", value=st.session_state.longitud_input, format="%.4f", step=0.001, key="lon_input")
            st.session_state.longitud_input = lon_input
        
        if st.button("Buscar en estas coordenadas"):
            st.session_state.punto_seleccionado = (lat_input, lon_input)
            st.session_state.busqueda_realizada = True
            st.rerun()
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
        
        # Buscar CUITs cercanos
        cuits_cercanos = encontrar_cuits_cercanos(lat, lon, datos_filtrados, radio_km=radio_busqueda)
        
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
        st.info("👈 Haz clic en el mapa o ingresa coordenadas manualmente para ver resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección en mapa**: Haz clic en cualquier punto del mapa.
2. **Usar coordenadas**: Haz clic en el botón "Usar estas coordenadas" para consultar el punto seleccionado.
3. **Resultados**: Verás el productor más cercano y todos los que estén dentro del radio especificado.
4. **Filtros**: Usa los filtros en el panel lateral para mostrar productores específicos.
5. **Radio de búsqueda**: Ajusta el radio para ver productores a mayor o menor distancia.
""")
