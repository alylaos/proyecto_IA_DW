import streamlit as st
import requests
from sqlalchemy import create_engine
import pandas as pd
import json
import matplotlib.pyplot as plt
import matplotlib
from io import BytesIO # Necesario para la exportación a Excel

# === Configuración de conexión a la base de datos ===
username = 'root'
password = 'root'  # Reemplaza con tu contraseña real
host = 'localhost'
port = 3306
db_name = 'dbseguro' # Asegúrate que este sea el nombre correcto de tu BD

try:
    engine = create_engine(f"mysql+pymysql://{username}:{password}@{host}:{port}/{db_name}")
except Exception as e:
    st.error(f"Error al crear el engine de SQLAlchemy: {e}")
    st.stop()

# === Conversión de pregunta a SQL ===
def pregunta_a_sql(pregunta):
    # Prompt actualizado para reflejar el nuevo esquema de la base de datos
    prompt = (
        "Tienes las siguientes tablas en la base de datos MySQL llamada dbseguro:\n"
        "• afiliados(id_afiliado, nombre, documento, fecha_nacimiento, genero, actividad_economica, provincia, ciudad, codigo_postal, antiguedad_meses, fecha_afiliacion)\n"
        "• productos(id_producto, nombre, tipo_seguro, riesgos_cubiertos, deducible, condiciones_generales)\n"
        "• polizas(id_poliza, id_afiliado, id_producto, fecha_inicio, fecha_fin, estado, monto_asegurado, prima, tipo_riesgo, vigencia_meses)\n"
        "• siniestros(id_siniestro, id_poliza, id_afiliado, fecha_siniestro, fecha_denuncia, tipo_siniestro, estado_siniestro, provincia, ciudad, causa, descripcion, gravedad)\n"
        "• pagos_siniestros(id_pago, id_siniestro, fecha_pago, monto_pagado, estado_pago, tipo_pago, moneda, cuenta_destino)\n"
        "• evaluaciones_siniestro(id_evaluacion, id_siniestro, id_perito, fecha_evaluacion, monto_estimado, monto_rechazado, motivo_rechazo, puntaje_fraude, comentarios)\n"
        "\n"
        "Detalles importantes sobre los valores en las columnas y relaciones:\n"
        "- La tabla 'afiliados' contiene información de los clientes.\n"
        "- La tabla 'productos' describe los seguros ofrecidos.\n"
        "- La tabla 'polizas' vincula a un 'afiliado' (mediante 'id_afiliado') con un 'producto' (mediante 'id_producto') y detalla la cobertura.\n"
        "  - 'polizas.estado' puede ser: 'Activa', 'Cancelada', 'Vencida'.\n"
        "  - 'polizas.tipo_riesgo' puede ser: 'Alto', 'Medio', 'Bajo'.\n"
        "- La tabla 'siniestros' registra los incidentes reportados bajo una 'poliza' (mediante 'id_poliza') por un 'afiliado' (mediante 'id_afiliado').\n"
        "  - 'siniestros.estado_siniestro' puede ser: 'Pendiente', 'Pagado', 'Rechazado'.\n"
        "  - 'siniestros.gravedad' puede ser: 'Leve', 'Moderada', 'Grave'.\n"
        "- La tabla 'pagos_siniestros' detalla los pagos realizados por un 'siniestro' (mediante 'id_siniestro').\n"
        "  - 'pagos_siniestros.estado_pago' puede ser: 'Procesado', 'Pendiente'.\n"
        "- La tabla 'evaluaciones_siniestro' contiene los detalles de la evaluación de un 'siniestro' (mediante 'id_siniestro').\n"
        "- 'afiliados.genero' puede ser: 'M' (Masculino), 'F' (Femenino).\n"
        "- Las columnas de fecha son: afiliados.fecha_nacimiento, afiliados.fecha_afiliacion, polizas.fecha_inicio, polizas.fecha_fin, siniestros.fecha_siniestro, siniestros.fecha_denuncia, pagos_siniestros.fecha_pago, evaluaciones_siniestro.fecha_evaluacion.\n"
        "REGLA CRÍTICA PARA FECHAS Y AGRUPACIONES: Las funciones de fecha como YEAR(col_fecha), MONTH(col_fecha), DAY(col_fecha) y DATE_FORMAT(col_fecha, 'formato') SOLO deben usarse en columnas que son explícitamente de tipo fecha (las listadas arriba). NUNCA uses funciones de fecha en columnas de texto como 'provincia', 'ciudad', 'nombre', 'tipo_seguro', 'estado_siniestro', etc. Si la pregunta pide agrupar por 'año-mes' de una columna de fecha real, puedes usar DATE_FORMAT(col_fecha_real, '%Y-%m') AS anio_mes. Para agrupaciones por columnas de texto como 'ciudad' o 'provincia', simplemente usa el nombre de la columna en el SELECT y en el GROUP BY. Por ejemplo, para 'Número de afiliados por ciudad', el SQL sería: SELECT ciudad, COUNT(id_afiliado) FROM afiliados GROUP BY ciudad.\n"
        f"\nConvierte esta pregunta en SQL compatible con MySQL / SingleStore: '{pregunta}'. "
        f"Solo devuelve el SQL, sin explicaciones ni comentarios. "
        "Si la pregunta implica contar o sumar por categorías (por ejemplo, 'cuántos por provincia', 'total por tipo_seguro', 'suma por año de fecha_siniestro', 'conteo por mes de fecha_afiliacion'), "
        "asegúrate de incluir la función de agregación (COUNT, SUM, etc.) en el SELECT y usar GROUP BY en la consulta SQL para obtener los resultados agregados por categoría. Por ejemplo, para 'conteo por mes de fecha_afiliacion en 2023', el SELECT podría ser DATE_FORMAT(fecha_afiliacion, '%Y-%m') AS anio_mes, COUNT(id_afiliado) AS cantidad_afiliados o YEAR(fecha_afiliacion) AS anio, MONTH(fecha_afiliacion) AS mes, COUNT(id_afiliado) AS cantidad_afiliados, y el WHERE incluiría YEAR(fecha_afiliacion) = 2023."
        
    )
    url = "http://localhost:11434/api/chat"
    # Asegúrate que "gemma3" sea el nombre correcto del modelo en Ollama (ej. gemma:7b, llama3).
    # Si usas una variante específica, cámbialo aquí.
    payload = {"model": "gemma3", "messages": [{"role": "user", "content": prompt}], "stream": True}
    headers = {"Content-Type": "application/json"}

    sql_parts = []
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                try:
                    line_json = json.loads(line.decode('utf-8'))
                    if 'message' in line_json and 'content' in line_json['message']:
                        sql_parts.append(line_json['message']['content'])
                    elif line_json.get("done") and not sql_parts and line_json.get("total_duration", 0) > 0:
                        if not sql_parts:
                            st.warning("El modelo finalizó la respuesta pero no generó contenido SQL.")
                            return ""
                except json.JSONDecodeError:
                    if not sql_parts:
                        st.warning(f"No se pudo decodificar una línea de la respuesta del modelo: {line.decode('utf-8')}")
                    continue
        
        if not sql_parts:
            st.warning("No se recibieron partes de SQL válidas del modelo.")
            return ""

        sql = ''.join(sql_parts)
        sql = sql.replace('```sql', '').replace('```', '').strip()
        
        if sql.endswith(';'):
            sql = sql[:-1].strip()

        if sql:
            sql += ';'
        else:
            st.warning("El SQL generado está vacío después de la limpieza.")
            return ""
        
        if sql.strip() == ';':
            st.warning("El SQL generado es inválido (solo un punto y coma).")
            return ""

        if not (sql.lower().startswith("select") or sql.lower().startswith("with")):
            st.warning(f"El SQL generado no parece ser una consulta SELECT válida: {sql}")
            # Considerar devolver "" o el SQL para que falle y muestre error.

        return sql

    except requests.exceptions.Timeout:
        st.error("Timeout al conectar con Ollama. El modelo está tardando demasiado en responder.")
        return ""
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión con Ollama: {e}")
        return ""
    except Exception as e:
        st.error(f"Error procesando la respuesta de Ollama: {e}")
        return ""

# === Ejecutar SQL ===
def ejecutar_sql(sql_query):
    if not sql_query or not sql_query.strip() or sql_query.strip() == ';':
        st.warning("No se proporcionó una consulta SQL para ejecutar.")
        return None
    try:
        # Escapar el carácter '%' para que no sea interpretado por el conector DB-API
        sql_query_escaped = sql_query.replace('%', '%%')

        with engine.connect() as connection:
            df = pd.read_sql_query(sql_query_escaped, connection) # Usar la query escapada
        
        # Conversión tentativa a datetime para columnas que contengan 'fecha' o 'mes'
        for col in df.columns:
            # Ampliar la detección de columnas de fecha
            if 'fecha' in col.lower() or col.lower().endswith('_at') or col.lower().startswith('date_') or 'nacimiento' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce') 
                except Exception: 
                    pass # Si falla la conversión, se deja la columna como está
        return df
    except pd.errors.DatabaseError as e: # Errores específicos de Pandas/SQLAlchemy al ejecutar SQL
        st.error(f"❌ Error de base de datos al ejecutar SQL: {e}")
        st.code(f"{sql_query}", language="sql") # Mostrar el SQL original que falló
        return None
    except Exception as e: # Otros errores inesperados
        st.error(f"❌ Error inesperado ejecutando SQL: {e}")
        st.code(f"{sql_query}", language="sql")
        return None

# === Generar recomendación ===
def generar_insight(dataframe):
    if dataframe is None or dataframe.empty:
        return "No se puede generar una recomendación porque no hay datos."
    
    # Crear un resumen más conciso si el dataframe es muy grande
    if len(dataframe) > 100:
        resumen_df = dataframe.sample(n=100).describe(include='all').to_string()
    else:
        resumen_df = dataframe.describe(include='all').to_string()

    prompt_insight = (
        f"Analiza el siguiente resumen estadístico de una consulta a una base de datos de seguros:\n\n{resumen_df}\n\n"
        "Basándote en este resumen, proporciona una recomendación o conclusión clave que sea útil para un analista de seguros. "
        "Sé breve y directo. La respuesta debe estar en español y no exceder las 3 frases. "
        "No repitas los números del resumen, enfócate en la interpretación."
        # "Cada vez que menciones un valor monetario, convierte ese valor a dólares estadounidenses "
        # "y formatea la cifra con el símbolo `$`, incluyendo separadores de miles y dos decimales.\n\n"
        # f"Analiza el siguiente resumen estadístico de una consulta a una base de datos de seguros:\n\n"
        # f"{resumen_df}\n\n"
        # "Basándote en este resumen, proporciona una recomendación o conclusión clave "
        # "que sea útil para un analista de seguros. Sé breve, directo y en español (máximo 3 frases). "
        # "No repitas los números del resumen, enfócate en la interpretación."

    )
    url = "http://localhost:11434/api/chat"
    # Asegúrate que "gemma3" sea el nombre correcto del modelo en Ollama.
    payload = {"model": "gemma3", "messages": [{"role": "user", "content": prompt_insight}], "stream": True}
    headers = {"Content-Type": "application/json"}
    
    insight_parts = []
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, stream=True, timeout=45)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                try:
                    line_json = json.loads(line.decode('utf-8'))
                    if 'message' in line_json and 'content' in line_json['message']:
                        insight_parts.append(line_json['message']['content'])
                except json.JSONDecodeError:
                    if not insight_parts:
                         st.warning(f"Error decodificando respuesta para insight: {line.decode('utf-8')}")
                    continue
        
        if not insight_parts:
            return "El modelo no generó una recomendación."
            
        # Limpiar el texto del insight antes de devolverlo
        cleaned_insight = ' '.join(''.join(insight_parts).strip().split())
        return cleaned_insight

    except requests.exceptions.Timeout:
        return "Timeout al generar la recomendación desde el modelo."
    except Exception as e:
        return f"Error al generar la recomendación: {e}"


# === Crear gráfico Matplotlib ===
def crear_grafico_matplotlib(categorias, valores, etiqueta_categoria, etiqueta_valor):
    if not categorias or not valores:
        return None
    if len(categorias) != len(valores):
        return None

    try:
        categorias_str = [str(cat) for cat in categorias]

        # === AJUSTE DE TAMAÑO DEL GRÁFICO ===
        # Puedes modificar estos valores para cambiar el tamaño del gráfico.
        # El primer valor es el ancho, el segundo es la altura (en pulgadas).
        ancho_grafico = 5 
        alto_grafico = 2
        fig, ax = plt.subplots(figsize=(ancho_grafico, alto_grafico)) 
        # ===================================
        
        bars = ax.bar(categorias_str, valores, color='skyblue')

        ax.set_title(f'Distribución de {etiqueta_valor} por {etiqueta_categoria}', fontsize=8) # Reducido
        ax.set_xlabel(etiqueta_categoria, fontsize=6) # Reducido
        ax.set_ylabel(etiqueta_valor, fontsize=6) # Reducido
        plt.xticks(rotation=45, ha="right", fontsize=5) # Reducido
        plt.yticks(fontsize=5) # Reducido

        if valores: 
            ax.set_ylim(0, max(valores) * 1.25 if max(valores) > 0 else 1.25) 

        for bar_item in bars:
            yval = bar_item.get_height()
            ax.text(bar_item.get_x() + bar_item.get_width()/2.0, yval + (max(valores)*0.02 if valores and max(valores) > 0 else 0.02), str(round(yval, 2)), ha='center', va='bottom', fontsize=4) # Reducido
        
        plt.tight_layout(pad=0.3) # Ajustar padding
        return fig
    except Exception as e:
        st.error(f"Error al crear gráfico Matplotlib: {e}")
        return None

# === Configuración de página y encabezado visual ===
st.set_page_config(page_title="Asistente DWConsulware", layout="wide", page_icon="📊")
matplotlib.use('Agg') # Configurar Matplotlib para backend no interactivo

# Inyectar CSS personalizado para texto más oscuro y cabeceras de tabla en negrita
st.markdown("""
<style>
    /* General text color for the body and common elements */
    body, p, div, span, li, label, figcaption, table, th, td, .stDataFrame div[data-testid="stTable"], .stTextInput>div>div>input, .stTextArea>label {
        color: #212121 !important; /* Very dark gray, almost black */
    }

    /* Input widgets text */
    .stTextInput input, .stTextArea textarea {
        color: #212121 !important;
    }
    
    /* Make DataFrame headers bold and ensure dark color */
    .stDataFrame table th {
        font-weight: bold !important;
        color: #212121 !important; /* Explicitly set header color */
    }
    
    /* Ensure DataFrame cell text is also dark */
    .stDataFrame table td {
        color: #212121 !important;
    }

    /* Tabs text */
    .stTabs [data-baseweb="tab"] div p { /* Targets the paragraph inside the tab label */
        color: #212121 !important;
    }
    .stTabs [aria-selected="true"] div p { /* Targets the paragraph inside the selected tab label */
        color: #003366 !important; /* Dark blue for active tab */
    }
    
    /* Text in st.info, st.warning, st.error */
    /* Aumentar tamaño de fuente para st.info (donde se muestra la recomendación) */
    div[data-testid="stInfo"] div[data-testid="stNotificationContent"] p {
         color: #0d2a40 !important; 
         font-size: 1.1em !important; /* Tamaño de fuente aumentado */
    }
    div[data-testid="stWarning"] div[data-testid="stNotificationContent"] p {
         color: #594400 !important; 
    }
    div[data-testid="stError"] div[data-testid="stNotificationContent"] p {
         color: #590000 !important; 
    }
    pre, code {
        color: #212121 !important;
        background-color: #f0f2f6 !important; 
    }
    /* CSS para asegurar que la imagen del logo no tenga bordes redondeados no deseados */
    div[data-testid="stImage"] img {
        border-radius: 0px !important;
    }
</style>
""", unsafe_allow_html=True)


# Encabezado alineado a la izquierda
try:
    st.image("mi_logo.png", width=190) # Ajusta el ancho del logo según necesites
except FileNotFoundError:
    st.info("Logo 'mi_logo.png' no encontrado.")
except Exception as e:
    st.warning(f"No se pudo cargar el logo: {e}")

st.markdown("<h1 style='color: #000000; text-align: left !important; margin-bottom: 0px; font-size: 2.2em;'>🔍 Asistente de Consultas Aseguradora</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color: #666; text-align: left !important; margin-top: 0px; font-weight: normal;'>Developed by <strong style='color:#1A73E8;'>PreSales & Value Creation - MVP Business Smart Insight</strong> — DWConsulware</h4>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #ccc;'/>", unsafe_allow_html=True)

# === Estado de sesión para persistencia ===
if 'sql_generado' not in st.session_state:
    st.session_state.sql_generado = ""
if 'pregunta_usuario' not in st.session_state:
    st.session_state.pregunta_usuario = "¿Cuántos afiliados hay en total?" # Pregunta inicial más genérica
if 'resultado' not in st.session_state:
    st.session_state.resultado = None
if 'insight' not in st.session_state:
    st.session_state.insight = ""


# === Pregunta del usuario ===
pregunta_actual = st.text_input("Escribe tu pregunta:", value=st.session_state.pregunta_usuario, key="input_pregunta_key")

if st.button("Enviar pregunta", key="btn_enviar_key"):
    st.session_state.pregunta_usuario = pregunta_actual # Actualizar la pregunta en el estado
    if not st.session_state.pregunta_usuario.strip():
        st.warning("Por favor, escribe una pregunta.")
        st.session_state.resultado = None # Limpiar resultados si la pregunta está vacía
        st.session_state.sql_generado = ""
        st.session_state.insight = ""
    else:
        with st.spinner("Generando SQL y obteniendo datos..."):
            st.session_state.sql_generado = pregunta_a_sql(st.session_state.pregunta_usuario)
            st.session_state.resultado = ejecutar_sql(st.session_state.sql_generado)
        
        if st.session_state.resultado is not None and not st.session_state.resultado.empty:
            with st.spinner("Generando recomendación..."):
                st.session_state.insight = generar_insight(st.session_state.resultado)
        else:
            st.session_state.insight = "No hay datos para generar una recomendación."


# === Mostrar resultados si existen usando pestañas ===
if st.session_state.resultado is not None:
    resultado_df = st.session_state.resultado # Usar el resultado del estado de sesión

    if not resultado_df.empty:
        # Pestañas: Consulta, Gráficos y Exportar. La recomendación se mueve a la pestaña de Gráficos.
        tab_nombres = ["📄 Consulta", "📊 Gráficos y Recomendación", "📥 Exportar"]
        
        tabs = st.tabs(tab_nombres)

        # Pestaña de Consulta
        with tabs[0]:
            st.markdown("### 📄 Resultado de la consulta")
            st.dataframe(resultado_df)

        # Pestaña de Gráficos y Recomendación (índice 1)
        with tabs[1]: 
            st.markdown("### 📊 Visualización")
            grafico_mostrado = False
            columnas_resultado = resultado_df.columns.tolist()
            
            col_conteo_detectada = None
            col_categoria_detectada = None

            if len(columnas_resultado) == 2:
                col1_nombre, col2_nombre = columnas_resultado[0], columnas_resultado[1]
                if isinstance(col1_nombre, str) and isinstance(col2_nombre, str): # Asegurar que los nombres de columna son strings
                    col1_tipo, col2_tipo = resultado_df[col1_nombre].dtype, resultado_df[col2_nombre].dtype
                    
                    # Lógica para identificar columna categórica (puede ser string o int como año) y numérica
                    es_col1_categoria = pd.api.types.is_string_dtype(col1_tipo) or pd.api.types.is_integer_dtype(col1_tipo) or pd.api.types.is_categorical_dtype(col1_tipo)
                    es_col2_categoria = pd.api.types.is_string_dtype(col2_tipo) or pd.api.types.is_integer_dtype(col2_tipo) or pd.api.types.is_categorical_dtype(col2_tipo)

                    if es_col1_categoria and pd.api.types.is_numeric_dtype(col2_tipo):
                        col_categoria_detectada, col_conteo_detectada = col1_nombre, col2_nombre
                    elif es_col2_categoria and pd.api.types.is_numeric_dtype(col1_tipo):
                        col_categoria_detectada, col_conteo_detectada = col2_nombre, col1_nombre
            
            if col_categoria_detectada and col_conteo_detectada:
                # Usar columnas para controlar el ancho del gráfico
                grafico_col, _ = st.columns([1.5, 1]) # Ajustar para que el gráfico sea más pequeño (ej. 1.5 de 2.5 partes)
                with grafico_col:
                    figura_matplotlib = crear_grafico_matplotlib(
                        resultado_df[col_categoria_detectada].tolist(),
                        resultado_df[col_conteo_detectada].tolist(),
                        col_categoria_detectada,
                        col_conteo_detectada
                    )
                    if figura_matplotlib:
                        st.pyplot(figura_matplotlib, use_container_width=True) 
                        grafico_mostrado = True
                
                # Gráfico de pastel como opción adicional si hay pocas categorías
                if len(resultado_df[col_categoria_detectada].unique()) <= 10: 
                     if st.button("Mostrar gráfico de pastel", key="btn_grafico_pastel_auto"): 
                        # Usar columnas para el pastel también, para controlar su tamaño
                        pastel_col, _ = st.columns([1,1]) # Más pequeño para el pastel
                        with pastel_col:
                            try:
                                fig_pastel, ax_pastel = plt.subplots(figsize=(3,1.8)) # Tamaño más pequeño para el pastel
                                labels_pastel = resultado_df[col_categoria_detectada].astype(str).tolist()
                                ax_pastel.pie(resultado_df[col_conteo_detectada], labels=labels_pastel, autopct='%1.1f%%', startangle=90, pctdistance=0.85, textprops={'fontsize': 4}) # Fuente más pequeña
                                ax_pastel.axis('equal') 
                                centre_circle = plt.Circle((0,0),0.70,fc='white')
                                fig_pastel.gca().add_artist(centre_circle)
                                st.pyplot(fig_pastel, use_container_width=True)
                            except Exception as e_pie:
                                st.error(f"No se pudo generar el gráfico de pastel: {e_pie}")

            # Gráfico de líneas si hay fechas
            fecha_col_detectada = next((col for col in resultado_df.columns if pd.api.types.is_datetime64_any_dtype(resultado_df[col])), None)
            if fecha_col_detectada:
                columnas_numericas_para_linea = [col for col in resultado_df.columns if pd.api.types.is_numeric_dtype(resultado_df[col]) and col != fecha_col_detectada]
                if columnas_numericas_para_linea:
                    try:
                        linea_grafico_col, _ = st.columns([1.5, 1]) # Controlar ancho del gráfico de líneas
                        with linea_grafico_col:
                            df_linea = resultado_df.set_index(fecha_col_detectada)
                            st.line_chart(df_linea[columnas_numericas_para_linea], height=180) # Altura reducida
                        grafico_mostrado = True
                    except Exception as e_line:
                         st.error(f"No se pudo generar el gráfico de líneas: {e_line}")

            if not grafico_mostrado:
                st.info("No se pudo generar un gráfico automáticamente con los datos actuales. Los datos podrían no tener el formato adecuado (ej. una columna de categorías y una numérica, o una columna de fechas y una numérica).")
            
            # Mostrar la recomendación debajo de los gráficos
            st.markdown("---") # Separador visual
            st.markdown("### 💡 Recomendación del modelo")
            if st.session_state.insight:
                 cleaned_insight = ' '.join(st.session_state.insight.split())
                 st.info(cleaned_insight) 
            else:
                 st.info("Generando recomendación...")
        
        # Pestaña de Exportar (índice 2, ya que Recomendación se movió)
        with tabs[2]: 
            st.markdown("### 📥 Exportar reporte")
            buffer = BytesIO()
            try:
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_exportar = resultado_df.copy()
                    for col in df_exportar.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_exportar[col]):
                            df_exportar[col] = df_exportar[col].astype(str)
                        if col.lower() == 'anio' and pd.api.types.is_integer_dtype(df_exportar[col]):
                            df_exportar[col] = df_exportar[col].astype(str)

                    df_exportar.to_excel(writer, index=False, sheet_name="Resultado Consulta")
                    
                    if st.session_state.insight:
                         pd.DataFrame({"Recomendacion": [st.session_state.insight]}).to_excel(writer, index=False, sheet_name="Recomendacion IA")
                    
                    info_consulta_df = pd.DataFrame({
                        "Pregunta Original": [st.session_state.pregunta_usuario],
                        "SQL Generado": [st.session_state.sql_generado]
                    })
                    info_consulta_df.to_excel(writer, index=False, sheet_name="Info Consulta")

                buffer.seek(0)
                st.download_button(
                    label="📥 Descargar Reporte Excel",
                    data=buffer,
                    file_name="reporte_aseguradora.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e_export:
                st.error(f"Error al generar el archivo Excel: {e_export}")
        

    elif st.session_state.sql_generado: 
        st.warning("⚠️ La consulta SQL se ejecutó pero no devolvió resultados.")
        if st.session_state.sql_generado: 
            st.markdown("#### SQL Generado:")
            st.code(st.session_state.sql_generado, language='sql')
    # No mostrar nada si no se ha presionado el botón y no hay resultados previos en sesión.

