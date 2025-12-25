import streamlit as st
import edge_tts
import asyncio
import io
import re
from datetime import datetime
from deep_translator import GoogleTranslator
import PyPDF2
import docx

# --- Configuración de Página ---
st.set_page_config(
    page_title="Studio Voz Master - Accesible", 
    page_icon="🎚️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 0. INICIALIZACIÓN DE ESTADO ---
if 'clean_start' not in st.session_state:
    st.session_state.historial = []
    st.session_state.texto_traducido = ""
    st.session_state.audio_origen = None
    st.session_state.audio_destino = None
    st.session_state.nombres_archivos = {"org": "", "dest": ""}
    st.session_state.rate_val = 0
    st.session_state.pitch_val = 0
    st.session_state.contenido_fuente = "" 
    st.session_state.clean_start = True

# --- 1. ESTILOS CSS (GLOBALES Y SIN SANGRÍA) ---
# Definimos los estilos aquí, pegados a la izquierda, para evitar errores visuales.

CSS_BASE = """
<style>
.stSelectbox label, .stTextArea label, .stSlider label { font-size: 1.1rem !important; font-weight: bold !important; margin-bottom: 0.4rem !important; }
div[data-baseweb="select"] > div:focus-within, textarea:focus, input:focus, button:focus { outline: 3px solid #FFFF00 !important; outline-offset: 2px; }
.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
div[data-testid="stVerticalBlock"] { gap: 1.5rem !important; }
textarea { font-size: 1.2rem !important; }
</style>
"""

CSS_OLED = """
<style>
.stApp { background-color: #000000; color: #E0E0E0; }
div[data-testid="stTextArea"] textarea { background-color: #111111; color: #FFFFFF; border: 1px solid #333333; }
div[data-testid="stSelectbox"] > div > div { background-color: #111111; color: white; }
div[data-testid="stSlider"] > div { color: #E0E0E0; }
h1, h2, h3, h4, h5, label, .stMarkdown, p { color: #FFFFFF !important; }
/* BOTÓN PROCESAR (Amarillo/Negro - Alto Contraste) */
div.stButton > button[kind="primary"] {
    background-color: #FFD700 !important;
    color: #000000 !important;
    font-weight: 900 !important;
    border: 2px solid #FFFFFF;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #FFC000 !important;
    color: #000000 !important;
    border: 2px solid #FFFF00;
}
</style>
"""

CSS_CLARO = """
<style>
.stApp { background-color: #FFFFFF; color: #000000; } 
label, h1, h2, h3, p { color: #000000 !important; }
/* BOTÓN PROCESAR (Azul/Blanco) */
div.stButton > button[kind="primary"] {
    background-color: #0056b3 !important;
    color: #FFFFFF !important;
    font-weight: bold !important;
}
</style>
"""

# --- 2. CABECERA Y SELECCIÓN DE TEMA ---
c_tit, c_sel = st.columns([6, 2], gap="medium")
with c_tit:
    st.markdown("<h1>🎚️ Studio Voz Master</h1>", unsafe_allow_html=True)
with c_sel:
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    tema_sel = st.selectbox("Apariencia visual", ["OLED (Negro)", "Claro", "Sistema"], help="Cambia el contraste y colores.")

# Inyectamos el estilo seleccionado
if "Negro" in tema_sel:
    st.markdown(CSS_BASE + CSS_OLED, unsafe_allow_html=True)
elif "Claro" in tema_sel:
    st.markdown(CSS_BASE + CSS_CLARO, unsafe_allow_html=True)
else:
    st.markdown(CSS_BASE, unsafe_allow_html=True)


# --- 3. DATOS DE VOCES ---
VOCES_LATINAS_ESTRUCTURA = {
    "Colombia": {"Salomé (Mujer)": "es-CO-SalomeNeural", "Gonzalo (Hombre)": "es-CO-GonzaloNeural"},
    "México": {"Dalia (Mujer)": "es-MX-DaliaNeural", "Jorge (Hombre)": "es-MX-JorgeNeural"},
    "Argentina": {"Elena (Mujer)": "es-AR-ElenaNeural", "Tomas (Hombre)": "es-AR-TomasNeural"},
    "España": {"Elvira (Mujer)": "es-ES-ElviraNeural", "Alvaro (Hombre)": "es-ES-AlvaroNeural"},
    "USA Latino": {"Paloma (Mujer)": "es-US-PalomaNeural", "Alonso (Hombre)": "es-US-AlonsoNeural"},
    "Otros Países": {"Venezuela - Paola": "es-VE-PaolaNeural", "Perú - Camila": "es-PE-CamilaNeural", "Chile - Catalina": "es-CL-CatalinaNeural"}
}
VOCES_EXTRANJERAS_ESTRUCTURA = {
    "Inglés (USA)": {"Jenny (Mujer)": {"code": "en-US-JennyNeural", "lang": "en"}, "Guy (Hombre)": {"code": "en-US-GuyNeural", "lang": "en"}},
    "Inglés (UK)": {"Ryan (Hombre)": {"code": "en-GB-RyanNeural", "lang": "en"}, "Sonia (Mujer)": {"code": "en-GB-SoniaNeural", "lang": "en"}},
    "Francés": {"Denise (Francia)": {"code": "fr-FR-DeniseNeural", "lang": "fr"}, "Henri (Francia)": {"code": "fr-FR-HenriNeural", "lang": "fr"}},
    "Portugués": {"Francisca (Brasil)": {"code": "pt-BR-FranciscaNeural", "lang": "pt"}, "Raquel (Portugal)": {"code": "pt-PT-RaquelNeural", "lang": "pt"}},
    "Otros Idiomas": {"Italiano - Isabella": {"code": "it-IT-IsabellaNeural", "lang": "it"}, "Alemán - Katja": {"code": "de-DE-KatjaNeural", "lang": "de"}}
}
VOCES_EXTRANJERAS_ESTRUCTURA["Español (Latino/España)"] = {}
for pais, voces in VOCES_LATINAS_ESTRUCTURA.items():
    for nombre_voz, codigo in voces.items():
        clave_nueva = f"{pais} - {nombre_voz}"
        VOCES_EXTRANJERAS_ESTRUCTURA["Español (Latino/España)"][clave_nueva] = {"code": codigo, "lang": "es"}

# --- 4. FUNCIONES DE LÓGICA ---
def extraer_texto_archivo(uploaded_file):
    try:
        texto = ""
        if uploaded_file.type == "text/plain": texto = str(uploaded_file.read(), "utf-8")
        elif uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages: texto += page.extract_text() + "\n"
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs: texto += para.text + "\n"
        return texto
    except Exception as e: return f"Error: {e}"

def generar_nombre_archivo(nombre_voz_full, velocidad, tono):
    nombre_clean = re.sub(r'[^\w\s-]', '', nombre_voz_full).strip()
    nombre_clean = nombre_clean.replace(" ", "_").replace("-", "")
    ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{nombre_clean}_Vel{velocidad}_P{tono}_{ahora}.mp3"

async def generar_audio_engine(texto, voz, velocidad, tono):
    try:
        rate_str = f"{'+' if velocidad >= 0 else ''}{velocidad}%"
        pitch_str = f"{'+' if tono >= 0 else ''}{tono}Hz"
        comunicacion = edge_tts.Communicate(text=texto, voice=voz, rate=rate_str, pitch=pitch_str)
        mp3_fp = io.BytesIO()
        async for chunk in comunicacion.stream():
            if chunk["type"] == "audio": mp3_fp.write(chunk["data"])
        return mp3_fp.getvalue()
    except Exception: return None

def reset_rate(): st.session_state.rate_val = 0
def reset_pitch(): st.session_state.pitch_val = 0

# --- 5. INTERFAZ GRÁFICA ---
col_izq, col_der = st.columns(2, gap="small")

with col_izq:
    st.markdown("### 1. Panel de Origen")
    pais_origen = st.selectbox("Paso 1: Seleccione el País o Región de origen", list(VOCES_LATINAS_ESTRUCTURA.keys()), help="Filtro de país.")
    voces_disponibles_origen = VOCES_LATINAS_ESTRUCTURA[pais_origen]
    voz_org_nombre_corta = st.selectbox(f"Paso 2: Seleccione la voz de {pais_origen}", list(voces_disponibles_origen.keys()), help="Selección de voz.")
    voz_org_code = voces_disponibles_origen[voz_org_nombre_corta]
    voz_org_nombre_completa = f"{pais_origen} - {voz_org_nombre_corta}"
    
    tab_escribir, tab_subir = st.tabs(["✍️ Escribir Texto", "📂 Subir Archivo"])
    with tab_subir:
        archivo = st.file_uploader("Cargar documento", type=["txt", "pdf", "docx"])
        if archivo is not None:
            texto_extraido = extraer_texto_archivo(archivo)
            if texto_extraido:
                st.session_state.contenido_fuente = texto_extraido
                st.success("Documento cargado.")
    with tab_escribir:
        def actualizar_texto(): st.session_state.contenido_fuente = st.session_state.txt_input_widget
        texto_usuario = st.text_area("Escriba o pegue el texto aquí", value=st.session_state.contenido_fuente, height=300, key="txt_input_widget", on_change=actualizar_texto, help="Cuadro de edición.")
        texto_a_procesar = st.session_state.contenido_fuente

with col_der:
    st.markdown("### 2. Panel de Destino")
    idioma_destino = st.selectbox("Paso 1: Seleccione el Idioma de destino", list(VOCES_EXTRANJERAS_ESTRUCTURA.keys()), help="Filtro de idioma.")
    voces_disponibles_destino = VOCES_EXTRANJERAS_ESTRUCTURA[idioma_destino]
    voz_dest_nombre_corta = st.selectbox(f"Paso 2: Seleccione la voz para {idioma_destino}", list(voces_disponibles_destino.keys()), help="Selección de voz destino.")
    datos_voz_dest = voces_disponibles_destino[voz_dest_nombre_corta]
    voz_dest_code = datos_voz_dest["code"]
    lang_dest = datos_voz_dest["lang"]
    voz_dest_nombre_completa = f"{idioma_destino} - {voz_dest_nombre_corta}"
    st.text_area("Texto resultante de la traducción", value=st.session_state.texto_traducido, height=368, help="Solo lectura.")

st.markdown("---")
c_ajustes, c_boton = st.columns([2, 1], gap="medium")

with c_ajustes:
    st.markdown("### Ajustes de Audio")
    k1, k2 = st.columns(2)
    with k1:
        s1, b1 = st.columns([5,1])
        velocidad = s1.slider("Velocidad", -100, 100, key="rate_val", step=1)
        b1.button("R", key="rv", on_click=reset_rate, help="Restablecer velocidad a cero")
    with k2:
        s2, b2 = st.columns([5,1])
        tono = s2.slider("Tono (Pitch)", -50, 50, key="pitch_val", step=1)
        b2.button("R", key="rp", on_click=reset_pitch, help="Restablecer tono a cero")

with c_boton:
    st.write("") 
    st.write("")
    if st.button("⚡ PROCESAR AUDIOS Y TRADUCCIÓN", type="primary", use_container_width=True):
        if not texto_a_procesar.strip():
            st.warning("El campo de texto está vacío.")
        else:
            with st.spinner('Procesando...'):
                try:
                    if lang_dest == 'es': resultado_traduccion = texto_a_procesar
                    else:
                        translator = GoogleTranslator(source='auto', target=lang_dest)
                        if len(texto_a_procesar) > 4500: resultado_traduccion = translator.translate(texto_a_procesar[:4500])
                        else: resultado_traduccion = translator.translate(texto_a_procesar)

                    st.session_state.texto_traducido = resultado_traduccion
                    
                    audio_es = asyncio.run(generar_audio_engine(texto_a_procesar, voz_org_code, velocidad, tono))
                    audio_tr = asyncio.run(generar_audio_engine(resultado_traduccion, voz_dest_code, velocidad, tono))

                    if audio_es and audio_tr:
                        fn_org = generar_nombre_archivo(voz_org_nombre_completa, velocidad, tono)
                        fn_dest = generar_nombre_archivo(voz_dest_nombre_completa, velocidad, tono)

                        st.session_state.audio_origen = audio_es
                        st.session_state.audio_destino = audio_tr
                        st.session_state.nombres_archivos = {"org": fn_org, "dest": fn_dest}
                        
                        now = datetime.now().strftime("%H:%M:%S")
                        st.session_state.historial.insert(0, {
                            "hora": now,
                            "org_txt": texto_a_procesar[:50] + "...",
                            "dest_txt": resultado_traduccion[:50] + "...",
                            "org_aud": audio_es,
                            "dest_aud": audio_tr,
                            "org_name": fn_org,
                            "dest_name": fn_dest
                        })
                        
                        # --- ALERTA ACCESIBLE Y ADAPTATIVA ---
                        if "Negro" in tema_sel:
                            # Fondo Verde Oscuro para OLED
                            estilo_alerta = "background-color: #054b0c; color: #e6ffed; border: 1px solid #0f6c18;"
                        else:
                            # Fondo Verde Claro para Modo Claro
                            estilo_alerta = "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;"

                        st.markdown(f"""
                            <div role="alert" style="{estilo_alerta} padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 20px; font-weight: bold;">
                                ✅ Tarea finalizada con éxito. Los audios están listos al final de la pantalla.
                            </div>
                        """, unsafe_allow_html=True)
                        st.toast("¡Tarea completada!", icon="✅")

                except Exception as e:
                    st.error(f"Error: {e}")

# RESULTADOS
if st.session_state.audio_origen and st.session_state.audio_destino:
    st.divider()
    st.markdown("### Resultados")
    r1, r2 = st.columns(2, gap="medium")
    with r1:
        st.write("**Audio Original**")
        st.audio(st.session_state.audio_origen, format='audio/mp3')
        st.download_button(f"Descargar Audio Izquierdo", st.session_state.audio_origen, file_name=st.session_state.nombres_archivos['org'], mime="audio/mp3", type="secondary", use_container_width=True)
    with r2:
        st.write("**Audio Resultado**")
        st.audio(st.session_state.audio_destino, format='audio/mp3')
        st.download_button(f"Descargar Audio Derecho", st.session_state.audio_destino, file_name=st.session_state.nombres_archivos['dest'], mime="audio/mp3", type="secondary", use_container_width=True)

# HISTORIAL
if st.session_state.historial:
    st.markdown("---")
    st.markdown("### Biblioteca")
    for i, item in enumerate(st.session_state.historial):
        with st.expander(f"{item['hora']} - {item['org_name']}"):
            h1, h2 = st.columns(2)
            with h1:
                st.caption(item['org_txt'])
                st.download_button("Descargar Audio Izquierdo", item['org_aud'], file_name=item['org_name'], key=f"ho_{i}")
            with h2:
                st.caption(item['dest_txt'])
                st.download_button("Descargar Audio Derecho", item['dest_aud'], file_name=item['dest_name'], key=f"hd_{i}")
