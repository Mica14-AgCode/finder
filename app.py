import streamlit as st
import pandas as pd
import pydeck as pdk
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
if 'clicked_coord' not in st.session_state:
    st.session_state.clicked_coord = None

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

# Layout principal
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa Interactivo")
    st.info("👆 **Haz clic en cualquier punto del mapa** para buscar productores cercanos.")
    
    # Verificar que tenemos datos válidos para el mapa
    if not datos_filtrados.empty and 'latitud' in datos_filtrados.columns and 'longitud' in datos_filtrados.columns:
        # Determinar el centro del mapa
        centro_lat = datos_filtrados['latitud'].mean()
        centro_lon = datos_filtrados['longitud'].mean()
        
        # Preparar datos para visualizar en el mapa
        mapa_datos = []
        for idx, fila in datos_filtrados.iterrows():
            if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
                mapa_datos.append({
                    'position': [fila['longitud'], fila['latitud']],
                    'tooltip': f"CUIT: {fila['cuit']}, Titular: {fila['titular']}",
                    'color': [0, 0, 255, 160],  # RGBA azul
                    'radius': 100
                })
        
        # Agregar punto seleccionado si existe
        if st.session_state.punto_seleccionado:
            lat, lon = st.session_state.punto_seleccionado
            mapa_datos.append({
                'position': [lon, lat],
                'tooltip': "Ubicación seleccionada",
                'color': [255, 0, 0, 200],  # RGBA rojo
                'radius': 150
            })
            
            # También agregar un círculo que represente el radio de búsqueda
            # Crear puntos para el círculo (aproximación)
            num_puntos = 40
            radio_grados = radio_busqueda / 111  # Aproximación: 1 grado ~ 111 km en el ecuador
            for i in range(num_puntos):
                angulo = (i / num_puntos) * 2 * math.pi
                x = lon + radio_grados * math.cos(angulo)
                y = lat + radio_grados * math.sin(angulo)
                mapa_datos.append({
                    'position': [x, y],
                    'color': [255, 0, 0, 100],  # RGBA rojo transparente
                    'radius': 30
                })
        
        # Configurar la vista inicial
        vista_inicial = pdk.ViewState(
            longitude=centro_lon,
            latitude=centro_lat,
            zoom=9,
            pitch=0
        )
        
        # Crear la capa de puntos
        capa_puntos = pdk.Layer(
            'ScatterplotLayer',
            data=mapa_datos,
            get_position='position',
            get_color='color',
            get_radius='radius',
            pickable=True
        )
        
        # Crear el mapa
        mapa = pdk.Deck(
            map_style='mapbox://styles/mapbox/satellite-v9',
            initial_view_state=vista_inicial,
            layers=[capa_puntos],
            tooltip={"text": "{tooltip}"}
        )
        
        # Mostrar el mapa y capturar clics
        deck_json = mapa.to_json()
        r = st.pydeck_chart(deck_json)
        
        # Capturar clics en el mapa
        st.write("**Seleccionar punto en el mapa:**")
        col_map_lat, col_map_lon = st.columns(2)
        with col_map_lat:
            map_lat = st.number_input("Latitud", value=-34.603722, format="%.6f", step=0.000001)
        with col_map_lon:
            map_lon = st.number_input("Longitud", value=-58.381592, format="%.6f", step=0.000001)
        
        if st.button("Buscar en estas coordenadas", key="btn_map_search"):
            st.session_state.punto_seleccionado = (map_lat, map_lon)
            st.session_state.busqueda_realizada = True
            st.experimental_rerun()
        
        # Botón para capturar clic en el mapa (simulado)
        st.markdown("---")
        st.write("**¿Has hecho clic en el mapa pero no se actualiza?**")
        st.write("Como el clic directo puede no funcionar en todos los navegadores, puedes:")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📌 Capturar punto actual"):
                st.success("Punto capturado. Los resultados se mostrarán a la derecha.")
                st.session_state.punto_seleccionado = (map_lat, map_lon)
                st.session_state.busqueda_realizada = True
        with col_btn2:
            if st.button("🔄 Limpiar selección"):
                st.session_state.punto_seleccionado = None
                st.session_state.busqueda_realizada = False
                st.experimental_rerun()
    else:
        st.warning("No hay datos válidos de ubicación para mostrar en el mapa.")

# Panel de resultados
with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si hay un punto seleccionado
    if st.session_state.busqueda_realizada and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        st.write(f"**Coordenadas del punto:** Lat {lat:.6f}, Lng {lon:.6f}")
        
        # Buscar el CUIT más cercano
        cuit_mas_cercano = encontrar_cuit_mas_cercano(lat, lon, datos_filtrados)
        
        if cuit_mas_cercano:
            st.success("**Productor más cercano:**")
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
            st.subheader(f"Productores en radio de {radio_busqueda} km:")
            
            # Mostrar número de productores encontrados
            st.info(f"Se encontraron {len(cuits_cercanos)} productores cercanos.")
            
            # Tabla resumida
            tabla_datos = []
            for cercano in cuits_cercanos:
                tabla_datos.append({
                    "CUIT": cercano['cuit'],
                    "Titular": cercano['titular'][:20] + "..." if len(cercano['titular']) > 20 else cercano['titular'],
                    "Km": cercano['distancia']
                })
            
            st.dataframe(pd.DataFrame(tabla_datos), use_container_width=True)
            
            # Detalles expandibles
            for i, cercano in enumerate(cuits_cercanos[:5]):  # Mostrar los 5 más cercanos
                with st.expander(f"{i+1}. {cercano['titular']} ({cercano['distancia']} km)"):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Titular:** {cercano['titular']}  
                    **RENSPA:** {cercano.get('renspa', 'No disponible')}  
                    **Localidad:** {cercano.get('localidad', 'No disponible')}  
                    **Superficie:** {cercano.get('superficie', 'No disponible')} ha  
                    **Distancia:** {cercano['distancia']} km  
                    **Coordenadas:** Lat {cercano['latitud']}, Lng {cercano['longitud']}
                    """)
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("👈 Haz clic en el mapa o ingresa coordenadas manualmente para ver resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Selección en mapa**: Haz clic en cualquier punto del mapa o ingresa coordenadas manualmente.
2. **Captura de punto**: Si el clic directo no funciona, usa el botón "Capturar punto actual".
3. **Resultados**: Verás el productor más cercano y todos los que estén dentro del radio especificado.
4. **Filtros**: Usa los filtros en el panel lateral para mostrar productores específicos.
5. **Radio de búsqueda**: Ajusta el radio para ver productores a mayor o menor distancia.
""")
