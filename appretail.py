# app.py

import streamlit as st
st.set_page_config(page_title="Demo Aseguradora Inteligente con LLM", layout="wide")

import pandas as pd
import requests
import pymysql
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import re # For regular expressions

# ----------------------------------------
# 1. CONFIGURACION DE CONEXION A LA BASE DE DATOS
# ----------------------------------------
DB_USER = 'root'
DB_PASS = 'root' # IMPORTANT: Use environment variables or Streamlit secrets for production
DB_HOST = 'localhost'
DB_PORT = '3306'
DB_NAME = 'demo_aseguradora'

engine = create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# ----------------------------------------
# 2. CARGAR LAS TRES TABLAS
# ----------------------------------------
@st.cache_data
def cargar_datos():
    try:
        df_empleados = pd.read_sql("SELECT * FROM empresas_empleados", con=engine)
        df_productos = pd.read_sql("SELECT * FROM productos_ofrecibles", con=engine)
        df_recomendaciones = pd.read_sql("SELECT * FROM recomendaciones_empresa_producto", con=engine)
        return df_empleados, df_productos, df_recomendaciones
    except Exception as e:
        st.error(f"Error al cargar datos desde la base de datos: {e}")
        # Return empty DataFrames on error to prevent downstream issues
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_empleados, df_productos, df_recomendaciones = cargar_datos()

# ----------------------------------------
# 3. FUNCION DE RESUMENES ESPECIFICOS (Your existing function)
# ----------------------------------------
def construir_resumen_dinamico():
    resumen = []
    if df_empleados.empty:
        return "No hay datos de empleados para generar resúmenes."

    # 1. Salario y edad promedio por empresa
    resumen_empresas = (
        df_empleados.groupby("nombre_empresa")
        .agg(salario_promedio=('salario_estimado', 'mean'), edad_promedio=('edad', 'mean'))
        .round(0)
        .reset_index()
    )
    resumen.append("\nSalario y edad promedio por empresa:")
    for _, row in resumen_empresas.iterrows():
        resumen.append(f"- {row.nombre_empresa}: salario promedio ${row.salario_promedio:,.0f}, edad promedio {row.edad_promedio:.0f} años") # Formatted numbers

    # 2. Empresas con empleados casados y mayores de 40
    if not df_empleados.empty:
        filtro_casados = df_empleados[(df_empleados.estado_civil == 'casado') & (df_empleados.edad > 40)]
        if not filtro_casados.empty:
            empresas_casados_40 = filtro_casados['nombre_empresa'].value_counts().index.tolist()
            resumen.append("\nEmpresas con empleados casados y mayores de 40 años (ejemplos):")
            resumen.extend([f"- {e}" for e in empresas_casados_40[:5]]) # Limit for brevity
        else:
            resumen.append("\nNo se encontraron empresas con un número significativo de empleados casados y mayores de 40 años.")
    else:
        resumen.append("\nNo hay datos de empleados para analizar estado civil y edad por empresa.")


    # 3. Cargos más comunes entre nivel medio-alto
    if not df_empleados.empty:
        empleados_medio_alto = df_empleados[df_empleados.nivel_socioeconomico == 'medio-alto']
        if not empleados_medio_alto.empty:
            cargos_comunes = (
                empleados_medio_alto['cargo']
                .value_counts()
                .head(5)
                .to_dict()
            )
            resumen.append("\nCargos más comunes entre empleados de nivel socioeconómico medio-alto:")
            for cargo, count in cargos_comunes.items():
                resumen.append(f"- {cargo}: {count} empleados")
        else:
            resumen.append("\nNo se encontraron empleados de nivel socioeconómico medio-alto.")
    else:
        resumen.append("\nNo hay datos de empleados para analizar cargos comunes por nivel socioeconómico.")


    # 4. Provincias con salario promedio > $2500
    if not df_empleados.empty:
        salario_provincia = (
            df_empleados.groupby("provincia")['salario_estimado'].mean().reset_index()
        )
        provincias_altos = salario_provincia[salario_provincia.salario_estimado > 2500]['provincia'].tolist()
        if provincias_altos:
            resumen.append("\nProvincias con salario promedio mayor a $2500:")
            resumen.extend([f"- {p}" for p in provincias_altos])
        else:
            resumen.append("\nNinguna provincia tiene un salario promedio mayor a $2500 según los datos.")
    else:
        resumen.append("\nNo hay datos de empleados para analizar salarios por provincia.")

    # 5. Empresa con mayor diversidad de cargos
    if not df_empleados.empty and 'nombre_empresa' in df_empleados.columns and 'cargo' in df_empleados.columns:
        diversidad = df_empleados.groupby("nombre_empresa")['cargo'].nunique().sort_values(ascending=False)
        if not diversidad.empty:
            top_empresa = diversidad.idxmax()
            resumen.append(f"\nEmpresa con mayor diversidad de cargos: {top_empresa} ({diversidad.max()} cargos únicos)")
        else:
            resumen.append("\nNo se pudo determinar la empresa con mayor diversidad de cargos.")
    else:
        resumen.append("\nDatos insuficientes o faltan columnas para determinar diversidad de cargos.")

    return "\n".join(resumen)

# ----------------------------------------
# 4. FUNCION PARA GENERAR CONTEXTO CON DATOS REALES
# ----------------------------------------
def generar_contexto():
    # Added column details to the prompt
    contexto = """
Tienes acceso a las siguientes tablas ya cargadas en memoria:

TABLA 1: empresas_empleados (con columnas: empresa_id, nombre_empresa, sede_id, provincia_sede, ciudad_sede, empleado_id, nombre_empleado, cargo, provincia, ciudad, edad, nivel_socioeconomico, estado_civil, salario_estimado)
TABLA 2: productos_ofrecibles (con columnas: producto_id, nombre_producto, tipo_producto, descripcion, edad_min, edad_max, salario_min, nivel_socioeconomico_objetivo, estado_civil_objetivo, cobertura_usd, duracion_meses, frecuencia_pago, destacado)
TABLA 3: recomendaciones_empresa_producto (con columnas: empresa_id, nombre_empresa, producto, tipo_producto, puntaje_afinidad, destacado, descripcion)

TAREAS QUE PUEDES HACER:
- Responder consultas específicas sobre empleados, productos o recomendaciones.
- Generar insights por empresa o por producto.
- Comparar empresas entre sí o analizar tendencias.
- Detectar brechas (por ejemplo, empresas sin ningún producto recomendado).
- Responder en lenguaje natural, con claridad y justificación.
- Ser útil, concreto y confiable.

IMPORTANTE:
No generes código SQL. No inventes datos. Responde solo con base en el contexto proporcionado.
**Si presentas una lista de elementos con valores numéricos (ej. una distribución, conteos, promedios por categoría), por favor usa un formato claro como '- NombreDeCategoria: ValorNumérico' o 'NombreDeCategoria: ValorNumérico' en cada línea, ya que esto podría usarse para generar un gráfico.**

A continuación, se incluye un resumen real basado en los datos actuales:
"""
    contexto += "\n" + construir_resumen_dinamico()
    return contexto

# ----------------------------------------
# 5. FUNCION PARA CONSULTAR A OLLAMA
# ----------------------------------------
def consultar_ollama(pregunta, modelo="llama3"):
    contexto_completo = generar_contexto()
    prompt = f"{contexto_completo}\n\nPREGUNTA DEL USUARIO: {pregunta}\n\nRESPUESTA:".strip()
    payload = {
        "model": modelo,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    try:
        # Increased timeout as LLM generation can be slow
        response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=120)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        return data.get("message", {}).get("content", "⚠️ No se encontró contenido en la respuesta.")
    except requests.exceptions.Timeout:
        return "❌ Error: La solicitud a Ollama tardó demasiado tiempo en responder (timeout)."
    except requests.exceptions.RequestException as e:
        return f"❌ Error al conectar con Ollama o en la solicitud: {str(e)}"
    except Exception as e: # Catch any other unexpected errors
        return f"❌ Error inesperado al procesar la respuesta de Ollama: {str(e)}"

# ----------------------------------------
# 6. FUNCION PARA CREAR GRAFICOS (MATPLOTLIB) - User Provided
# ----------------------------------------
def crear_grafico_matplotlib(categorias, valores, etiqueta_categoria, etiqueta_valor, titulo_grafico="Gráfico de Barras"):
    if not categorias or not valores:
        return None
    if len(categorias) != len(valores):
        return None

    try:
        MAX_CAT_LABEL_LENGTH = 18
        categorias_display = []
        for cat in categorias:
            cat_str = str(cat)
            if len(cat_str) > MAX_CAT_LABEL_LENGTH:
                categorias_display.append(cat_str[:MAX_CAT_LABEL_LENGTH-3] + "...")
            else:
                categorias_display.append(cat_str)
        
        valores_numeric = []
        for v in valores:
            try:
                cleaned_v = str(v).replace('$', '').replace('€', '').replace(',', '') 
                valores_numeric.append(float(cleaned_v))
            except ValueError:
                return None
        
        if not valores_numeric:
            return None

        num_categorias = len(categorias_display)
        
        # --- AJUSTE DE TAMAÑO DEL GRÁFICO Y DPI ---
        # El ancho en pulgadas puede variar un poco con el número de categorías
        # Un gráfico muy estrecho no es legible. Mínimo de ~3.5-4 pulgadas.
        ancho_pulgadas = max(3.5, num_categorias * 0.45) 
        # Limitar el ancho máximo para que no se vuelva demasiado grande incluso con muchas categorías
        ancho_pulgadas = min(ancho_pulgadas, 7) # Por ejemplo, máximo 7 pulgadas de ancho

        alto_pulgadas = 2.8  # Altura fija en pulgadas, más pequeña
        DPI_GRAFICO = 75  # DPI más bajo para una imagen más pequeña en píxeles
        # --- FIN AJUSTE DE TAMAÑO Y DPI ---
        
        # Aplicar figsize y dpi al crear la figura
        fig, ax = plt.subplots(figsize=(ancho_pulgadas, alto_pulgadas), dpi=DPI_GRAFICO)
        
        bars = ax.bar(categorias_display, valores_numeric, color='mediumseagreen')

        ax.set_title(titulo_grafico, fontsize=8, pad=8) 
        ax.set_xlabel(etiqueta_categoria, fontsize=7) 
        ax.set_ylabel(etiqueta_valor, fontsize=7)   
        
        rotation_angle = 0
        horizontal_alignment = 'center'
        if num_categorias > 3 and ancho_pulgadas < num_categorias * 0.9:
            rotation_angle = 30
            horizontal_alignment = 'right'
        if num_categorias > 5 and ancho_pulgadas < num_categorias * 0.7:
            rotation_angle = 45
        if num_categorias > 8 and ancho_pulgadas < num_categorias * 0.5: # Si está muy apretado
            rotation_angle = 60
        
        plt.xticks(rotation=rotation_angle, ha=horizontal_alignment, fontsize=6) 
        plt.yticks(fontsize=6) 

        if valores_numeric:
            max_val = max(valores_numeric) if valores_numeric else 0
            ax.set_ylim(0, (max_val * 1.25) if max_val > 0 else 1) 

            for bar_item in bars:
                yval = bar_item.get_height()
                label_text = f'{yval:,.2f}' if isinstance(yval, float) and not yval.is_integer() else f'{yval:,.0f}'
                ax.text(bar_item.get_x() + bar_item.get_width()/2.0, 
                        yval + (max_val * 0.02 if max_val > 0 else 0.02), 
                        label_text, 
                        ha='center', va='bottom', fontsize=5) 
        
        plt.tight_layout(pad=0.4) # Padding ajustado
        return fig
    except Exception as e:
        st.error(f"Error interno al crear gráfico Matplotlib: {e}")
        return None

# ... (el resto de tu código como construir_resumen_dinamico, generar_contexto, consultar_ollama, intentar_extraer_datos_graficables, y la UI de Streamlit) ...
# Asegúrate de que esta función `crear_grafico_matplotlib` reemplaza la existente en tu archivo app.py

# ----------------------------------------
# 7. NEW: FUNCION PARA EXTRAER DATOS DE LA RESPUESTA DEL LLM PARA GRAFICAR
# ----------------------------------------
def intentar_extraer_datos_graficables(texto_respuesta):
    """
    Intenta extraer categorías y valores de un texto formateado para un gráfico de barras.
    Busca patrones como:
    - Categoria: [descripcion opcional] ValorNumerico
    - Categoria - [descripcion opcional] ValorNumerico
    - * Categoria: [descripcion opcional] ValorNumerico
    Devuelve (categorias, valores, etiqueta_categoria_sugerida, etiqueta_valor_sugerida) o Nones.
    """
    categorias = []
    valores = []
    
    # Regex ajustado:
    # ^\s*(?:[-*]\s*)?       : Opcional inicio de línea con viñeta (- o *) y espacios.
    # ([^:]+?)                : Grupo 1 (Categoría): Uno o más caracteres hasta el primer ':' (no codicioso).
    # \s*:\s* : Separador (dos puntos) rodeado de espacios opcionales.
    # (?:.*?)                 : Grupo no capturador para cualquier texto intermedio (como "salario promedio ") (no codicioso).
    # ([\$€]?\s*[\d\.\,]+(?:\s*[a-zA-Z%ºª\$€]*)?) : Grupo 2 (Valor String):
    #     [\$€]?                : Símbolo de moneda opcional.
    #     \s* : Espacios opcionales.
    #     [\d\.\,]+             : Uno o más dígitos, puntos o comas.
    #     (?:\s*[a-zA-Z%ºª\$€]*)? : Opcionalmente seguido de espacios y unidades/símbolos comunes.
    # \s*$                     : Fin de línea con espacios opcionales.
    pattern = re.compile(r"^\s*(?:[-*]\s*)?([^:]+?)\s*:\s*(?:.*?)([\$€]?\s*[\d\.\,]+(?:\s*[a-zA-Z%ºª\$€]*)?)\s*$", re.MULTILINE)

    def extract_numeric_value(value_str):
        # Quitar símbolos comunes y texto no numérico al final.
        cleaned_value_str = value_str.replace('$', '').replace('€', '').replace('%', '').replace('USD', '').strip()
        # Eliminar separadores de miles (coma no seguida de exactamente 3 dígitos o no al final)
        # Esta heurística es para formatos como "1,234.56" o "1234"
        cleaned_value_str = re.sub(r'(?<=\d),(?=\d{3}(?!\d))', '', cleaned_value_str) # Para comas como separador de miles
        
        # Intentar hacer coincidir la primera parte numérica válida (maneja "1.234" o "1234.56")
        # También puede manejar si la coma es decimal si no fue eliminada como separador de miles.
        # Por ahora, asumimos que el punto es el separador decimal si está presente después de la limpieza de comas.
        numeric_match = re.match(r"[\d\.]+", cleaned_value_str) # Busca dígitos y puntos.
        if numeric_match:
            try:
                return float(numeric_match.group(0))
            except ValueError:
                return None
        return None

    for match in pattern.finditer(texto_respuesta):
        categoria = match.group(1).strip()
        valor_str_completo = match.group(2).strip()
        
        valor_numeric = extract_numeric_value(valor_str_completo)

        if valor_numeric is not None:
            if len(categoria) > 70: # Heurística para evitar categorías demasiado largas
                continue
            if not categoria: # Evitar categorías vacías
                continue

            categorias.append(categoria)
            valores.append(valor_numeric)
        # else:
            # Descomentar para depuración si es necesario:
            # st.write(f"Debug (intentar_extraer): No se pudo extraer valor numérico de '{valor_str_completo}' para categoría '{categoria}'")


    if categorias and valores and len(categorias) == len(valores) and len(categorias) > 1 : # Requiere al menos 2 puntos de datos
        etiqueta_categoria = "Categoría"
        etiqueta_valor = "Valor"
        return categorias, valores, etiqueta_categoria, etiqueta_valor
    else:
        # Descomentar para depuración si es necesario:
        # st.write(f"Debug (intentar_extraer): No se extrajeron suficientes datos o las longitudes no coinciden. Categorías: {len(categorias)}, Valores: {len(valores)}")
        return None, None, None, None


# ----------------------------------------
# 8. UI STREAMLIT
# ----------------------------------------
st.title("🧠 Asistente Asegurador")

st.markdown("""
Este asistente puede responder preguntas sobre:
- 👥 Empleados y empresas
- 📦 Productos disponibles
- ✅ Recomendaciones generadas
""")

# Initialize session state variables
if 'respuesta_ollama' not in st.session_state:
    st.session_state.respuesta_ollama = ""
if 'pregunta_actual' not in st.session_state:
    st.session_state.pregunta_actual = ""
if 'chart_fig' not in st.session_state: # To store the generated figure object
    st.session_state.chart_fig = None
if 'chart_attempted' not in st.session_state: # To know if we tried to make a chart
    st.session_state.chart_attempted = False


pregunta_usuario = st.text_area("Escribe tu pregunta:", value=st.session_state.pregunta_actual, height=100, key="pregunta_usuario_ta")

if st.button("💬 Consultar al Asistente", key="consultar_btn"):
    if pregunta_usuario.strip() == "":
        st.warning("Por favor, escribe una pregunta antes de consultar.")
        st.session_state.respuesta_ollama = ""
        st.session_state.pregunta_actual = ""
        st.session_state.chart_fig = None
        st.session_state.chart_attempted = False
    else:
        st.session_state.pregunta_actual = pregunta_usuario
        st.session_state.respuesta_ollama = "" # Clear previous
        st.session_state.chart_fig = None      # Clear previous
        st.session_state.chart_attempted = True # Mark that we will attempt

        with st.spinner("Consultando a Ollama y procesando respuesta..."):
            respuesta_texto = consultar_ollama(pregunta_usuario)
            st.session_state.respuesta_ollama = respuesta_texto

            if "❌ Error" not in respuesta_texto:
                # Intentar extraer datos y generar el gráfico
                cats, vals, et_cat, et_val = intentar_extraer_datos_graficables(respuesta_texto)
                if cats and vals:
                    # Generar un título para el gráfico basado en la pregunta
                    titulo_grafico = f"Gráfico"
                    # titulo_grafico = f"Visualización para: '{pregunta_usuario[:60]}...'" if pregunta_usuario else "Gráfico de Barras"
                    fig = crear_grafico_matplotlib(cats, vals, et_cat, et_val, titulo_grafico=titulo_grafico)
                    st.session_state.chart_fig = fig
                # else:
                    # st.session_state.chart_fig = None # Already done above
            # else: Error message will be shown in the response tab

# --- Tabs for Response and Chart ---
tab_respuesta, tab_visualizacion = st.tabs(["📝 Respuesta del Asistente", "📊 Visualización Dinámica"])

with tab_respuesta:
    if st.session_state.respuesta_ollama:
        if "❌ Error" in st.session_state.respuesta_ollama:
            st.error(st.session_state.respuesta_ollama)
        else:
            st.success("Respuesta recibida:")
            st.markdown(st.session_state.respuesta_ollama)
    elif st.session_state.pregunta_actual : # If a question was asked but no response yet
        st.info("Esperando respuesta del asistente...")
    else:
        st.info("Realice una consulta para ver la respuesta aquí.")

with tab_visualizacion:
    # st.subheader("Gráfico Generado desde la Respuesta (Intento)")

    # Usar columnas para centrar el gráfico y limitar su expansión horizontal
    # Esto crea tres columnas: una de espacio, una para el gráfico, y otra de espacio.
    # Ajusta los ratios [0.1, 0.8, 0.1] según cuánto quieras centrar/encoger el área del gráfico.
    # Por ejemplo, [0.25, 0.5, 0.25] haría el área del gráfico aún más estrecha (50% del espacio disponible en la pestaña).
    # Si quieres que el gráfico use un ancho máximo fijo más pequeño, podrías necesitar CSS o trucos más avanzados.
    
    col_izq_espacio, col_grafico, col_der_espacio = st.columns([0.15, 0.7, 0.15]) # 70% del ancho para el gráfico, centrado

    with col_grafico: # El gráfico se dibujará en esta columna central
        if st.session_state.chart_fig:
            # IMPORTANTE: use_container_width=False para que el tamaño del gráfico
            # sea determinado por figsize y dpi de Matplotlib, no por el ancho de la columna.
            st.pyplot(st.session_state.chart_fig, use_container_width=False)
            st.caption("Gráfico generado automáticamente a partir de los datos detectados en la respuesta del asistente.")
        elif st.session_state.chart_attempted and "❌ Error" not in st.session_state.respuesta_ollama:
            st.info("No se pudieron extraer datos adecuados de la respuesta del asistente para generar un gráfico, o la respuesta no contenía un formato de lista graficable.")
        elif not st.session_state.chart_attempted and st.session_state.pregunta_actual:
            st.info("Procesando la solicitud...")
        else:
            st.info("Si la respuesta del asistente contiene una lista de categorías y valores, se intentará mostrar un gráfico aquí.")

# ----------------------------------------
# 9. Visualizar tablas de respaldo (Your existing section)
# ----------------------------------------
if not all(df.empty for df in [df_empleados, df_productos, df_recomendaciones]):
    with st.expander("💾 Ver datos tabulares de respaldo (empleados: primeras 300 filas)"):
        if not df_empleados.empty:
            st.subheader("👥 Empleados por Empresa")
            st.dataframe(df_empleados.head(300), use_container_width=True, height=300)
        else:
            st.caption("No hay datos de empleados para mostrar.")

        if not df_productos.empty:
            st.subheader("📦 Productos Ofrecibles")
            st.dataframe(df_productos, use_container_width=True, height=300)
        else:
            st.caption("No hay datos de productos para mostrar.")

        if not df_recomendaciones.empty:
            st.subheader("✅ Recomendaciones por Empresa")
            st.dataframe(df_recomendaciones, use_container_width=True, height=300)
        else:
            st.caption("No hay datos de recomendaciones para mostrar.")
else:
    st.warning("Advertencia: No se pudieron cargar los datos de las tablas. El asistente y los resúmenes podrían no funcionar como se espera.")