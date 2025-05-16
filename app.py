import streamlit as st
import pandas as pd
import math
import os
import json
import folium
from folium.plugins import Draw, Geocoder
from streamlit_folium import st_folium
import re
from shapely.geometry import Point, Polygon
import branca.colormap as cm

# Configuración de la página
st.set_page_config(
    page_title="Visor de Productores Agrícolas", 
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

# Título de la aplicación
st.title("Visor de Productores Agrícolas")
st.markdown("""
Este sistema permite visualizar parcelas agrícolas y buscar productores cercanos a un punto geográfico.
Seleccione un punto en el mapa o ingrese coordenadas para encontrar parcelas cercanas.
""")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

# Inicializar variables de estado
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'radio_busqueda' not in st.session_state:
    st.session_state.radio_busqueda = 10.0
if 'mostrar_resultado' not in st.session_state:
    st.session_state.mostrar_resultado = False
if 'lat' not in st.session_state:
    st.session_state.lat = -36.0  # Centro aproximado de la región
if 'lon' not in st.session_state:
    st.session_state.lon = -62.0
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

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

def formato_a_poligono(poligono_str):
    """
    Convertir el formato actual de polígonos (ya sea WKT o formato personalizado) 
    a un formato que pueda usar Folium
    """
    if not poligono_str or not isinstance(poligono_str, str):
        return None
    
    try:
        # Primero verificar si es formato WKT
        if poligono_str.strip().upper().startswith('POLYGON'):
            # Extraer las coordenadas del polígono WKT
            coords_str = poligono_str.replace('POLYGON', '').replace('((', '').replace('))', '').strip()
            
            # Separar las coordenadas por coma
            coords_pares = coords_str.split(',')
            
            # Convertir a pares de [lat, lon] para Folium
            coords = []
            for par in coords_pares:
                valores = par.strip().split()
                if len(valores) >= 2:
                    # En WKT es lon lat, pero en Folium necesitamos lat lon
                    lon, lat = float(valores[0]), float(valores[1])
                    coords.append([lat, lon])
        else:
            # Intentar formato alternativo como "(lat,lon), (lat,lon)..."
            coords_pattern = r'\(([^)]+)\)'
            coords_matches = re.findall(coords_pattern, poligono_str)
            
            if not coords_matches:
                return None
            
            coords = []
            for coord_pair in coords_matches:
                try:
                    lat, lon = map(float, coord_pair.split(','))
                    coords.append([lat, lon])  # Folium usa [lat, lon]
                except:
                    continue
        
        return coords if coords else None
    except Exception as e:
        st.error(f"Error al procesar polígono: {str(e)}")
        return None

def punto_en_poligono(point, polygon):
    """
    Verifica si un punto está dentro de un polígono usando Shapely.
    Point es una tupla (lon, lat) y polygon es una lista de coordenadas [[lat, lon], ...]
    """
    if polygon is None or not polygon:
        return False
    
    try:
        # Crear objeto Point de Shapely (x=lon, y=lat)
        point_obj = Point(point)
        
        # Convertir Folium polygon [lat, lon] a formato Shapely [lon, lat]
        shapely_coords = [(coord[1], coord[0]) for coord in polygon]
        
        # Crear objeto Polygon de Shapely
        polygon_obj = Polygon(shapely_coords)
        
        # Verificar si el punto está dentro del polígono
        return polygon_obj.contains(point_obj)
    except Exception as e:
        st.error(f"Error al verificar punto en polígono: {str(e)}")
        return False

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

        # Asegurarse de que las coordenadas sean numéricas
        df['latitud'] = pd.to_numeric(df['latitud'], errors='coerce')
        df['longitud'] = pd.to_numeric(df['longitud'], errors='coerce')
        
        # Formatear los polígonos
        if 'poligono' in df.columns:
            df['poligono_formatted'] = df['poligono'].apply(formato_a_poligono)
        
        # Eliminar filas con coordenadas nulas
        df = df.dropna(subset=['latitud', 'longitud'])
        
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return crear_datos_ejemplo()

def encontrar_productor_contenedor(lat, lon, datos):
    """Encuentra el productor cuyo polígono contiene el punto dado"""
    productor_contenedor = None
    
    if 'poligono_formatted' in datos.columns:
        for idx, fila in datos.iterrows():
            if pd.notna(fila['poligono_formatted']):
                if punto_en_poligono((lon, lat), fila['poligono_formatted']):
                    productor_contenedor = {
                        'cuit': fila['cuit'],
                        'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                        'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                        'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                        'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                        'distancia': 0,  # Distancia 0 porque está dentro del polígono
                        'latitud': fila['latitud'],
                        'longitud': fila['longitud'],
                        'poligono_formatted': fila['poligono_formatted'],
                        'dentro_poligono': True
                    }
                    break
    
    return productor_contenedor

def encontrar_productores_cercanos(lat, lon, datos, radio_km=10):
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
                    'poligono_formatted': fila.get('poligono_formatted', None),
                    'dentro_poligono': False
                })
                cuits_encontrados.add(fila['cuit'])
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    return cercanos

# Función para crear mapa base
def crear_mapa_base(lat, lon, zoom=10):
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
    
    # Añadir capas base adicionales
    folium.TileLayer('CartoDB dark_matter', name='Dark Mode').add_to(m)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                   name='Satellite', attr='Esri').add_to(m)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                   name='Google Map', attr='Google').add_to(m)
    
    # Añadir control de capas
    folium.LayerControl().add_to(m)
    
    # Añadir escala
    folium.plugins.MeasureControl(position='bottomleft').add_to(m)
    
    return m

# Función para visualizar resultados en el mapa
def visualizar_resultados(m, point, resultados, radio_km):
    # Añadir marcador para el punto seleccionado
    folium.Marker(
        location=point,
        popup="Punto seleccionado",
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    
    # Añadir círculo para el radio de búsqueda
    folium.Circle(
        location=point,
        radius=radio_km * 1000,  # Convertir a metros
        color="#2c6e49",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)
    
    # Crear mapa de colores para los polígonos según la distancia
    colormap = cm.LinearColormap(
        colors=['green', 'yellow', 'orange', 'red'],
        index=[0, radio_km/3, 2*radio_km/3, radio_km],
        vmin=0,
        vmax=radio_km
    )
    
    # Añadir marcadores y polígonos para los productores cercanos
    for productor in resultados:
        # Definir icono según si el punto está dentro del polígono
        icon_color = "green" if productor.get('dentro_poligono', False) else "blue"
        icon_symbol = "check" if productor.get('dentro_poligono', False) else "info"
        
        # Añadir marcador
        folium.Marker(
            location=[productor['latitud'], productor['longitud']],
            popup=folium.Popup(
                f"""
                <b>{productor['titular']}</b><br>
                CUIT: {productor['cuit']}<br>
                RENSPA: {productor.get('renspa', 'No disponible')}<br>
                Localidad: {productor.get('localidad', 'No disponible')}<br>
                Superficie: {productor.get('superficie', 'No disponible')} ha<br>
                Distancia: {productor['distancia']} km
                """,
                max_width=300
            ),
            icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix="fa"),
            tooltip=f"{productor['titular']} - {productor['distancia']} km"
        ).add_to(m)
        
        # Añadir polígono si está disponible
        if productor.get('poligono_formatted') and len(productor['poligono_formatted']) > 2:
            folium.Polygon(
                locations=productor['poligono_formatted'],
                popup=productor['titular'],
                color=colormap(productor['distancia']),
                fill=True,
                fill_opacity=0.4,
                weight=2
            ).add_to(m)
    
    # Añadir leyenda de colores
    colormap.caption = 'Distancia (km)'
    colormap.add_to(m)
    
    return m

# Cargar datos
datos_productores = cargar_datos()

# Si hay datos, mostrar información básica
if not datos_productores.empty:
    # Contar CUITs únicos
    cuits_unicos = datos_productores['cuit'].nunique()
    st.success(f"Datos cargados correctamente: {len(datos_productores)} parcelas de {cuits_unicos} productores")

# Panel lateral
with st.sidebar:
    st.header("Configuración")
    
    # Radio de búsqueda
    radio_busqueda = st.slider(
        "Radio de búsqueda (km):",
        min_value=1.0,
        max_value=500.0,
        value=st.session_state.radio_busqueda,
        step=1.0
    )
    st.session_state.radio_busqueda = radio_busqueda
    
    # Control para mostrar/ocultar polígonos
    mostrar_poligonos = st.checkbox("Mostrar polígonos", value=True)
    
    # Información del dataset
    st.header("Información del Dataset")
    if not datos_productores.empty:
        st.write(f"Total de parcelas: {len(datos_productores)}")
        st.write(f"Total de productores: {datos_productores['cuit'].nunique()}")
        
        if 'poligono_formatted' in datos_productores.columns:
            poligonos_validos = datos_productores['poligono_formatted'].notna().sum()
            st.write(f"Parcelas con polígonos: {poligonos_validos}")
        
        # Mostrar un mapa con todos los puntos
        if st.checkbox("Ver mapa general"):
            overview_map = folium.Map(location=[-36.0, -62.0], zoom_start=7, tiles='CartoDB positron')
            
            # Crear cluster de marcadores para mejorar rendimiento
            marker_cluster = folium.plugins.MarkerCluster().add_to(overview_map)
            
            # Añadir marcadores para cada productor
            for _, row in datos_productores.sample(min(500, len(datos_productores))).iterrows():  # Limitar a 500 para rendimiento
                folium.Marker(
                    location=[row['latitud'], row['longitud']],
                    popup=row['titular'],
                    icon=folium.Icon(color="blue", icon="info", prefix="fa")
                ).add_to(marker_cluster)
            
            st.write("Vista general (muestra de 500 productores):")
            st_folium(overview_map, width="100%", height=300)
    
    # Instrucciones
    with st.expander("Instrucciones de uso"):
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

# Layout principal
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa Interactivo")
    
    # Crear mapa base
    m = crear_mapa_base(st.session_state.lat, st.session_state.lon)
    
    # Si hay un punto seleccionado y resultados, mostrar visualización
    if st.session_state.punto_seleccionado and st.session_state.mostrar_resultado:
        # Obtener resultados actualizados con el radio actual
        lat, lon = st.session_state.punto_seleccionado
        st.session_state.search_results = encontrar_productores_cercanos(
            lat, lon, datos_productores, radio_km=radio_busqueda
        )
        
        # Visualizar resultados en el mapa
        if mostrar_poligonos:
            m = visualizar_resultados(m, st.session_state.punto_seleccionado, 
                                     st.session_state.search_results, radio_busqueda)
        else:
            # Si no mostramos polígonos, usamos el mismo mapa pero sin añadir polígonos
            m = visualizar_resultados(m, st.session_state.punto_seleccionado, 
                                     [p for p in st.session_state.search_results if True], 
                                     radio_busqueda)
    
    # Mostrar el mapa y capturar interacciones
    map_data = st_folium(m, width="100%", height=500)
    
    # Procesar datos del mapa
    if map_data and 'last_clicked' in map_data and map_data['last_clicked']:
        # Obtener coordenadas del punto seleccionado
        lat, lon = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.punto_seleccionado = [lat, lon]
        
        # Buscar productores cercanos
        if not datos_productores.empty:
            st.session_state.search_results = encontrar_productores_cercanos(
                lat, lon, datos_productores, radio_km=radio_busqueda
            )
            st.session_state.mostrar_resultado = True
            
            # Recargar la página para mostrar los resultados
            # Usando st.rerun() en lugar de experimental_rerun
            st.rerun()
    
    # Mostrar coordenadas actuales
    if st.session_state.punto_seleccionado:
        st.info(f"Punto seleccionado: Lat {st.session_state.punto_seleccionado[0]:.6f}, Lon {st.session_state.punto_seleccionado[1]:.6f}")
    
    # Formulario para entrada manual de coordenadas
    with st.expander("Buscar por coordenadas"):
        with st.form("coord_form"):
            col_lat, col_lon = st.columns(2)
            
            with col_lat:
                input_lat = st.number_input(
                    "Latitud:",
                    min_value=-90.0,
                    max_value=90.0,
                    value=st.session_state.lat if st.session_state.punto_seleccionado else -36.0,
                    format="%.6f"
                )
            
            with col_lon:
                input_lon = st.number_input(
                    "Longitud:",
                    min_value=-180.0,
                    max_value=180.0,
                    value=st.session_state.lon if st.session_state.punto_seleccionado else -62.0,
                    format="%.6f"
                )
            
            buscar_submitted = st.form_submit_button("Buscar en estas coordenadas")
            
            if buscar_submitted:
                st.session_state.lat = input_lat
                st.session_state.lon = input_lon
                st.session_state.punto_seleccionado = [input_lat, input_lon]
                
                # Buscar productores cercanos
                if not datos_productores.empty:
                    st.session_state.search_results = encontrar_productores_cercanos(
                        input_lat, input_lon, datos_productores, radio_km=radio_busqueda
                    )
                    st.session_state.mostrar_resultado = True
                
                # Recargar la página
                st.rerun()

with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si tenemos un punto seleccionado
    if st.session_state.mostrar_resultado and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        if st.session_state.search_results:
            # Contar razones sociales únicas
            cuits_unicos = len(set(productor['cuit'] for productor in st.session_state.search_results))
            st.success(f"Se encontraron {cuits_unicos} productores en un radio de {radio_busqueda} km")
            
            # Verificar si hay productores cuyo polígono contiene el punto
            productores_contenedores = [p for p in st.session_state.search_results if p.get('dentro_poligono', False)]
            
            if productores_contenedores:
                st.subheader("Parcela que contiene este punto:")
                
                for productor in productores_contenedores:
                    with st.expander(f"🌱 {productor['titular']}", expanded=True):
                        st.markdown(f"""
                        **CUIT:** {productor['cuit']}  
                        **Razón Social:** {productor['titular']}  
                        **RENSPA:** {productor.get('renspa', 'No disponible')}  
                        **Localidad:** {productor.get('localidad', 'No disponible')}  
                        **Superficie:** {productor.get('superficie', 'No disponible')} ha  
                        **Distancia:** {productor['distancia']} km  
                        **Coordenadas:** Lat {productor['latitud']:.6f}, Lng {productor['longitud']:.6f}
                        """)
            
            # Mostrar otros productores cercanos
            other_productores = [p for p in st.session_state.search_results if not p.get('dentro_poligono', False)]
            
            if other_productores:
                st.subheader("Otros productores cercanos:")
                
                # Crear un DataFrame para la tabla
                tabla_data = []
                for productor in other_productores:
                    tabla_data.append({
                        "CUIT": productor['cuit'],
                        "Razón Social": productor['titular'],
                        "Distancia (km)": productor['distancia'],
                        "Localidad": productor.get('localidad', ''),
                    })
                
                # Mostrar tabla
                st.dataframe(pd.DataFrame(tabla_data), use_container_width=True)
                
                # Mostrar detalles expandibles para los más cercanos
                for i, productor in enumerate(other_productores[:10]):  # Limitar a los 10 más cercanos
                    with st.expander(f"📍 {productor['titular']} - {productor['distancia']} km"):
                        st.markdown(f"""
                        **CUIT:** {productor['cuit']}  
                        **Razón Social:** {productor['titular']}  
                        **RENSPA:** {productor.get('renspa', 'No disponible')}  
                        **Localidad:** {productor.get('localidad', 'No disponible')}  
                        **Superficie:** {productor.get('superficie', 'No disponible')} ha  
                        **Distancia:** {productor['distancia']} km  
                        **Coordenadas:** Lat {productor['latitud']:.6f}, Lng {productor['longitud']:.6f}
                        """)
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("Haz clic en el mapa para seleccionar un punto y buscar productores cercanos")

# Pie de página
st.markdown("---")
st.markdown("Desarrollado con ❤️ para productores agrícolas")
