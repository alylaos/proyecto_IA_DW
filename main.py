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
        "- 'afiliados.fecha_afiliacion' es la fecha de registro del afiliado.\n"
        "- 'polizas.fecha_inicio' y 'polizas.fecha_fin' definen la vigencia de la póliza.\n"
        "- 'siniestros.fecha_siniestro' es la fecha del evento y 'siniestros.fecha_denuncia' es cuándo se reportó.\n"
        "- 'pagos_siniestros.fecha_pago' es cuándo se efectuó un pago.\n"
        "- 'evaluaciones_siniestro.fecha_evaluacion' es cuándo se evaluó el siniestro.\n"
        "REGLA PARA FECHAS: Para extraer el año, usa YEAR(col_fecha). Para extraer el mes, usa MONTH(col_fecha). Si la pregunta pide agrupar o mostrar 'año-mes' o 'mes y año' como una sola columna formateada (ej. '2023-01'), puedes usar DATE_FORMAT(col_fecha, '%Y-%m') y nombrarla apropiadamente (ej. 'anio_mes'). De lo contrario, prefiere seleccionar YEAR() y MONTH() como columnas separadas. Evita DATE_FORMAT con '%' si solo necesitas el número del año o del mes para filtros o agrupaciones simples.\n"
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
        
        for col in df.columns:
            if 'fecha' in col.lower() or col.lower().endswith('_at') or col.lower().startswith('date_') or 'nacimiento' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce') 
                except Exception: 
                    pass 
        return df
    except pd.errors.DatabaseError as e: 
        st.error(f"❌ Error de base de datos al ejecutar SQL: {e}")
        st.code(f"{sql_query}", language="sql") 
        return None
    except Exception as e: 
        st.error(f"❌ Error inesperado ejecutando SQL: {e}")
        st.code(f"{sql_query}", language="sql")
        return None

# === Generar recomendación ===
def generar_insight(dataframe):
    if dataframe is None or dataframe.empty:
        return "No se puede generar una recomendación porque no hay datos."
    
    if len(dataframe) > 100:
        resumen_df = dataframe.sample(n=100).describe(include='all').to_string()
    else:
        resumen_df = dataframe.describe(include='all').to_string()

    prompt_insight = (
        f"Analiza el siguiente resumen estadístico de una consulta a una base de datos de seguros:\n\n{resumen_df}\n\n"
        "Basándote en este resumen, proporciona una recomendación o conclusión clave que sea útil para un analista de seguros. "
        "Sé breve y directo. La respuesta debe estar en español y no exceder las 3 frases. "
        "No repitas los números del resumen, enfócate en la interpretación."
    )
    url = "http://localhost:11434/api/chat"
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
            
        return ''.join(insight_parts).strip()

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
        fig, ax = plt.subplots(figsize=(10, 7))
        bars = ax.bar(categorias_str, valores, color='skyblue')

        ax.set_title(f'Distribución de {etiqueta_valor} por {etiqueta_categoria}', fontsize=14)
        ax.set_xlabel(etiqueta_categoria, fontsize=12)
        ax.set_ylabel(etiqueta_valor, fontsize=12)
        plt.xticks(rotation=45, ha="right", fontsize=10)
        plt.yticks(fontsize=10)

        if valores:
            ax.set_ylim(0, max(valores) * 1.15 if max(valores) > 0 else 1) 

        for bar_item in bars:
            yval = bar_item.get_height()
            ax.text(bar_item.get_x() + bar_item.get_width()/2.0, yval + (max(valores)*0.01 if valores and max(valores) > 0 else 0.01), str(round(yval, 2)), ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        return fig
    except Exception as e:
        st.error(f"Error al crear gráfico Matplotlib: {e}")
        return None

# === Configuración de página y encabezado visual ===
st.set_page_config(page_title="Asistente DWConsulware", layout="wide", page_icon="📊")
matplotlib.use('Agg') 

col_logo_izq, col_titulo, col_logo_der = st.columns([1,8,1.5]) 
with col_titulo:
    st.markdown("<h1 style='color: #003366; text-align: center;'>🔍 Asistente de Consultas Aseguradora</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='color: #666; text-align: center;'>Developed by <strong style='color:#1A73E8;'>PreSales & Value Creation - MVP Business Smart Insight</strong> — DWConsulware</h4>", unsafe_allow_html=True)
with col_logo_der:
    try:
        st.image("mi_logo.png", width=140) 
    except FileNotFoundError:
        st.info("Logo 'mi_logo.png' no encontrado.")
    except Exception as e:
        st.warning(f"No se pudo cargar el logo: {e}")

st.markdown("<hr style='border: 1px solid #ccc;'/>", unsafe_allow_html=True)

if 'sql_generado' not in st.session_state:
    st.session_state.sql_generado = ""
if 'pregunta_usuario' not in st.session_state:
    st.session_state.pregunta_usuario = "¿Cuántos afiliados hay en total?" 
if 'resultado' not in st.session_state:
    st.session_state.resultado = None
if 'insight' not in st.session_state:
    st.session_state.insight = ""

pregunta_actual = st.text_input("Escribe tu pregunta:", value=st.session_state.pregunta_usuario, key="input_pregunta_key")

if st.button("Enviar pregunta", key="btn_enviar_key"):
    st.session_state.pregunta_usuario = pregunta_actual 
    if not st.session_state.pregunta_usuario.strip():
        st.warning("Por favor, escribe una pregunta.")
        st.session_state.resultado = None 
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

if st.session_state.resultado is not None:
    resultado_df = st.session_state.resultado 

    if not resultado_df.empty:
        # Pestañas: Consulta, Gráficos y Exportar. La recomendación se mueve a la pestaña de Gráficos.
        tab_nombres = ["📄 Consulta", "📊 Gráficos y Recomendación", "📥 Exportar"]
        
        tabs = st.tabs(tab_nombres)

        # Pestaña de Consulta
        with tabs[0]:
            st.markdown("### 📄 Resultado de la consulta")
            st.dataframe(resultado_df)
            if st.session_state.sql_generado: 
                st.markdown("#### SQL Generado:")
                st.code(st.session_state.sql_generado, language='sql')

        # Pestaña de Gráficos y Recomendación (índice 1)
        with tabs[1]: 
            st.markdown("### 📊 Visualización")
            grafico_mostrado = False
            columnas_resultado = resultado_df.columns.tolist()
            
            col_conteo_detectada = None
            col_categoria_detectada = None

            if len(columnas_resultado) == 2:
                col1_nombre, col2_nombre = columnas_resultado[0], columnas_resultado[1]
                if isinstance(col1_nombre, str) and isinstance(col2_nombre, str): 
                    col1_tipo, col2_tipo = resultado_df[col1_nombre].dtype, resultado_df[col2_nombre].dtype
                    
                    es_col1_categoria = pd.api.types.is_string_dtype(col1_tipo) or pd.api.types.is_integer_dtype(col1_tipo) or pd.api.types.is_categorical_dtype(col1_tipo)
                    es_col2_categoria = pd.api.types.is_string_dtype(col2_tipo) or pd.api.types.is_integer_dtype(col2_tipo) or pd.api.types.is_categorical_dtype(col2_tipo)

                    if es_col1_categoria and pd.api.types.is_numeric_dtype(col2_tipo):
                        col_categoria_detectada, col_conteo_detectada = col1_nombre, col2_nombre
                    elif es_col2_categoria and pd.api.types.is_numeric_dtype(col1_tipo):
                        col_categoria_detectada, col_conteo_detectada = col2_nombre, col1_nombre
            
            if col_categoria_detectada and col_conteo_detectada:
                figura_matplotlib = crear_grafico_matplotlib(
                    resultado_df[col_categoria_detectada].tolist(),
                    resultado_df[col_conteo_detectada].tolist(),
                    col_categoria_detectada,
                    col_conteo_detectada
                )
                if figura_matplotlib:
                    st.pyplot(figura_matplotlib)
                    grafico_mostrado = True
                
                if len(resultado_df[col_categoria_detectada].unique()) <= 10: 
                     if st.button("Mostrar gráfico de pastel", key="btn_grafico_pastel_auto"): 
                        try:
                            fig_pastel, ax_pastel = plt.subplots()
                            labels_pastel = resultado_df[col_categoria_detectada].astype(str).tolist()
                            ax_pastel.pie(resultado_df[col_conteo_detectada], labels=labels_pastel, autopct='%1.1f%%', startangle=90, pctdistance=0.85)
                            ax_pastel.axis('equal') 
                            centre_circle = plt.Circle((0,0),0.70,fc='white')
                            fig_pastel.gca().add_artist(centre_circle)
                            st.pyplot(fig_pastel)
                        except Exception as e_pie:
                            st.error(f"No se pudo generar el gráfico de pastel: {e_pie}")

            fecha_col_detectada = next((col for col in resultado_df.columns if pd.api.types.is_datetime64_any_dtype(resultado_df[col])), None)
            if fecha_col_detectada:
                columnas_numericas_para_linea = [col for col in resultado_df.columns if pd.api.types.is_numeric_dtype(resultado_df[col]) and col != fecha_col_detectada]
                if columnas_numericas_para_linea:
                    try:
                        df_linea = resultado_df.set_index(fecha_col_detectada)
                        st.line_chart(df_linea[columnas_numericas_para_linea])
                        grafico_mostrado = True
                    except Exception as e_line:
                         st.error(f"No se pudo generar el gráfico de líneas: {e_line}")

            if not grafico_mostrado:
                st.info("No se pudo generar un gráfico automáticamente con los datos actuales. Los datos podrían no tener el formato adecuado (ej. una columna de categorías y una numérica, o una columna de fechas y una numérica).")
            
            # Mostrar la recomendación debajo de los gráficos
            st.markdown("---") # Separador visual
            st.markdown("### 💡 Recomendación del modelo")
            if st.session_state.insight:
                 st.info(st.session_state.insight)
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

