import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import folium
from streamlit_folium import folium_static
import numpy as np
from geopy.distance import geodesic
import os

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV (debe estar en la misma carpeta que la app)
RUTA_CSV = "datos_productores.csv"

# Cargar datos de productores desde CSV
@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """
    Carga los datos de productores desde un archivo CSV.
    El CSV debe estar en la misma carpeta que la aplicación Streamlit.
    """
    try:
        # Verificar si el archivo existe
        if not os.path.exists(ruta_archivo):
            st.error(f"Error: No se encontró el archivo {ruta_archivo}")
            return crear_datos_demo()
        
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        
        # Verificar si tiene la columna de polígonos
        if 'poligono' in df.columns:
            # Asegurar que no hay valores nulos en la columna de polígonos
            df = df.dropna(subset=['poligono'])
            
            try:
                # Intenta convertir la columna 'poligono' a geometría
                gdf = gpd.GeoDataFrame(
                    df, geometry=gpd.GeoSeries.from_wkt(df['poligono']), crs="EPSG:4326"
                )
            except Exception as e:
                st.warning(f"Error al convertir los polígonos: {e}. Usando coordenadas de puntos en su lugar.")
                gdf = gpd.GeoDataFrame(
                    df, geometry=gpd.points_from_xy(df['longitud'], df['latitud']), crs="EPSG:4326"
                )
        else:
            # Si no tiene polígonos, usar latitud/longitud
            gdf = gpd.GeoDataFrame(
                df, geometry=gpd.points_from_xy(df['longitud'], df['latitud']), crs="EPSG:4326"
            )
        return gdf
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return crear_datos_demo()

def crear_datos_demo():
    """Crea un conjunto de datos de demostración"""
    return gpd.GeoDataFrame(
        {
            'cuit': ['20123456789', '30987654321'],
            'nombre': ['Productor Ejemplo 1', 'Productor Ejemplo 2'],
            'localidad': ['Localidad 1', 'Localidad 2'],
            'geometry': [
                Polygon([(-60.0, -34.0), (-60.1, -34.0), (-60.1, -34.1), (-60.0, -34.1)]),
                Polygon([(-60.2, -34.2), (-60.3, -34.2), (-60.3, -34.3), (-60.2, -34.3)])
            ]
        }, crs="EPSG:4326"
    )

# Mostrar mensaje de instrucciones para el archivo
with st.sidebar:
    st.info(f"""
    **Instrucciones de configuración:**
    
    El archivo CSV con los datos de productores debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener las columnas: 'cuit', 'titular', 'longitud', 'latitud', etc.
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

# Función para encontrar el CUIT asociado a un punto y los CUITs cercanos
def encontrar_cuits(lat, lon, datos, radio_km=5):
    """
    Encuentra el CUIT asociado a un punto y los CUITs cercanos.
    
    Args:
        lat: Latitud del punto
        lon: Longitud del punto
        datos: GeoDataFrame con los datos de productores
        radio_km: Radio de búsqueda en kilómetros
        
    Returns:
        (cuit_exacto, cuits_cercanos): Tupla con el CUIT exacto y una lista de CUITs cercanos
    """
    punto = Point(lon, lat)
    
    # Verificar si el punto está dentro de algún polígono
    dentro = None
    for idx, fila in datos.iterrows():
        if punto.within(fila.geometry):
            dentro = {
                'cuit': fila['cuit'],
                'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                'tipo': 'Exacto'
            }
            break
    
    # Encontrar CUITs cercanos basados en la distancia al centroide del polígono
    cercanos = []
    punto_coords = (lat, lon)
    
    for idx, fila in datos.iterrows():
        # Calcular el centroide del polígono
        centroide = fila.geometry.centroid
        centroide_coords = (centroide.y, centroide.x)
        
        # Calcular distancia
        distancia = geodesic(punto_coords, centroide_coords).kilometers
        
        if distancia <= radio_km:
            cercanos.append({
                'cuit': fila['cuit'],
                'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                'distancia': round(distancia, 2),
                'tipo': 'Cercano'
            })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return dentro, cercanos

# Configurar el mapa inicial
# Centro del mapa en Argentina
centro_mapa = [-34.603722, -58.381592]  # Buenos Aires por defecto

# Calcular un centro mejor basado en los datos si es posible
if not datos_filtrados.empty:
    centro_mapa = [
        datos_filtrados.geometry.centroid.y.mean(),
        datos_filtrados.geometry.centroid.x.mean()
    ]

# Crear el mapa con folium
m = folium.Map(location=centro_mapa, zoom_start=7)

# Agregar capa base de satélite
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Satélite',
    overlay=False
).add_to(m)

# Agregar los polígonos de los campos al mapa
for idx, fila in datos_filtrados.iterrows():
    try:
        # Extraer información para el popup
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
        
        # Crear el polígono en el mapa
        if hasattr(fila.geometry, 'exterior'):
            # Es un polígono
            coords = [(y, x) for x, y in fila.geometry.exterior.coords]
            
            folium.Polygon(
                locations=coords,
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=f"CUIT: {cuit}",
                color='blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)
        else:
            # Es un punto
            folium.CircleMarker(
                location=[fila.geometry.y, fila.geometry.x],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=f"CUIT: {cuit}",
                color='blue',
                fill=True,
                fill_opacity=0.2,
                radius=50
            ).add_to(m)
    except Exception as e:
        continue  # Ignorar geometrías problemáticas

# Agregar control de capas
folium.LayerControl().add_to(m)

# Contenedor para mostrar el mapa y resultados lado a lado
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa de Productores")
    
    # Mostrar el mapa
    folium_static(m, width=800, height=600)
    
    # Campos para ingresar coordenadas manualmente
    st.subheader("Ingresar coordenadas manualmente")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        latitud = st.number_input("Latitud", value=-34.603722, format="%.6f", step=0.000001)
    with col_lon:
        longitud = st.number_input("Longitud", value=-58.381592, format="%.6f", step=0.000001)
    
    if st.button("Buscar en estas coordenadas"):
        st.session_state.punto_seleccionado = (latitud, longitud)
        st.session_state.busqueda_realizada = True

with col2:
    st.subheader("Resultados")
    
    # Verificar si se ha seleccionado un punto
    if 'busqueda_realizada' in st.session_state and st.session_state.busqueda_realizada:
        lat, lon = st.session_state.punto_seleccionado
        
        # Buscar CUIT exacto y cercanos
        cuit_exacto, cuits_cercanos = encontrar_cuits(lat, lon, datos_filtrados, radio_km=radio_busqueda)
        
        if cuit_exacto:
            st.success(f"**Campo encontrado en el punto exacto:**")
            st.markdown(f"""
            **CUIT:** {cuit_exacto['cuit']}  
            **Titular:** {cuit_exacto['titular']}  
            **RENSPA:** {cuit_exacto['renspa']}  
            **Superficie:** {cuit_exacto['superficie']} ha  
            **Localidad:** {cuit_exacto['localidad']}  
            """)
        else:
            st.info("No se encontró ningún campo en esta ubicación exacta.")
        
        if cuits_cercanos:
            st.subheader(f"Productores cercanos (radio {radio_busqueda} km):")
            for i, cercano in enumerate(cuits_cercanos[:5]):  # Mostrar los 5 más cercanos
                with st.expander(f"{i+1}. CUIT: {cercano['cuit']} - {cercano['titular']} ({cercano['distancia']} km)"):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Titular:** {cercano['titular']}  
                    **RENSPA:** {cercano['renspa']}  
                    **Localidad:** {cercano['localidad']}  
                    **Distancia:** {cercano['distancia']} km  
                    """)
        else:
            st.info(f"No se encontraron productores cercanos en un radio de {radio_busqueda} km.")
    else:
        st.info("Selecciona un punto en el mapa o ingresa coordenadas para ver los resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Filtrado**: Usa los filtros en el panel lateral para mostrar productores específicos.
2. **Selección en mapa**: Haz clic en el mapa para consultar un punto.
3. **Coordenadas manuales**: O puedes ingresar las coordenadas manualmente y hacer clic en "Buscar".
4. **Resultados**: El sistema mostrará si el punto seleccionado pertenece a un campo registrado y qué productores están cercanos.
""")

# Inicializar variables de estado si no existen
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
