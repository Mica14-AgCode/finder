import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as mplPolygon
from io import StringIO
import re
import math
import base64
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Visor de Productores Agrícolas", layout="wide")

# Título de la aplicación
st.title("Visor de Productores Agrícolas")

# Ruta al archivo CSV
RUTA_CSV = "datos_productores.csv"

# Clases básicas para manejar geometrías sin shapely
class Punto:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def distancia(self, otro_punto):
        """Calcular la distancia euclidiana entre dos puntos"""
        return math.sqrt((self.x - otro_punto.x) ** 2 + (self.y - otro_punto.y) ** 2)
    
    def distancia_km(self, otro_punto):
        """Distancia aproximada en kilómetros usando la fórmula de Haversine"""
        # Radio de la Tierra en km
        R = 6371.0
        
        # Convertir coordenadas a radianes
        lat1 = math.radians(self.y)
        lon1 = math.radians(self.x)
        lat2 = math.radians(otro_punto.y)
        lon2 = math.radians(otro_punto.x)
        
        # Diferencias de latitud y longitud
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        # Fórmula de Haversine
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distancia = R * c
        
        return distancia

class Poligono:
    def __init__(self, puntos):
        self.puntos = puntos
    
    def contiene_punto(self, punto):
        """Verifica si un punto está dentro del polígono usando ray casting"""
        x, y = punto.x, punto.y
        n = len(self.puntos)
        dentro = False
        
        p1x, p1y = self.puntos[0].x, self.puntos[0].y
        for i in range(n + 1):
            p2x, p2y = self.puntos[i % n].x, self.puntos[i % n].y
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            dentro = not dentro
            p1x, p1y = p2x, p2y
        
        return dentro
    
    def centroide(self):
        """Calcular el centroide del polígono"""
        x_sum = sum(p.x for p in self.puntos)
        y_sum = sum(p.y for p in self.puntos)
        return Punto(x_sum / len(self.puntos), y_sum / len(self.puntos))

def parse_poligono(poligono_wkt):
    """Parsea un polígono en formato WKT a nuestra estructura"""
    if not poligono_wkt or not isinstance(poligono_wkt, str):
        return None

    try:
        # Extraer las coordenadas del polígono WKT
        coords_str = re.search(r'POLYGON\s*\(\((.*?)\)\)', poligono_wkt)
        if not coords_str:
            return None
        
        # Convertir las coordenadas en puntos
        coords = coords_str.group(1).split(',')
        puntos = []
        for coord in coords:
            x, y = map(float, coord.strip().split())
            puntos.append(Punto(x, y))
        
        return Poligono(puntos)
    except Exception as e:
        st.warning(f"Error al parsear polígono: {e}")
        return None

# Función para cargar y procesar los datos
@st.cache_data
def cargar_datos(ruta_archivo=RUTA_CSV):
    """Carga los datos de productores desde un archivo CSV"""
    try:
        # Cargar el CSV
        df = pd.read_csv(ruta_archivo)
        
        # Procesar las geometrías
        if 'poligono' in df.columns:
            # Convertir los polígonos WKT a nuestra estructura
            df['geom'] = df['poligono'].apply(parse_poligono)
            
            # Filtrar filas sin geometría válida
            df = df[df['geom'].notna()]
            
            # Agregar centroides
            df['centroide'] = df['geom'].apply(lambda p: p.centroide() if p else None)
        else:
            # Si no hay polígonos, usar puntos de latitud/longitud
            df['centroide'] = df.apply(
                lambda row: Punto(row['longitud'], row['latitud']) 
                if pd.notna(row['longitud']) and pd.notna(row['latitud']) else None, 
                axis=1
            )
            df = df[df['centroide'].notna()]
        
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

# Generar un mapa estático usando matplotlib
def generar_mapa(datos, punto_seleccionado=None, radio_km=5):
    """Genera un mapa estático con matplotlib"""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Dibujar los polígonos
    for _, fila in datos.iterrows():
        if 'geom' in fila and fila['geom'] is not None:
            # Convertir puntos del polígono al formato que espera matplotlib
            poligono = fila['geom']
            puntos = [(p.x, p.y) for p in poligono.puntos]
            
            # Dibujar el polígono
            poly = mplPolygon(puntos, closed=True, fill=True, alpha=0.3, edgecolor='blue', facecolor='lightblue')
            ax.add_patch(poly)
            
            # Dibujar el centroide
            if fila['centroide']:
                ax.plot(fila['centroide'].x, fila['centroide'].y, 'bo', markersize=3)
        elif fila['centroide']:
            # Si no hay polígono, solo dibujar el punto
            ax.plot(fila['centroide'].x, fila['centroide'].y, 'bo', markersize=5)
    
    # Dibujar el punto seleccionado y el radio
    if punto_seleccionado:
        lat, lon = punto_seleccionado
        ax.plot(lon, lat, 'ro', markersize=8)
        
        # Dibujar círculo de radio
        # Aproximación simple: en estas latitudes, 1 grado ~ 111 km
        radio_grados = radio_km / 111
        circle = plt.Circle((lon, lat), radio_grados, fill=False, color='red', linestyle='--')
        ax.add_patch(circle)
    
    # Configurar los ejes
    if not datos.empty:
        # Calcular los límites del mapa basados en los datos
        if 'geom' in datos.columns and datos['geom'].notna().any():
            # Usar los límites de los polígonos
            all_x = []
            all_y = []
            for geom in datos['geom'].dropna():
                if geom:
                    for p in geom.puntos:
                        all_x.append(p.x)
                        all_y.append(p.y)
            
            if all_x and all_y:
                min_x, max_x = min(all_x), max(all_x)
                min_y, max_y = min(all_y), max(all_y)
                
                # Agregar un margen
                margin_x = (max_x - min_x) * 0.1
                margin_y = (max_y - min_y) * 0.1
                
                ax.set_xlim(min_x - margin_x, max_x + margin_x)
                ax.set_ylim(min_y - margin_y, max_y + margin_y)
        else:
            # Usar los centroides
            centroides = datos['centroide'].dropna()
            if len(centroides) > 0:
                all_x = [c.x for c in centroides if c]
                all_y = [c.y for c in centroides if c]
                
                if all_x and all_y:
                    min_x, max_x = min(all_x), max(all_x)
                    min_y, max_y = min(all_y), max(all_y)
                    
                    # Agregar un margen
                    margin_x = (max_x - min_x) * 0.1
                    margin_y = (max_y - min_y) * 0.1
                    
                    ax.set_xlim(min_x - margin_x, max_x + margin_x)
                    ax.set_ylim(min_y - margin_y, max_y + margin_y)
    
    ax.set_xlabel('Longitud')
    ax.set_ylabel('Latitud')
    ax.set_title('Mapa de Productores Agrícolas')
    ax.grid(True)
    
    # Convertir la figura a una imagen para mostrar en Streamlit
    return fig

# Función para encontrar el CUIT en un punto y los CUITs cercanos
def encontrar_cuits(lat, lon, datos, radio_km=5):
    """
    Encuentra el CUIT asociado a un punto y los CUITs cercanos.
    """
    punto = Punto(lon, lat)
    
    # Verificar si el punto está dentro de algún polígono
    dentro = None
    for idx, fila in datos.iterrows():
        if 'geom' in fila and fila['geom'] is not None and fila['geom'].contiene_punto(punto):
            dentro = {
                'cuit': fila['cuit'],
                'titular': fila['titular'] if 'titular' in fila else 'No disponible',
                'renspa': fila['renspa'] if 'renspa' in fila else 'No disponible',
                'superficie': fila['superficie'] if 'superficie' in fila else 'No disponible',
                'localidad': fila['localidad'] if 'localidad' in fila else 'No disponible',
                'tipo': 'Exacto'
            }
            break
    
    # Encontrar CUITs cercanos basados en la distancia
    cercanos = []
    for idx, fila in datos.iterrows():
        if fila['centroide']:
            distancia = punto.distancia_km(fila['centroide'])
            
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

# Mostrar mensaje de instrucciones
with st.sidebar:
    st.info(f"""
    **Instrucciones de configuración:**
    
    El archivo CSV con los datos de productores debe:
    1. Llamarse '{RUTA_CSV}'
    2. Estar en la misma carpeta que esta aplicación
    3. Contener las columnas necesarias: 'cuit', 'titular', etc.
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

# Contenedor para mostrar el mapa y resultados
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Mapa de Productores")
    
    # Campos para ingresar coordenadas manualmente
    st.subheader("Ingresar coordenadas")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        latitud = st.number_input("Latitud", value=-34.603722, format="%.6f", step=0.000001)
    with col_lon:
        longitud = st.number_input("Longitud", value=-58.381592, format="%.6f", step=0.000001)
    
    if st.button("Buscar en estas coordenadas"):
        st.session_state.punto_seleccionado = (latitud, longitud)
        st.session_state.busqueda_realizada = True
    
    # Generar y mostrar el mapa
    punto_seleccionado = st.session_state.get('punto_seleccionado')
    fig = generar_mapa(datos_filtrados, punto_seleccionado, radio_busqueda)
    st.pyplot(fig)
    
    # Disclaimer
    st.info("""
    **Nota:** Este mapa es estático y no permite interacción directa. 
    Para consultar un punto, ingresa las coordenadas manualmente y haz clic en "Buscar".
    """)

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
                with st.expander(f"{i+1}. CUIT: {cercano['cuit']} ({cercano['distancia']} km)"):
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
        st.info("Selecciona un punto ingresando coordenadas y haciendo clic en 'Buscar'.")

# Instrucciones de uso
st.markdown("---")
st.subheader("Instrucciones de uso")
st.markdown("""
1. **Filtrado**: Usa los filtros en el panel lateral para mostrar productores específicos.
2. **Coordenadas**: Ingresa las coordenadas del punto que deseas consultar.
3. **Buscar**: Haz clic en el botón "Buscar" para ver si el punto pertenece a un campo registrado.
4. **Resultados**: El sistema mostrará si el punto seleccionado pertenece a un campo registrado y qué productores están cercanos.
""")

# Inicializar variables de estado si no existen
if 'punto_seleccionado' not in st.session_state:
    st.session_state.punto_seleccionado = None
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False
