import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static, st_folium
import math
import json

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

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

# Función para crear polígono desde WKT
def wkt_a_coordenadas(wkt_str):
    """Convierte un string WKT de polígono a una lista de coordenadas [lat, lon]"""
    if not wkt_str or not isinstance(wkt_str, str):
        return None
    
    try:
        # Extraer las coordenadas del formato WKT POLYGON
        coords_str = wkt_str.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
        
        # Separar las coordenadas por coma
        coords_pairs = coords_str.split(',')
        
        # Convertir a pares de [lat, lon] (folium usa lat, lon en este orden)
        coords = []
        for pair in coords_pairs:
            lon, lat = map(float, pair.strip().split())
            coords.append([lat, lon])  # Invertido para folium
        
        return coords
    except Exception as e:
        st.warning(f"Error al convertir polígono WKT: {e}")
        return None

# Función para cargar y procesar los datos
@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """Carga los datos de productores desde un archivo CSV"""
    try:
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        
        # Procesar polígonos si existen
        if 'poligono' in df.columns:
            df['coords'] = df['poligono'].apply(wkt_a_coordenadas)
        
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
                    'coords': fila.get('coords')
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
                    'coords': fila.get('coords')
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Mostrar mensaje de instrucciones
with st.sidebar:
    st.info(f"""
    **Instrucciones de configuración:**
    
    El archivo CSV con los datos de productores debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener al menos las columnas: 'cuit', 'titular', 'latitud', 'longitud'
    4. Opcionalmente: 'poligono' en formato WKT para visualizar los campos
    """)

# Cargar datos
datos_productores = cargar_datos()

# Crear un sidebar para filtros
st.sidebar.header("Filtros")

# Filtro por CUIT
cuits_disponibles = ["Todos"] + sorted(list(datos_productores['cuit'].unique()))
cuit_seleccionado = st.sidebar.selectbox("Filtrar por CUIT:", cuits_disponibles)

# Filtro por localidad si existe
if 'localidad' in datos_productores.columns:
    localidades = ["Todas"] + sorted(list(datos_productores['localidad'].unique()))
    localidad_seleccionada = st.sidebar.selectbox("Filtrar por localidad:", localidades)
    
    if localidad_seleccionada != "Todas":
        datos_filtrados = datos_productores[datos_productores['localidad'] == localidad_seleccionada]
    else:
        datos_filtrados = datos_productores
else:
    datos_filtrados = datos_productores

# Aplicar filtro de CUIT
if cuit_seleccionado != "Todos":
    datos_filtrados = datos_filtrados[datos_filtrados['cuit'] == cuit_seleccionado]

# Radio de búsqueda ajustable
radio_busqueda = st.sidebar.slider(
    "Radio de búsqueda (km):", 
    min_value=0.5, 
    max_value=20.0, 
    value=5.0, 
    step=0.5
)

# Determinar el centro del mapa
if not datos_filtrados.empty and 'latitud' in datos_filtrados.columns and 'longitud' in datos_filtrados.columns:
    centro_mapa = [
        datos_filtrados['latitud'].mean(),
        datos_filtrados['longitud'].mean()
    ]
else:
    # Valores por defecto (centro de Argentina)
    centro_mapa = [-34.603722, -58.381592]

# Crear el mapa con folium
m = folium.Map(location=centro_mapa, zoom_start=7)

# Agregar capa base de satélite
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Satélite',
    overlay=False
).add_to(m)

# Agregar los marcadores/polígonos de los campos al mapa
for idx, fila in datos_filtrados.iterrows():
    try:
        # Información para el popup
        cuit = fila['cuit']
        titular = fila['titular'] if 'titular' in fila else 'No disponible'
        renspa = fila['renspa'] if 'renspa' in fila else 'No disponible'
        superficie = fila['superficie'] if 'superficie' in fila else 'No disponible'
        localidad = fila['localidad'] if 'localidad' in fila else 'No disponible'
        
        # Contenido del popup
        popup_content = f"""
        <b>CUIT:</b> {cuit}<br>
        <b>Titular:</b> {titular}<br>
        <b>RENSPA:</b> {renspa}<br>
        <b>Superficie:</b> {superficie} ha<br>
        <b>Localidad:</b> {localidad}
        """
        
        # Si tiene polígono, agregar al mapa
        if 'coords' in fila and fila['coords'] is not None:
            folium.Polygon(
                locations=fila['coords'],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=f"CUIT: {cuit}",
                color='blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)
        # Si no tiene polígono pero tiene coordenadas, agregar un marcador
        elif pd.notna(fila.get('latitud')) and pd.notna(fila.get('longitud')):
            folium.Marker(
                location=[fila['latitud'], fila['longitud']],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=f"CUIT: {cuit}",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
    except Exception as e:
        st.warning(f"Error al agregar elemento al mapa: {e}")
        continue

# Agregar control de capas
folium.LayerControl().add_to(m)

# Contenedor para mostrar el mapa y resultados
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa Interactivo")
    
    # Mensaje instructivo
    st.info("Haz clic en el mapa para seleccionar una ubicación y ver los productores cercanos.")
    
    # Renderizar el mapa interactivo y capturar eventos de clic
    map_data = st_folium(m, width=800, height=500)
    
    # Procesar el clic en el mapa
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lng = map_data["last_clicked"]["lng"]
        
        # Guardar las coordenadas en session_state
        st.session_state.punto_seleccionado = (clicked_lat, clicked_lng)
        st.session_state.busqueda_realizada = True
        
        # Mostrar las coordenadas seleccionadas
        st.success(f"Ubicación seleccionada: Lat {clicked_lat:.6f}, Lng {clicked_lng:.6f}")
    
    # Opción alternativa para ingresar coordenadas manualmente
    st.subheader("O ingresa coordenadas manualmente")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        latitud = st.number_input("Latitud", value=-34.603722, format="%.6f", step=0.000001)
    with col_lon:
        longitud = st.number_input("Longitud", value=-58.381592, format="%.6f", step=0.000001)
    
    if st.button("Buscar en estas coordenadas"):
        st.session_state.punto_seleccionado = (latitud, longitud)
        st.session_state.busqueda_realizada = True

with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Verificar si se ha seleccionado un punto
    if 'busqueda_realizada' in st.session_state and st.session_state.busqueda_realizada:
        lat, lon = st.session_state.punto_seleccionado
        
        # Buscar el CUIT más cercano
        cuit_mas_cercano = encontrar_cuit_mas_cercano(lat, lon, datos_filtrados)
        
        if cuit_mas_cercano:
            st.subheader("Productor más cercano:")
            st.markdown(f"""
            **CUIT:** {cuit_mas_cercano['cuit']}  
            **Titular:** {cuit_mas_cercano['titular']}  
            **RENSPA:** {cuit_mas_cercano.get('renspa', 'No disponible')}  
            **Localidad:** {cuit_mas_cercano.get('localidad', 'No disponible')}  
            **Superficie:** {cuit_mas_cercano.get('superficie', 'No disponible')} ha  
            **Distancia:** {cuit_mas_cercano['distancia']} km  
            """)
        
        # Buscar CUITs cercanos
        cuits_cercanos = encontrar_cuits_cercanos(lat, lon, datos_filtrados, radio_km=radio_busqueda)
        
        if cuits_cercanos:
            st.subheader(f"Productores cercanos (radio {radio_busqueda} km):")
            
            # Mostrar cuántos productores se encontraron
            st.info(f"Se encontraron {len(cuits_cercanos)} productores en el radio especificado.")
            
            # Mostrar los productores cercanos
            for i, cercano in enumerate(cuits_cercanos[:5]):  # Mostrar los 5 más cercanos
                with st.expander(f"{i+1}. {cercano['titular']} ({cercano['distancia']} km)"):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Titular:** {cercano['titular']}  
                    **RENSPA:** {cercano.get('renspa', 'No disponible')}  
                    **Localidad:** {cercano.get('localidad', 'No disponible')}  
                    **Superficie:** {cercano.get('superficie', 'No disponible')} ha  
                    **Distancia:** {cercano['distancia']} km  
                    """)
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("Selecciona un punto en el mapa o ingresa coordenadas manualmente para ver resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección en mapa**: Haz clic en cualquier punto del mapa para seleccionar una ubicación.
2. **Coordenadas manuales**: Alternativamente, puedes ingresar coordenadas exactas y hacer clic en "Buscar".
3. **Filtrado**: Usa los filtros en el panel lateral para mostrar productores específicos.
4. **Radio de búsqueda**: Ajusta el radio para ver productores a mayor o menor distancia del punto seleccionado.
5. **Resultados**: El sistema mostrará el productor más cercano y todos los que estén dentro del radio especificado.
""")

# Inicializar variables de estado si no existen
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
