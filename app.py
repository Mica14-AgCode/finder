import streamlit as st
import pandas as pd
import math
import json
import base64
import os
from io import StringIO
import numpy as np

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
if 'radio_busqueda' not in st.session_state:
    st.session_state.radio_busqueda = 5.0
if 'modo_debug' not in st.session_state:
    st.session_state.modo_debug = True

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
        if st.session_state.modo_debug:
            st.warning(f"Error al verificar si el punto está en el polígono: {e}")
        return False

def crear_datos_ejemplo():
    """Crea datos de ejemplo cuando no se puede cargar el CSV"""
    st.warning("Usando datos de ejemplo para demostración")
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

# Función para cargar y procesar los datos
@st.cache_data
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

# Función para encontrar el productor cuyo polígono contiene el punto
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
                    'idx': int(idx),
                    'contenedor': True
                }
                break
    
    return productor_contenedor

# Función para encontrar el CUIT más cercano a un punto
def encontrar_cuit_mas_cercano(lat, lon, datos):
    """Encuentra el CUIT más cercano a un punto dado"""
    # Primero verificar si el punto está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        return productor_contenedor
    
    # Si no está dentro de ningún polígono, buscar el más cercano
    distancia_min = float('inf')
    cuit_cercano = None
    
    # Para depuración
    if st.session_state.modo_debug:
        st.write(f"Buscando el CUIT más cercano al punto ({lat}, {lon})")
        st.write(f"Total de registros en datos: {len(datos)}")
    
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
                    'idx': int(idx),
                    'contenedor': False
                }
    
    # Para depuración
    if st.session_state.modo_debug:
        if cuit_cercano:
            st.write(f"CUIT más cercano encontrado: {cuit_cercano['cuit']} a {cuit_cercano['distancia']} km")
        else:
            st.write("No se encontró ningún CUIT cercano")
        
    return cuit_cercano

# Función para encontrar CUITs cercanos a un punto
def encontrar_cuits_cercanos(lat, lon, datos, radio_km=5):
    """
    Encuentra CUITs cercanos a un punto dado dentro de un radio específico.
    """
    cercanos = []
    
    # Primero verificar si está dentro de algún polígono
    productor_contenedor = encontrar_productor_contenedor(lat, lon, datos)
    if productor_contenedor:
        cercanos.append(productor_contenedor)
        if st.session_state.modo_debug:
            st.write(f"El punto está dentro del polígono de: {productor_contenedor['titular']}")
    
    for idx, fila in datos.iterrows():
        if pd.notna(fila['latitud']) and pd.notna(fila['longitud']):
            # Si ya encontramos que este productor contiene el punto, saltarlo
            if productor_contenedor and int(idx) == productor_contenedor['idx']:
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
                    'poligono': fila['poligono'] if 'poligono' in fila else None,
                    'idx': int(idx),
                    'contenedor': False
                })
    
    # Ordenar por distancia
    cercanos = sorted(cercanos, key=lambda x: x['distancia'])
    
    # Para depuración
    if st.session_state.modo_debug:
        st.write(f"Se encontraron {len(cercanos)} CUITs dentro del radio de {radio_km} km")
    
    return cercanos

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

# Agregar un toggle para el modo de depuración en el sidebar
st.sidebar.subheader("Modo depuración")
modo_debug = st.sidebar.checkbox("Activar modo depuración", value=st.session_state.modo_debug)
st.session_state.modo_debug = modo_debug

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

# Radio de búsqueda como un solo campo editable sin límite
st.sidebar.subheader("Radio de búsqueda")
radio_busqueda = st.sidebar.number_input(
    "Radio de búsqueda (km):",
    min_value=0.1,
    value=st.session_state.radio_busqueda,
    step=0.1,
    format="%.1f"
)
st.session_state.radio_busqueda = radio_busqueda

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
    st.sidebar.success(f"Archivo cargado: {archivo_subido.name}")

# Layout principal
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Mapa Interactivo")
    
    # Mostrar un formulario para ingresar coordenadas manualmente
    with st.form("coordenadas_form"):
        st.write("Ingresa coordenadas manualmente:")
        col_lat, col_lon = st.columns(2)
        with col_lat:
            latitud = st.number_input("Latitud:", value=-34.603722, format="%.6f")
        with col_lon:
            longitud = st.number_input("Longitud:", value=-58.381592, format="%.6f")
        
        submitted = st.form_submit_button("Buscar en estas coordenadas")
        if submitted:
            st.session_state.punto_seleccionado = (latitud, longitud)
            st.session_state.busqueda_realizada = True
            
            # Mostrar las coordenadas que se están usando
            st.success(f"Buscando en: Lat {latitud}, Lng {longitud}")
    
    # Mostrar datos básicos del conjunto de datos
    st.markdown("### Vista previa de datos")
    if 'poligono' in datos_filtrados.columns:
        st.info(f"Datos cargados: {len(datos_filtrados)} registros con {datos_filtrados['poligono'].notna().sum()} polígonos")
    else:
        st.info(f"Datos cargados: {len(datos_filtrados)} registros sin polígonos")
    
    # Mostrar una vista previa del dataset
    columnas_mostrar = ['cuit', 'titular', 'latitud', 'longitud']
    columnas_mostrar = [col for col in columnas_mostrar if col in datos_filtrados.columns]
    st.dataframe(datos_filtrados[columnas_mostrar].head(5), use_container_width=True)

# Panel de resultados
with col2:
    st.subheader("Resultados de la búsqueda")
    
    # Mostrar resultados si hay un punto seleccionado
    if st.session_state.busqueda_realizada and st.session_state.punto_seleccionado:
        lat, lon = st.session_state.punto_seleccionado
        
        st.write(f"**Coordenadas del punto:** Lat {lat:.4f}, Lng {lon:.4f}")
        
        # Mostrar un spinner mientras se busca
        with st.spinner("Buscando productores cercanos..."):
            # Buscar el CUIT más cercano
            cuit_mas_cercano = encontrar_cuit_mas_cercano(lat, lon, datos_filtrados)
            
            # Buscar CUITs cercanos
            cuits_cercanos = encontrar_cuits_cercanos(lat, lon, datos_filtrados, radio_km=radio_busqueda)
        
        if cuit_mas_cercano:
            if cuit_mas_cercano.get('contenedor', False):
                st.success("**Productor que contiene este punto:**")
            else:
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
                    "Km": cercano['distancia'],
                    "Contenedor": "Sí" if cercano.get('contenedor', False) else "No"
                })
            
            st.dataframe(pd.DataFrame(tabla_datos), use_container_width=True)
            
            # Detalles expandibles
            for i, cercano in enumerate(cuits_cercanos[:10]):  # Mostrar los 10 más cercanos
                titulo = f"{i+1}. {cercano['titular']} ({cercano['distancia']} km)"
                if cercano.get('contenedor', False):
                    titulo += " - Contiene el punto"
                    
                with st.expander(titulo):
                    st.markdown(f"""
                    **CUIT:** {cercano['cuit']}  
                    **Razón Social:** {cercano['titular']}  
                    **RENSPA:** {cercano.get('renspa', 'No disponible')}  
                    **Localidad:** {cercano.get('localidad', 'No disponible')}  
                    **Superficie:** {cercano.get('superficie', 'No disponible')} ha  
                    **Distancia:** {cercano['distancia']} km  
                    **Coordenadas:** Lat {cercano['latitud']:.4f}, Lng {cercano['longitud']:.4f}
                    """)
                    
                    if cercano.get('poligono') is not None:
                        st.markdown(f"**Polígono disponible:** Sí")
                        if st.session_state.modo_debug:
                            st.code(cercano['poligono'][:100] + "..." if len(cercano['poligono']) > 100 else cercano['poligono'])
        else:
            st.warning(f"No se encontraron productores en un radio de {radio_busqueda} km")
    else:
        st.info("Ingresa coordenadas y haz clic en 'Buscar' para ver resultados.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Entrada de coordenadas**: Ingresa las coordenadas del punto que deseas consultar y haz clic en "Buscar".
2. **Filtros**: Usa los filtros en el panel lateral para mostrar productores específicos.
3. **Radio**: Ajusta el radio de búsqueda para encontrar productores a mayor o menor distancia.
4. **Resultados**: El sistema mostrará los productores cercanos a la ubicación seleccionada.
5. **Modo depuración**: Activa este modo para ver información adicional útil para diagnóstico.
""")

# Información sobre la verificación de polígonos
st.markdown("### Verificación de polígonos")
st.markdown("""
- Si un punto está dentro de un polígono, se mostrará ese productor como "Contiene el punto".
- Para que esto funcione, necesitas que la columna 'poligono' en tu CSV contenga los datos en formato WKT.
- Ejemplo de formato WKT de polígono: `POLYGON((-60.0 -34.0, -60.1 -34.0, -60.1 -34.1, -60.0 -34.1, -60.0 -34.0))`
""")

# Mostrar información de depuración si está activado
if st.session_state.modo_debug:
    st.markdown("---")
    with st.expander("Información de depuración"):
        st.write("**Estado de la aplicación:**")
        st.json({
            "punto_seleccionado": st.session_state.punto_seleccionado,
            "busqueda_realizada": st.session_state.busqueda_realizada,
            "radio_busqueda": st.session_state.radio_busqueda,
            "archivo_cargado": st.session_state.archivo_cargado["nombre"] if st.session_state.archivo_cargado else None,
            "modo_debug": st.session_state.modo_debug
        })
        
        if 'poligono' in datos_filtrados.columns:
            st.write("**Estadísticas de polígonos:**")
            st.write(f"- Total de registros: {len(datos_filtrados)}")
            st.write(f"- Registros con polígono: {datos_filtrados['poligono'].notna().sum()}")
            st.write(f"- Registros sin polígono: {datos_filtrados['poligono'].isna().sum()}")
            
            if datos_filtrados['poligono'].notna().any():
                primer_poligono = datos_filtrados.loc[datos_filtrados['poligono'].notna(), 'poligono'].iloc[0]
                st.write("**Ejemplo de polígono WKT:**")
                st.code(primer_poligono)
