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

# --- 1. CABECERA Y DISEÑO (CSS Accesible) ---
css_accesible = """
<style>
/* Etiquetas grandes y claras */
.stSelectbox label, .stTextArea label, .stSlider label {
    font-size: 1.1rem !important;
    font-weight: bold !important;
    color: #FFFFFF !important; 
    margin-bottom: 0.4rem !important;
}
/* Foco visible de alto contraste (Criterio WCAG para baja visión) */
div[data-baseweb="select"] > div:focus-within, textarea:focus, input:focus, button:focus {
    outline: 3px solid #FFFF00 !important; /* Amarillo para máximo contraste */
    outline-offset: 2px;
}
.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
div[data-testid="stVerticalBlock"] { gap: 1.5rem !important; }
textarea { font-size: 1.2rem !important; }
</style>
"""

css_oled = """
<style>
.stApp { background-color: #000000; color: #E0E0E0; }
div[data-testid="stTextArea"] textarea { background-color: #111111; color: #FFFFFF; border: 1px solid #333333; }
div[data-testid="stSelectbox"] > div > div { background-color: #111111; color: white; }
div[data-testid="stSlider"] > div { color: #E0E0E0; }
div[data-testid="stMarkdownContainer"] p { color: #E0E0E0; }
h1, h2, h3, h4, h5 { color: #FFFFFF !important; }
</style>
"""

css_claro = """<style>.stApp { background-color: #FFFFFF; color: #000000; } label { color: #000000 !important; }</style>"""

c_tit, c_sel = st.columns([6, 2], gap="medium")
with c_tit:
    st.markdown("<h1>🎚️ Studio Voz Master</h1>", unsafe_allow_html=True)
with c_sel:
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    tema_sel = st.selectbox("Apariencia visual", ["OLED (Negro)", "Claro", "Sistema"], help="Cambia el contraste y colores.")

if "Negro" in tema_sel:
    st.markdown(css_accesible + css_oled, unsafe_allow_html=True)
elif "Claro" in tema_sel:
    st.markdown(css_accesible + css_claro, unsafe_allow_html=True)
else:
    st.markdown(css_accesible, unsafe_allow_html=True)


# --- 2. VOCES ORGANIZADAS POR CATEGORÍA ---
VOCES_LATINAS_ESTRUCTURA = {
    "Colombia": {
        "Salomé (Mujer)": "es-CO-SalomeNeural",
        "Gonzalo (Hombre)": "es-CO-GonzaloNeural"
    },
    "México": {
        "Dalia (Mujer)": "es-MX-DaliaNeural",
        "Jorge (Hombre)": "es-MX-JorgeNeural"
    },
    "Argentina": {
        "Elena (Mujer)": "es-AR-ElenaNeural",
        "Tomas (Hombre)": "es-AR-TomasNeural"
    },
    "España": {
        "Elvira (Mujer)": "es-ES-ElviraNeural",
        "Alvaro (Hombre)": "es-ES-AlvaroNeural"
    },
    "USA Latino": {
        "Paloma (Mujer)": "es-US-PalomaNeural",
        "Alonso (Hombre)": "es-US-AlonsoNeural"
    },
    "Otros Países": {
        "Venezuela - Paola": "es-VE-PaolaNeural",
        "Perú - Camila": "es-PE-CamilaNeural",
        "Chile - Catalina": "es-CL-CatalinaNeural"
    }
}

VOCES_EXTRANJERAS_ESTRUCTURA = {
    "Inglés (USA)": {
        "Jenny (Mujer)": {"code": "en-US-JennyNeural", "lang": "en"},
        "Guy (Hombre)":  {"code": "en-US-GuyNeural",   "lang": "en"}
    },
    "Inglés (UK)": {
        "Ryan (Hombre)": {"code": "en-GB-RyanNeural", "lang": "en"},
        "Sonia (Mujer)": {"code": "en-GB-SoniaNeural", "lang": "en"}
    },
    "Francés": {
        "Denise (Francia)": {"code": "fr-FR-DeniseNeural", "lang": "fr"},
        "Henri (Francia)":  {"code": "fr-FR-HenriNeural",  "lang": "fr"}
    },
    "Portugués": {
        "Francisca (Brasil)": {"code": "pt-BR-FranciscaNeural", "lang": "pt"},
        "Raquel (Portugal)":  {"code": "pt-PT-RaquelNeural",    "lang": "pt"}
    },
    "Otros Idiomas": {
        "Italiano - Isabella": {"code": "it-IT-IsabellaNeural", "lang": "it"},
        "Alemán - Katja":      {"code": "de-DE-KatjaNeural",    "lang": "de"}
    }
}
VOCES_EXTRANJERAS_ESTRUCTURA["Español (Latino/España)"] = {}
for pais, voces in VOCES_LATINAS_ESTRUCTURA.items():
    for nombre_voz, codigo in voces.items():
        clave_nueva = f"{pais} - {nombre_voz}"
        VOCES_EXTRANJERAS_ESTRUCTURA["Español (Latino/España)"][clave_nueva] = {"code": codigo, "lang": "es"}


# --- 3. FUNCIONES LÓGICAS ---
def extraer_texto_archivo(uploaded_file):
    try:
        texto = ""
        if uploaded_file.type == "text/plain":
            texto = str(uploaded_file.read(), "utf-8")
        elif uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                texto += page.extract_text() + "\n"
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                texto += para.text + "\n"
        return texto
    except Exception as e:
        return f"Error leyendo archivo: {e}"

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
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])
        return mp3_fp.getvalue()
    except Exception:
        return None

def reset_rate(): st.session_state.rate_val = 0
def reset_pitch(): st.session_state.pitch_val = 0

# --- 4. INTERFAZ ACCESIBLE ---
col_izq, col_der = st.columns(2, gap="small")

with col_izq:
    st.markdown("### 1. Panel de Origen")
    
    # FILTROS ORIGEN
    pais_origen = st.selectbox(
        "Paso 1: Seleccione el País o Región de origen", 
        list(VOCES_LATINAS_ESTRUCTURA.keys()),
        help="Filtrar las voces por país ayuda a navegar la lista más rápido."
    )
    
    voces_disponibles_origen = VOCES_LATINAS_ESTRUCTURA[pais_origen]
    voz_org_nombre_corta = st.selectbox(
        f"Paso 2: Seleccione la voz de {pais_origen}", 
        list(voces_disponibles_origen.keys()),
        help="Elija la persona que leerá el texto."
    )
    voz_org_code = voces_disponibles_origen[voz_org_nombre_corta]
    voz_org_nombre_completa = f"{pais_origen} - {voz_org_nombre_corta}"
    
    # PESTAÑAS
    tab_escribir, tab_subir = st.tabs(["✍️ Escribir Texto", "📂 Subir Archivo"])
    
    with tab_subir:
        archivo = st.file_uploader("Cargar documento (TXT, PDF, Word)", type=["txt", "pdf", "docx"])
        if archivo is not None:
            texto_extraido = extraer_texto_archivo(archivo)
            if texto_extraido:
                st.session_state.contenido_fuente = texto_extraido
                st.success("Documento cargado.")

    with tab_escribir:
        def actualizar_texto():
            st.session_state.contenido_fuente = st.session_state.txt_input_widget
            
        texto_usuario = st.text_area(
            "Escriba o pegue el texto aquí", 
            value=st.session_state.contenido_fuente,
            height=300, 
            key="txt_input_widget",
            on_change=actualizar_texto,
            help="Texto principal a convertir."
        )
        texto_a_procesar = st.session_state.contenido_fuente

with col_der:
    st.markdown("### 2. Panel de Destino")
    
    # FILTROS DESTINO
    idioma_destino = st.selectbox(
        "Paso 1: Seleccione el Idioma de destino", 
        list(VOCES_EXTRANJERAS_ESTRUCTURA.keys()),
        help="Seleccione a qué idioma desea traducir."
    )
    
    voces_disponibles_destino = VOCES_EXTRANJERAS_ESTRUCTURA[idioma_destino]
    voz_dest_nombre_corta = st.selectbox(
        f"Paso 2: Seleccione la voz para {idioma_destino}", 
        list(voces_disponibles_destino.keys()),
        help="Elija la voz que leerá la traducción."
    )
    
    datos_voz_dest = voces_disponibles_destino[voz_dest_nombre_corta]
    voz_dest_code = datos_voz_dest["code"]
    lang_dest = datos_voz_dest["lang"]
    voz_dest_nombre_completa = f"{idioma_destino} - {voz_dest_nombre_corta}"

    st.text_area(
        "Texto resultante de la traducción", 
        value=st.session_state.texto_traducido, 
        height=368,
        help="Aquí aparecerá el texto traducido automáticamente."
    )

# CONTROLES MEJORADOS
st.markdown("---")
c_ajustes, c_boton = st.columns([2, 1], gap="medium")

with c_ajustes:
    st.markdown("### Ajustes de Audio")
    k1, k2 = st.columns(2)
    with k1:
        s1, b1 = st.columns([5,1])
        velocidad = s1.slider("Velocidad", -100, 100, key="rate_val", step=1, help="Velocidad de lectura")
        # BOTÓN PEQUEÑO CON ETIQUETA '↺' PERO AYUDA DESCRIPTIVA
        b1.button("↺", key="rv", on_click=reset_rate, help="Restablecer velocidad a cero")
    with k2:
        s2, b2 = st.columns([5,1])
        tono = s2.slider("Tono (Pitch)", -50, 50, key="pitch_val", step=1, help="Agudeza de la voz")
        # BOTÓN PEQUEÑO CON ETIQUETA '↺' PERO AYUDA DESCRIPTIVA
        b2.button("↺", key="rp", on_click=reset_pitch, help="Restablecer tono a cero")

with c_boton:
    st.write("") 
    st.write("")
    if st.button("⚡ PROCESAR AUDIO Y TRADUCCIÓN", type="primary", use_container_width=True):
        if not texto_a_procesar.strip():
            st.warning("El campo de texto está vacío.")
        else:
            with st.spinner('Procesando...'):
                try:
                    # Traducción
                    if lang_dest == 'es':
                        resultado_traduccion = texto_a_procesar
                    else:
                        translator = GoogleTranslator(source='auto', target=lang_dest)
                        if len(texto_a_procesar) > 4500:
                            st.warning("Texto cortado a 4500 caracteres.")
                            resultado_traduccion = translator.translate(texto_a_procesar[:4500])
                        else:
                            resultado_traduccion = translator.translate(texto_a_procesar)

                    st.session_state.texto_traducido = resultado_traduccion

                    # Audio
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
                        
                        # --- NOTIFICACIÓN DE FINALIZACIÓN ---
                        st.toast("¡Tarea completada con éxito!", icon="✅")
                        st.success("¡Tarea finalizada! Los audios y la traducción están listos al final de la pantalla.") 
                        
                        st.rerun()

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
