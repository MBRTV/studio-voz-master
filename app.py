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

# --- 1. CABECERA Y DISEÑO (CSS Adaptado para Accesibilidad) ---
css_base = """
<style>
/* Ajuste para que las etiquetas sean visibles pero no ocupen mucho espacio */
.stSelectbox label, .stTextArea label, .stSlider label {
    font-size: 1rem !important;
    font-weight: bold !important;
    margin-bottom: 0.2rem !important;
}
.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
div[data-testid="stVerticalBlock"] { gap: 1rem !important; }
textarea { font-size: 1.1rem !important; }
</style>
"""

css_oled = """
<style>
.stApp { background-color: #000000; color: #E0E0E0; }
div[data-testid="stTextArea"] textarea { background-color: #111111; color: #FFFFFF; border: 1px solid #333333; }
div[data-testid="stSelectbox"] > div > div { background-color: #111111; color: white; }
div[data-testid="stSlider"] > div { color: #E0E0E0; }
div[data-testid="stMarkdownContainer"] p { color: #E0E0E0; }
h1, h2, h3, h4, h5, label { color: #FFFFFF !important; }
div[data-testid="stFileUploader"] { background-color: #111111; padding: 10px; border-radius: 5px; }
/* Mejorar contraste del foco para baja visión */
button:focus, input:focus, textarea:focus, select:focus {
    outline: 2px solid #FF4B4B !important;
}
</style>
"""

css_claro = """<style>.stApp { background-color: #FFFFFF; color: #000000; }</style>"""

c_tit, c_sel = st.columns([6, 2], gap="medium")
with c_tit:
    st.markdown("<h1>🎚️ Studio Voz Master</h1>", unsafe_allow_html=True)
with c_sel:
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    tema_sel = st.selectbox("Apariencia visual", ["OLED (Negro)", "Claro", "Sistema"], help="Cambia el contraste y colores de la aplicación")

if "Negro" in tema_sel:
    st.markdown(css_base + css_oled, unsafe_allow_html=True)
elif "Claro" in tema_sel:
    st.markdown(css_base + css_claro, unsafe_allow_html=True)
else:
    st.markdown(css_base, unsafe_allow_html=True)


# --- 2. VOCES ---
VOCES_LATINAS = {
    "Colombia - Salomé (Mujer)": "es-CO-SalomeNeural",
    "Colombia - Gonzalo (Hombre)": "es-CO-GonzaloNeural",
    "México - Dalia (Mujer)": "es-MX-DaliaNeural",
    "México - Jorge (Hombre)": "es-MX-JorgeNeural",
    "Argentina - Elena (Mujer)": "es-AR-ElenaNeural",
    "Argentina - Tomas (Hombre)": "es-AR-TomasNeural",
    "España - Alvaro (Hombre)": "es-ES-AlvaroNeural",
    "España - Elvira (Mujer)": "es-ES-ElviraNeural",
    "USA - Paloma (Mujer Latina)": "es-US-PalomaNeural",
    "USA - Alonso (Hombre Latino)": "es-US-AlonsoNeural",
    "Venezuela - Paola (Mujer)": "es-VE-PaolaNeural",
    "Perú - Camila (Mujer)": "es-PE-CamilaNeural",
    "Chile - Catalina (Mujer)": "es-CL-CatalinaNeural"
}

VOCES_EXTRANJERAS = {
    "Inglés USA - Jenny":  {"voz": "en-US-JennyNeural", "lang": "en"},
    "Inglés USA - Guy":    {"voz": "en-US-GuyNeural",   "lang": "en"},
    "Inglés UK - Ryan":    {"voz": "en-GB-RyanNeural",  "lang": "en"},
    "Francés - Denise": {"voz": "fr-FR-DeniseNeural", "lang": "fr"},
    "Francés - Henri":  {"voz": "fr-FR-HenriNeural",  "lang": "fr"},
    "Portugués Brasil - Francisca": {"voz": "pt-BR-FranciscaNeural", "lang": "pt"},
    "Portugués Portugal - Raquel":  {"voz": "pt-PT-RaquelNeural",    "lang": "pt"},
    "Italiano - Isabella": {"voz": "it-IT-IsabellaNeural", "lang": "it"},
    "Italiano - Diego":    {"voz": "it-IT-DiegoNeural",    "lang": "it"},
    "Rumano - Alina": {"voz": "ro-RO-AlinaNeural", "lang": "ro"},
    "Alemán - Katja": {"voz": "de-DE-KatjaNeural", "lang": "de"}
}

VOCES_ORIGEN = VOCES_LATINAS
VOCES_DESTINO = VOCES_EXTRANJERAS.copy()
# Agregamos voces latinas al destino con nombres claros
for nombre, codigo in VOCES_LATINAS.items():
    nombre_claro = f"Español - {nombre}"
    VOCES_DESTINO[nombre_claro] = {"voz": codigo, "lang": "es"}

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

# --- 4. INTERFAZ ---
col_izq, col_der = st.columns(2, gap="small")

with col_izq:
    st.markdown("### 1. Panel de Origen")
    
    # ETIQUETA VISIBLE para JAWS
    voz_org_nombre = st.selectbox(
        "Seleccione la voz para el texto original", 
        list(VOCES_ORIGEN.keys()),
        help="Elija la voz que leerá el texto que usted escriba en el panel izquierdo."
    )
    voz_org_code = VOCES_ORIGEN[voz_org_nombre]
    
    tab_escribir, tab_subir = st.tabs(["✍️ Escribir Texto", "📂 Subir Archivo"])
    
    with tab_subir:
        archivo = st.file_uploader("Cargar documento (TXT, PDF, Word)", type=["txt", "pdf", "docx"], help="El texto del archivo se extraerá automáticamente.")
        if archivo is not None:
            texto_extraido = extraer_texto_archivo(archivo)
            if texto_extraido:
                st.session_state.contenido_fuente = texto_extraido
                st.success("Documento cargado correctamente. Verifique la pestaña Escribir.")
            else:
                st.error("No se pudo leer el archivo.")

    with tab_escribir:
        def actualizar_texto():
            st.session_state.contenido_fuente = st.session_state.txt_input_widget
            
        texto_usuario = st.text_area(
            "Escriba o pegue el texto aquí", 
            value=st.session_state.contenido_fuente,
            height=300, 
            key="txt_input_widget",
            on_change=actualizar_texto,
            help="Este es el texto principal que será convertido a voz y traducido."
        )
        texto_a_procesar = st.session_state.contenido_fuente

with col_der:
    st.markdown("### 2. Panel de Destino")
    
    # ETIQUETA VISIBLE para JAWS
    voz_dest_nombre = st.selectbox(
        "Seleccione el idioma y voz de destino", 
        list(VOCES_DESTINO.keys()),
        help="Esta voz leerá la traducción del texto. Si elige Español, solo leerá sin traducir."
    )
    info_dest = VOCES_DESTINO[voz_dest_nombre]
    
    st.text_area(
        "Texto resultante de la traducción", 
        value=st.session_state.texto_traducido, 
        height=368,
        help="Aquí aparecerá el texto traducido automáticamente después de procesar."
    )

# CONTROLES ACCESIBLES
st.markdown("---")
c_ajustes, c_boton = st.columns([2, 1], gap="medium")

with c_ajustes:
    st.markdown("### Ajustes de Voz")
    k1, k2 = st.columns(2)
    with k1:
        s1, b1 = st.columns([5,1])
        velocidad = s1.slider("Velocidad de lectura", -100, 100, key="rate_val", step=1, help="Aumenta o disminuye la rapidez de la voz.")
        b1.button("↺", key="rv", on_click=reset_rate, help="Restablecer velocidad a cero")
    with k2:
        s2, b2 = st.columns([5,1])
        tono = s2.slider("Tono de voz (Pitch)", -50, 50, key="pitch_val", step=1, help="Hace la voz más aguda o más grave.")
        b2.button("↺", key="rp", on_click=reset_pitch, help="Restablecer tono a cero")

with c_boton:
    st.write("") 
    st.write("")
    # Botón con etiqueta clara
    if st.button("⚡ PROCESAR AUDIO Y TRADUCCIÓN", type="primary", use_container_width=True, help="Presione para generar las voces y la traducción."):
        if not texto_a_procesar.strip():
            st.warning("El campo de texto está vacío. Por favor escriba algo.")
        else:
            with st.spinner('Procesando... por favor espere.'):
                try:
                    # Traducción
                    if info_dest['lang'] == 'es':
                        resultado_traduccion = texto_a_procesar
                    else:
                        translator = GoogleTranslator(source='auto', target=info_dest['lang'])
                        if len(texto_a_procesar) > 4500:
                            st.warning("Aviso: Texto muy largo. Se tradujeron los primeros 4500 caracteres.")
                            resultado_traduccion = translator.translate(texto_a_procesar[:4500])
                        else:
                            resultado_traduccion = translator.translate(texto_a_procesar)

                    st.session_state.texto_traducido = resultado_traduccion

                    # Audio
                    audio_es = asyncio.run(generar_audio_engine(texto_a_procesar, voz_org_code, velocidad, tono))
                    audio_tr = asyncio.run(generar_audio_engine(resultado_traduccion, info_dest['voz'], velocidad, tono))

                    if audio_es and audio_tr:
                        fn_org = generar_nombre_archivo(voz_org_nombre, velocidad, tono)
                        fn_dest = generar_nombre_archivo(voz_dest_nombre, velocidad, tono)

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
                        st.rerun()

                except Exception as e:
                    st.error(f"Ocurrió un error: {e}")

# RESULTADOS ACCESIBLES
if st.session_state.audio_origen and st.session_state.audio_destino:
    st.divider()
    st.markdown("### Resultados Generados")
    r1, r2 = st.columns(2, gap="medium")
    with r1:
        st.write("**Audio Original:**")
        st.audio(st.session_state.audio_origen, format='audio/mp3')
        st.download_button(
            label=f"Descargar Audio Izquierdo ({st.session_state.nombres_archivos['org']})", 
            data=st.session_state.audio_origen, 
            file_name=st.session_state.nombres_archivos['org'], 
            mime="audio/mp3", 
            type="secondary", 
            use_container_width=True
        )
    with r2:
        st.write("**Audio Resultado:**")
        st.audio(st.session_state.audio_destino, format='audio/mp3')
        st.download_button(
            label=f"Descargar Audio Derecho ({st.session_state.nombres_archivos['dest']})", 
            data=st.session_state.audio_destino, 
            file_name=st.session_state.nombres_archivos['dest'], 
            mime="audio/mp3", 
            type="secondary", 
            use_container_width=True
        )

# HISTORIAL
if st.session_state.historial:
    st.markdown("---")
    st.markdown("### Biblioteca de Audios Recientes")
    for i, item in enumerate(st.session_state.historial):
        with st.expander(f"Generado a las {item['hora']} - {item['org_name']}"):
            h1, h2 = st.columns(2)
            with h1:
                st.caption(f"Texto: {item['org_txt']}")
                st.download_button("Descargar Audio Izquierdo", item['org_aud'], file_name=item['org_name'], key=f"ho_{i}")
            with h2:
                st.caption(f"Texto: {item['dest_txt']}")
                st.download_button("Descargar Audio Derecho", item['dest_aud'], file_name=item['dest_name'], key=f"hd_{i}")
