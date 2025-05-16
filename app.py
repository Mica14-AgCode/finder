import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Draw, Geocoder
from streamlit_folium import st_folium
import math
from shapely.geometry import Point, Polygon
import re
import json
import branca.colormap as cm

# Configuración de página
st.set_page_config(
    page_title="Visor de Parcelas Agrícolas",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem;}
    h1, h2, h3 {color: #2c6e49;}
    .stButton>button {background-color: #2c6e49; color: white;}
    .stButton>button:hover {background-color: #214d36;}
    .st-bx {border: 1px solid #eee; border-radius: 5px; padding: 1rem;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Título y descripción
st.title("Visor de Parcelas Agrícolas")
st.markdown("""
Este sistema permite visualizar parcelas agrícolas y buscar productores cercanos a un punto geográfico.
Seleccione un punto en el mapa o ingrese coordenadas para encontrar parcelas cercanas.
""")

# Función para cargar datos
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('data.csv')
        # Asegurarse de que las coordenadas sean numéricas
        df['latitud'] = pd.to_numeric(df['latitud'], errors='coerce')
        df['longitud'] = pd.to_numeric(df['longitud'], errors='coerce')
        
        # Limpiar y formatear los datos de polígonos
        df['poligono_formatted'] = df['poligono'].apply(format_polygon)
        
        # Eliminar filas con coordenadas nulas
        df = df.dropna(subset=['latitud', 'longitud'])
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return pd.DataFrame()

# Función para formatear polígonos de formato personalizado a formato compatible con folium
def format_polygon(polygon_str):
    if not isinstance(polygon_str, str):
        return None
    
    try:
        # Extraer coordenadas del formato (lat,lon), (lat,lon), ...
        coords_pattern = r'\(([^)]+)\)'
        coords_matches = re.findall(coords_pattern, polygon_str)
        
        if not coords_matches:
            return None
        
        coordinates = []
        for coord_pair in coords_matches:
            try:
                lat, lon = map(float, coord_pair.split(','))
                coordinates.append([lat, lon])  # Folium usa [lat, lon]
            except:
                continue
        
        return coordinates if coordinates else None
    except:
        return None

# Función para calcular la distancia Haversine
def haversine_distance(lat1, lon1, lat2, lon2):
    # Radio de la Tierra en kilómetros
    R = 6371.0
    
    # Convertir grados a radianes
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Diferencia de longitud y latitud
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

# Función para verificar si un punto está dentro de un polígono
def point_in_polygon(point, polygon):
    if polygon is None or not polygon:
        return False
    
    try:
        # Crear objeto Point de Shapely
        point_obj = Point(point)
        
        # Crear objeto Polygon de Shapely
        polygon_obj = Polygon(polygon)
        
        # Verificar si el punto está dentro del polígono
        return polygon_obj.contains(point_obj)
    except:
        return False

# Función para buscar productores cercanos a un punto
def find_nearby_producers(df, lat, lon, radius_km):
    nearby = []
    
    for _, row in df.iterrows():
        # Calcular distancia
        dist = haversine_distance(lat, lon, row['latitud'], row['longitud'])
        
        # Verificar si está dentro del radio
        if dist <= radius_km:
            # Verificar si el punto está dentro de algún polígono
            inside_polygon = False
            polygon = row['poligono_formatted']
            if polygon:
                inside_polygon = point_in_polygon((lon, lat), polygon)
            
            # Añadir a resultados
            nearby.append({
                'renspa': row['renspa'],
                'titular': row['titular'],
                'cuit': row['cuit'],
                'localidad': row['localidad'],
                'direccion': row['direccion'],
                'superficie': row['superficie'],
                'latitud': row['latitud'],
                'longitud': row['longitud'],
                'distancia_km': round(dist, 2),
                'dentro_poligono': inside_polygon
            })
    
    # Ordenar por distancia
    nearby.sort(key=lambda x: x['distancia_km'])
    return nearby

# Función para crear mapa base
def create_base_map(lat, lon, zoom=10):
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles='CartoDB positron')
    
    # Añadir control de dibujo
    draw = Draw(
        draw_options={
            'polyline': False,
            'rectangle': False,
            'polygon': False,
            'circle': False,
            'circlemarker': False,
            'marker': True
        },
        edit_options={'edit': False}
    )
    draw.add_to(m)
    
    # Añadir buscador geocoder
    Geocoder().add_to(m)
    
    # Añadir escala
    folium.plugins.MeasureControl(position='bottomleft').add_to(m)
    
    return m

# Función para visualizar resultados en el mapa
def visualize_results(m, point, nearby_producers, show_polygons=True):
    # Añadir marcador para el punto seleccionado
    folium.Marker(
        location=point,
        popup="Punto seleccionado",
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    
    # Añadir círculo para el radio de búsqueda
    folium.Circle(
        location=point,
        radius=radius_km * 1000,  # Convertir a metros
        color="#2c6e49",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)
    
    # Crear mapa de colores para los polígonos según la distancia
    colormap = cm.LinearColormap(
        colors=['green', 'yellow', 'orange', 'red'],
        index=[0, radius_km/3, 2*radius_km/3, radius_km],
        vmin=0,
        vmax=radius_km
    )
    
    # Añadir marcadores y polígonos para los productores cercanos
    for producer in nearby_producers:
        # Definir icono según si el punto está dentro del polígono
        icon_color = "green" if producer['dentro_poligono'] else "blue"
        icon_symbol = "check" if producer['dentro_poligono'] else "info"
        
        # Añadir marcador
        folium.Marker(
            location=[producer['latitud'], producer['longitud']],
            popup=folium.Popup(
                f"""
                <b>{producer['titular']}</b><br>
                RENSPA: {producer['renspa']}<br>
                CUIT: {producer['cuit']}<br>
                Localidad: {producer['localidad']}<br>
                Dirección: {producer['direccion']}<br>
                Superficie: {producer['superficie']} ha<br>
                Distancia: {producer['distancia_km']} km
                """,
                max_width=300
            ),
            icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix="fa"),
            tooltip=f"{producer['titular']} - {producer['distancia_km']} km"
        ).add_to(m)
        
        # Añadir polígono si está disponible y la opción está habilitada
        if show_polygons and 'poligono_formatted' in df.columns:
            polygon = df[df['renspa'] == producer['renspa']]['poligono_formatted'].iloc[0]
            if polygon and len(polygon) > 2:  # Necesita al menos 3 puntos para un polígono
                folium.Polygon(
                    locations=polygon,
                    popup=producer['titular'],
                    color=colormap(producer['distancia_km']),
                    fill=True,
                    fill_opacity=0.4,
                    weight=2
                ).add_to(m)
    
    # Añadir leyenda de colores
    colormap.caption = 'Distancia (km)'
    colormap.add_to(m)
    
    return m

# Inicializar estado de sesión si no existe
if 'lat' not in st.session_state:
    st.session_state.lat = -36.0  # Centro aproximado de la región
if 'lon' not in st.session_state:
    st.session_state.lon = -62.0
if 'selected_point' not in st.session_state:
    st.session_state.selected_point = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# Cargar datos
df = load_data()

# Crear columnas para el layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Mapa Interactivo")
    
    # Control para mostrar/ocultar polígonos
    show_polygons = st.checkbox("Mostrar polígonos", value=True)
    
    # Control de radio de búsqueda
    radius_km = st.slider(
        "Radio de búsqueda (km):", 
        min_value=1.0, 
        max_value=50.0, 
        value=10.0, 
        step=1.0
    )
    
    # Crear mapa base
    m = create_base_map(st.session_state.lat, st.session_state.lon)
    
    # Mostrar el mapa y capturar interacciones
    map_data = st_folium(m, width="100%", height=500)
    
    # Procesar datos del mapa
    if map_data and 'last_clicked' in map_data and map_data['last_clicked']:
        # Obtener coordenadas del punto seleccionado
        lat, lon = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.selected_point = [lat, lon]
        
        # Buscar productores cercanos
        if not df.empty:
            st.session_state.search_results = find_nearby_producers(df, lat, lon, radius_km)
    
    # Mostrar coordenadas actuales
    if st.session_state.selected_point:
        st.info(f"Punto seleccionado: Lat {st.session_state.lat:.6f}, Lon {st.session_state.lon:.6f}")

with col2:
    st.subheader("Buscar por Coordenadas")
    
    # Formulario para buscar por coordenadas
    with st.form("coord_form"):
        input_lat = st.number_input(
            "Latitud:",
            min_value=-90.0,
            max_value=90.0,
            value=st.session_state.lat,
            format="%.6f"
        )
        
        input_lon = st.number_input(
            "Longitud:",
            min_value=-180.0,
            max_value=180.0,
            value=st.session_state.lon,
            format="%.6f"
        )
        
        submitted = st.form_submit_button("Buscar")
        
        if submitted:
            st.session_state.lat = input_lat
            st.session_state.lon = input_lon
            st.session_state.selected_point = [input_lat, input_lon]
            
            # Buscar productores cercanos
            if not df.empty:
                st.session_state.search_results = find_nearby_producers(df, input_lat, input_lon, radius_km)
            
            # Indicar que se debe recargar la página
            st.rerun()
    
    # Mostrar resultados
    st.subheader("Resultados")
    
    if st.session_state.search_results:
        st.write(f"Se encontraron {len(st.session_state.search_results)} productores cercanos:")
        
        # Verificar si hay algún productor cuyo polígono contiene el punto
        inside_polygon_producers = [p for p in st.session_state.search_results if p['dentro_poligono']]
        
        if inside_polygon_producers:
            st.success(f"¡El punto seleccionado está dentro de {len(inside_polygon_producers)} parcela(s)!")
            
            # Mostrar los productores cuya parcela contiene el punto
            for i, producer in enumerate(inside_polygon_producers):
                with st.expander(f"🌱 {producer['titular']} (Parcela Contenedora)", expanded=True):
                    st.write(f"**RENSPA:** {producer['renspa']}")
                    st.write(f"**CUIT:** {producer['cuit']}")
                    st.write(f"**Localidad:** {producer['localidad']}")
                    st.write(f"**Dirección:** {producer['direccion']}")
                    st.write(f"**Superficie:** {producer['superficie']} ha")
                    st.write(f"**Distancia al punto:** {producer['distancia_km']} km")
        
        # Mostrar otros productores cercanos
        other_producers = [p for p in st.session_state.search_results if not p['dentro_poligono']]
        
        if other_producers:
            st.write("#### Otros productores cercanos:")
            
            for i, producer in enumerate(other_producers):
                with st.expander(f"📍 {producer['titular']} - {producer['distancia_km']} km"):
                    st.write(f"**RENSPA:** {producer['renspa']}")
                    st.write(f"**CUIT:** {producer['cuit']}")
                    st.write(f"**Localidad:** {producer['localidad']}")
                    st.write(f"**Dirección:** {producer['direccion']}")
                    st.write(f"**Superficie:** {producer['superficie']} ha")
    else:
        if st.session_state.selected_point:
            st.info("No se encontraron productores en el radio especificado.")
        else:
            st.info("Seleccione un punto en el mapa o ingrese coordenadas para buscar.")

# Si hay un punto seleccionado y resultados, mostrar visualización
if st.session_state.selected_point and st.session_state.search_results:
    st.subheader("Visualización de Resultados")
    
    # Crear mapa con resultados
    result_map = create_base_map(st.session_state.lat, st.session_state.lon, zoom=12)
    result_map = visualize_results(
        result_map, 
        st.session_state.selected_point,
        st.session_state.search_results,
        show_polygons
    )
    
    # Mostrar mapa de resultados
    st_folium(result_map, width="100%", height=500)

# Mostrar información del dataset
st.sidebar.header("Información del Dataset")
if not df.empty:
    st.sidebar.write(f"Total de productores: {len(df)}")
    st.sidebar.write(f"Productores con polígonos: {df['poligono_formatted'].notna().sum()}")
    
    # Mostrar un mapa con todos los puntos
    if st.sidebar.checkbox("Ver mapa general"):
        overview_map = folium.Map(location=[-36.0, -62.0], zoom_start=7, tiles='CartoDB positron')
        
        # Crear cluster de marcadores para mejorar rendimiento
        marker_cluster = folium.plugins.MarkerCluster().add_to(overview_map)
        
        # Añadir marcadores para cada productor
        for _, row in df.sample(min(500, len(df))).iterrows():  # Limitar a 500 para rendimiento
            folium.Marker(
                location=[row['latitud'], row['longitud']],
                popup=row['titular'],
                icon=folium.Icon(color="blue", icon="info", prefix="fa")
            ).add_to(marker_cluster)
        
        st.sidebar.write("Vista general (muestra de 500 productores):")
        st_folium(overview_map, width="100%", height=300)
    
    # Lista de localidades
    localities = df['localidad'].dropna().unique()
    st.sidebar.write(f"Localidades registradas: {len(localities)}")
    
    if st.sidebar.checkbox("Ver lista de localidades"):
        st.sidebar.write(", ".join(sorted(localities)))
else:
    st.sidebar.error("No se pudieron cargar los datos.")

# Información de ayuda
with st.sidebar.expander("Ayuda"):
    st.write("""
    ### Cómo usar esta aplicación:
    
    1. **Seleccionar un punto**: Haga clic en el mapa o ingrese coordenadas manualmente.
    2. **Ajustar radio**: Use el control deslizante para cambiar el radio de búsqueda.
    3. **Ver resultados**: Los productores cercanos se muestran en el panel derecho.
    4. **Visualización**: Los productores cuyas parcelas contienen el punto seleccionado se destacan en verde.
    
    ### Leyenda:
    - 🔴 Punto seleccionado
    - 🟢 Productor cuya parcela contiene el punto
    - 🔵 Otros productores cercanos
    - Polígonos coloreados según distancia (verde=cerca, rojo=lejos)
    """)

# Pie de página
st.sidebar.markdown("---")
st.sidebar.markdown("Desarrollado con ❤️ para agricultores")
st.sidebar.markdown("Versión 1.0.0")
