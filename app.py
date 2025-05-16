import streamlit as st
import pandas as pd
import math
import os

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

# Inicializar variables de estado si no existen
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

# Formulario de búsqueda
st.header("Buscar por coordenadas")

col1, col2 = st.columns(2)
with col1:
    latitud = st.number_input("Latitud:", value=-34.603722, format="%.6f")
with col2:
    longitud = st.number_input("Longitud:", value=-58.381592, format="%.6f")

if st.button("Buscar productores cercanos", type="primary", use_container_width=True):
    with st.spinner(f"Buscando productores en un radio de {radio_busqueda} km..."):
        # Buscar productores cercanos
        productores_cercanos = encontrar_cuits_cercanos(latitud, longitud, datos_productores, radio_km=radio_busqueda)
    
    # Mostrar resultados
    st.header("Resultados de la búsqueda")
    st.write(f"**Coordenadas consultadas:** Lat {latitud:.6f}, Lng {longitud:.6f}")
    
    if productores_cercanos:
        st.success(f"Se encontraron {len(productores_cercanos)} productores en un radio de {radio_busqueda} km")
        
        # Productor más cercano
        mas_cercano = productores_cercanos[0]
        
        st.subheader("Productor más cercano:")
        st.markdown(f"""
        **CUIT:** {mas_cercano['cuit']}  
        **Razón Social:** {mas_cercano['titular']}  
        **Distancia:** {mas_cercano['distancia']} km  
        **Localidad:** {mas_cercano.get('localidad', 'No disponible')}  
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
                "Localidad": productor.get('localidad', '')
            })
        
        # Mostrar tabla
        st.dataframe(pd.DataFrame(tabla_data), use_container_width=True)
        
        # Mostrar detalles expandibles
        for i, productor in enumerate(productores_cercanos[:10]):  # Limitar a los 10 más cercanos
            with st.expander(f"{i+1}. {productor['titular']} ({productor['distancia']} km)"):
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
